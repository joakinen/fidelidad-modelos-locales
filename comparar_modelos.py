"""Compara modelos generadores sobre las mismas preguntas y los mismos fragmentos.

Usa la recuperación del servicio (todas las páginas permitidas), así que solo
cambia el modelo. Semilla fija, mismo prompt, mismo contexto (8K).

Cada configuración es `modelo` o `modelo@razonamiento`, donde razonamiento es
`si` (think=true) o un nivel `low|medium|high` (gpt-oss). Sin @, el
razonamiento va apagado si el modelo lo admite.

Salida:
  resultados.json    respuestas, velocidad, latencia, memoria
  ciego_<n>.json     lotes para evaluación ciega (respuestas como R1..Rk,
                     barajadas en cada pregunta)
  claves.json        qué configuración es cada Rk en cada pregunta

    uv run python comparar_modelos.py salida/ gemma4:12b qwen3.5:9b qwen3.5:9b@si
"""

import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import httpx

from config import OLLAMA
from servicio import embeber, indice, montar_mensajes, seleccionar

SEMILLA = 42
LOTES = 2  # en cuántos ficheros se parte la evaluación ciega

# Las preguntas se leen de un fichero JSON (lista de cadenas). Las del estudio
# no se publican porque identifican el corpus; ver preguntas.ejemplo.json.
PREGUNTAS = json.loads(Path(os.environ.get("PREGUNTAS", "preguntas.json")).read_text())


def leer_config(config: str) -> tuple[str, object]:
    modelo, _, razona = config.partition("@")
    if razona == "si":
        return modelo, True
    if razona in ("low", "medium", "high"):
        return modelo, razona
    return modelo, False


async def capacidades(cliente: httpx.AsyncClient, modelo: str) -> list[str]:
    r = await cliente.post(f"{OLLAMA}/api/show", json={"model": modelo})
    r.raise_for_status()
    return r.json().get("capabilities", [])


async def responder(cliente, modelo, razona, admite_razonar, mensajes) -> dict:
    cuerpo = {
        "model": modelo,
        "messages": mensajes,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.3, "num_ctx": 8192, "seed": SEMILLA},
    }
    if admite_razonar:
        cuerpo["think"] = razona
    r = await cliente.post(f"{OLLAMA}/api/chat", json=cuerpo)
    r.raise_for_status()
    d = r.json()
    return {
        "texto": d["message"]["content"],
        "razonamiento_caracteres": len(d["message"].get("thinking") or ""),
        "tok_s": round(d["eval_count"] / d["eval_duration"] * 1e9, 1),
        "segundos": round(d["total_duration"] / 1e9, 1),
        "tokens": d["eval_count"],
    }


async def memoria(cliente, modelo) -> float | None:
    r = await cliente.get(f"{OLLAMA}/api/ps")
    for m in r.json().get("models", []):
        if m["name"] == modelo or m["model"] == modelo:
            return round(m["size"] / 1e9, 1)
    return None


def comprobaciones(texto: str, n_fuentes: int) -> dict:
    citas = [int(n) for grupo in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", texto) for n in re.split(r"\s*,\s*", grupo)]
    return {
        "citas": len(citas),
        "citas_fuera_de_rango": sorted({n for n in citas if not 1 <= n <= n_fuentes}),
        "caracteres_no_latinos": bool(re.search(r"[Ѐ-ӿ぀-ヿ一-鿿]", texto)),
        "vacia": not texto.strip(),
    }


async def main(salida: Path, configs: list[str]):
    salida.mkdir(parents=True, exist_ok=True)
    indice.actualizar()
    todas = set(indice.paginas.tolist())

    # Fragmentos fijos para todas las configuraciones.
    casos = []
    for pregunta in PREGUNTAS:
        fragmentos = seleccionar(indice.similitudes(await embeber(pregunta)), todas)
        mensajes, fuentes = montar_mensajes(pregunta, fragmentos)
        casos.append({"pregunta": pregunta, "mensajes": mensajes, "fuentes": fuentes})

    respuestas: dict[str, list[dict]] = {}
    resumen: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=1200) as cliente:
        for config in configs:  # modelo a modelo: cada uno se carga una sola vez
            modelo, razona = leer_config(config)
            admite = "thinking" in await capacidades(cliente, modelo)
            await responder(cliente, modelo, razona, admite, [{"role": "user", "content": "Hola"}])
            respuestas[config] = []
            for i, caso in enumerate(casos, 1):
                r = await responder(cliente, modelo, razona, admite, caso["mensajes"])
                r.update(comprobaciones(r["texto"], len(caso["fuentes"])))
                respuestas[config].append(r)
                print(f"{config:22s} P{i:<2} {r['tok_s']:5.1f} tok/s {r['segundos']:6.1f} s", flush=True)
            rs = respuestas[config]
            resumen[config] = {
                "memoria_gb": await memoria(cliente, modelo),
                "tok_s": round(sum(x["tok_s"] for x in rs) / len(rs), 1),
                "segundos_media": round(sum(x["segundos"] for x in rs) / len(rs), 1),
                "tokens_media": round(sum(x["tokens"] for x in rs) / len(rs)),
                "citas_fuera_de_rango": sum(bool(x["citas_fuera_de_rango"]) for x in rs),
                "sin_citas": sum(x["citas"] == 0 for x in rs),
                "no_latinos": sum(x["caracteres_no_latinos"] for x in rs),
                "vacias": sum(x["vacia"] for x in rs),
            }
            await cliente.post(f"{OLLAMA}/api/generate", json={"model": modelo, "keep_alive": 0})

    rng = random.Random(SEMILLA)
    claves, lotes = {}, [[] for _ in range(LOTES)]
    for i, caso in enumerate(casos, 1):
        orden = configs[:]
        rng.shuffle(orden)
        claves[i] = {f"R{k}": c for k, c in enumerate(orden, 1)}
        lotes[(i - 1) * LOTES // len(casos)].append(
            {
                "n": i,
                "pregunta": caso["pregunta"],
                "fragmentos": caso["mensajes"][1]["content"],
                "respuestas": {f"R{k}": respuestas[c][i - 1]["texto"] for k, c in enumerate(orden, 1)},
            }
        )

    (salida / "resultados.json").write_text(
        json.dumps(
            {"preguntas": PREGUNTAS, "resumen": resumen, "respuestas": respuestas, "fuentes": [c["fuentes"] for c in casos]},
            ensure_ascii=False,
            indent=1,
        )
    )
    for n, lote in enumerate(lotes, 1):
        (salida / f"ciego_{n}.json").write_text(json.dumps(lote, ensure_ascii=False, indent=1))
    (salida / "claves.json").write_text(json.dumps(claves, indent=1))

    print()
    for config, r in resumen.items():
        print(f"{config:22s} {json.dumps(r)}")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2:]))
