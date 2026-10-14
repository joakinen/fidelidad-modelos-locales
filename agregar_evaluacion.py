"""Junta las puntuaciones de los evaluadores ciegos con las claves y resume.

    uv run python agregar_evaluacion.py salida/

Lee salida/claves.json, salida/resultados.json y salida/puntuaciones_*.json
(un fichero por lote y evaluador: lista de {n, r, fid, cit, cob, con}).
"""

import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

CRITERIOS = ("fid", "cit", "cob", "con")  # fidelidad, citas, cobertura, contención
AUSENTES = {12, 13, 14}  # preguntas sobre autores que no están en la wiki


def main(salida: Path):
    claves = json.loads((salida / "claves.json").read_text())
    resumen = json.loads((salida / "resultados.json").read_text())["resumen"]

    # notas[juez][(n, config)] = {criterio: valor}
    notas: dict[str, dict] = defaultdict(dict)
    for f in sorted(salida.glob("puntuaciones_*.json")):
        juez = f.stem.split("_")[-1]
        for p in json.loads(f.read_text()):
            config = claves[str(p["n"])][p["r"]]
            notas[juez][(p["n"], config)] = {c: p[c] for c in CRITERIOS}

    jueces = sorted(notas)
    comunes = set.intersection(*(set(notas[j]) for j in jueces))
    print(f"Evaluadores: {jueces}; respuestas puntuadas por todos: {len(comunes)}")

    # Acuerdo entre evaluadores: coincidencia exacta por criterio.
    for a, b in combinations(jueces, 2):
        for c in CRITERIOS:
            iguales = sum(notas[a][k][c] == notas[b][k][c] for k in comunes)
            cerca = sum(abs(notas[a][k][c] - notas[b][k][c]) <= 1 for k in comunes)
            print(f"  acuerdo {a}-{b} {c}: exacto {iguales / len(comunes):.0%}, ±1 {cerca / len(comunes):.0%}")

    configs = sorted({k[1] for k in comunes})
    filas = []
    for config in configs:
        claves_c = [k for k in comunes if k[1] == config]
        media = {c: sum(notas[j][k][c] for j in jueces for k in claves_c) / len(jueces) for c in CRITERIOS}
        por_juez = {j: sum(notas[j][k][c] for k in claves_c for c in CRITERIOS) for j in jueces}
        ausentes = [k for k in claves_c if k[0] in AUSENTES]
        con_aus = sum(notas[j][k]["con"] for j in jueces for k in ausentes) / len(jueces)
        maximo = 2 * len(claves_c)
        filas.append((config, media, por_juez, con_aus, 2 * len(ausentes), maximo))

    filas.sort(key=lambda f: -sum(f[1].values()))
    print()
    print(f"{'configuración':48s} {'fid':>5} {'cit':>5} {'cob':>5} {'con':>5} {'total':>6}  por evaluador  con.ausentes  memoria  tok/s  s/resp")
    for config, media, por_juez, con_aus, max_aus, maximo in filas:
        r = resumen.get(config, {})
        print(
            f"{config:48s} "
            + " ".join(f"{media[c]:5.1f}" for c in CRITERIOS)
            + f" {sum(media.values()):6.1f}/{4 * maximo}  "
            + "/".join(str(v) for v in por_juez.values()).ljust(13)
            + f"  {con_aus:4.1f}/{max_aus}     "
            + f"{r.get('memoria_gb', '?')!s:>5} GB {r.get('tok_s', '?')!s:>6} {r.get('segundos_media', '?')!s:>6}"
        )

    # Orden de configuraciones según cada evaluador (estabilidad del ranking).
    for j in jueces:
        orden = sorted(configs, key=lambda c: -sum(notas[j][k][x] for k in comunes if k[1] == c for x in CRITERIOS))
        print(f"\nOrden según {j}: " + " > ".join(orden))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
