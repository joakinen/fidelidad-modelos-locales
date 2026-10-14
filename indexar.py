"""Construye o actualiza el índice semántico de la wiki.

Lee los .txt de las páginas de una wiki DokuWiki, los trocea por secciones y
calcula embeddings con bge-m3 en Ollama. Solo recalcula las páginas que han
cambiado desde la última vez.

    uv run python indexar.py            # incremental
    uv run python indexar.py --todo     # desde cero
"""

import hashlib
import json
import re
import sys
import time

import httpx
import numpy as np

from config import DIR_INDICE, DIR_PAGINAS, EXCLUIR, MODELO_EMBED, OLLAMA

TAM_TROZO = 1500  # caracteres, aprox. 350-400 tokens
MIN_PAGINA = 200  # páginas más cortas no aportan (índices, redirecciones)

RE_TITULO = re.compile(r"^\s*(={2,6})\s*(.+?)\s*\1\s*$", re.M)
RE_ENLACE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
RE_ENLACE_SOLO = re.compile(r"\[\[([^\]|]+)\]\]")
RE_MEDIA = re.compile(r"\{\{[^}]*\}\}")
RE_ETIQUETAS = re.compile(r"</?(WRAP|wrap|html|HTML|div|span|font|nowiki|code|file)[^>]*>")
RE_MACRO = re.compile(r"~~[A-Z_]+(:[^~]*)?~~")


def id_pagina(ruta) -> str:
    return ":".join(ruta.relative_to(DIR_PAGINAS).with_suffix("").parts)


def excluida(pid: str) -> bool:
    """«ns:» excluye un espacio de nombres; otro valor, páginas cuyo nombre
    empieza así en cualquier espacio (sidebar, motd2...)."""
    nombre = pid.split(":")[-1]
    return any(pid.startswith(e) if e.endswith(":") else nombre.startswith(e) for e in EXCLUIR)


def limpiar(texto: str) -> str:
    texto = RE_MEDIA.sub("", texto)
    texto = RE_ENLACE.sub(r"\2", texto)
    texto = RE_ENLACE_SOLO.sub(r"\1", texto)
    texto = RE_ETIQUETAS.sub("", texto)
    texto = RE_MACRO.sub("", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def trocear(pid: str, texto: str) -> list[dict]:
    """Trozos de hasta TAM_TROZO caracteres que no cruzan secciones.

    Cada trozo lleva delante «título de página > sección» para que el
    embedding sepa de qué va aunque el párrafo no lo diga.
    """
    m = RE_TITULO.search(texto)
    titulo = m.group(2) if m else pid.split(":")[-1]

    secciones, ultimo, seccion = [], 0, ""
    for m in RE_TITULO.finditer(texto):
        secciones.append((seccion, texto[ultimo : m.start()]))
        seccion, ultimo = m.group(2), m.end()
    secciones.append((seccion, texto[ultimo:]))

    trozos = []
    for seccion, cuerpo in secciones:
        cuerpo = limpiar(cuerpo)
        if not cuerpo:
            continue
        actual = ""
        for parrafo in re.split(r"\n\s*\n", cuerpo):
            while len(parrafo) > TAM_TROZO:  # párrafos enormes: cortar en frases
                corte = parrafo.rfind(". ", 0, TAM_TROZO) + 1 or TAM_TROZO
                if actual:
                    trozos.append((seccion, actual))
                    actual = ""
                trozos.append((seccion, parrafo[:corte].strip()))
                parrafo = parrafo[corte:].strip()
            if len(actual) + len(parrafo) > TAM_TROZO and actual:
                trozos.append((seccion, actual))
                actual = ""
            actual = f"{actual}\n\n{parrafo}" if actual else parrafo
        if actual:
            trozos.append((seccion, actual))

    return [
        {
            "pagina": pid,
            "titulo": titulo,
            "seccion": seccion,
            "texto": t,
            "cabecera": f"{titulo} > {seccion}" if seccion and seccion != titulo else titulo,
        }
        for seccion, t in trozos
    ]


def embeber(textos: list[str], cliente: httpx.Client) -> np.ndarray:
    r = cliente.post(f"{OLLAMA}/api/embed", json={"model": MODELO_EMBED, "input": textos})
    r.raise_for_status()
    v = np.array(r.json()["embeddings"], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def main(desde_cero: bool = False):
    DIR_INDICE.mkdir(parents=True, exist_ok=True)
    f_trozos, f_vectores = DIR_INDICE / "trozos.jsonl", DIR_INDICE / "vectores.npy"

    previos, vect_previos = {}, None
    if not desde_cero and f_trozos.exists():
        vect_previos = np.load(f_vectores)
        for i, linea in enumerate(f_trozos.open()):
            t = json.loads(linea)
            previos.setdefault(t["pagina"], {"hash": t["hash"], "filas": []})["filas"].append((i, t))

    trozos, vectores, pendientes = [], [], []
    reutilizadas = 0
    for ruta in sorted(DIR_PAGINAS.rglob("*.txt")):
        pid = id_pagina(ruta)
        if excluida(pid):
            continue
        texto = ruta.read_text(errors="replace")
        if len(texto) < MIN_PAGINA:
            continue
        h = hashlib.sha1(texto.encode()).hexdigest()
        if pid in previos and previos[pid]["hash"] == h:
            for i, t in previos[pid]["filas"]:
                trozos.append(t)
                vectores.append(vect_previos[i])
            reutilizadas += 1
            continue
        for t in trocear(pid, texto):
            t["hash"] = h
            pendientes.append(t)

    print(f"{reutilizadas} páginas sin cambios, {len(pendientes)} trozos nuevos que embeber")
    inicio = time.time()
    with httpx.Client(timeout=300) as cliente:
        for i in range(0, len(pendientes), 32):
            lote = pendientes[i : i + 32]
            v = embeber([f"{t['cabecera']}\n\n{t['texto']}" for t in lote], cliente)
            trozos.extend(lote)
            vectores.extend(v)
            print(f"  {i + len(lote)}/{len(pendientes)}  ({time.time() - inicio:.0f} s)", end="\r")
    print()

    # Escritura atómica: el servicio puede estar leyendo el índice anterior.
    tmp_t, tmp_v = f_trozos.with_suffix(".tmp"), DIR_INDICE / "vectores.tmp.npy"
    with tmp_t.open("w") as f:
        for t in trozos:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    np.save(tmp_v, np.array(vectores, dtype=np.float32).reshape(-1, 1024))
    tmp_v.replace(f_vectores)
    tmp_t.replace(f_trozos)
    (DIR_INDICE / "estado.json").write_text(
        json.dumps(
            {
                "fecha": time.strftime("%Y-%m-%d %H:%M"),
                "paginas": len({t["pagina"] for t in trozos}),
                "trozos": len(trozos),
            }
        )
    )
    print(f"Índice: {len(trozos)} trozos de {len({t['pagina'] for t in trozos})} páginas")


if __name__ == "__main__":
    main(desde_cero="--todo" in sys.argv)
