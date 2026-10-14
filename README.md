# Fidelidad de modelos locales en RAG con citas

Código y datos del *preprint* **«Fidelidad a las fuentes de modelos locales
en RAG con citas: once configuraciones en un ordenador de 24 GB»**
([articulo/main.pdf](articulo/main.pdf)), de Joaquín Herrero Pintado
([Creative Codeworks](https://creativecodeworks.com)).

Once configuraciones de modelos locales (Ollama 0.40.4, Mac mini M4 Pro de
24 GB) responden 14 preguntas en español sobre una wiki temática. Todas
reciben los mismos fragmentos recuperados, y dos evaluadores ciegos puntúan
cada respuesta en fidelidad, citas, cobertura y contención (decir lo que los
fragmentos no cubren sin rellenarlo con conocimiento propio).

## Resultados

| Configuración | Total /112 | Fidelidad /28 | bits/peso | tok/s |
|---|---|---|---|---|
| gemma4 26B-a4b (MoE) | 110,0 | 26,0 | 5,57 | 53,7 |
| gemma4 e4b | 109,5 | 28,0 | 5,83 | 70,0 |
| gemma4 12B | 108,5 | 26,0 | 4,95 | 25,2 |
| gemma4 12B + razonamiento | 107,0 | 25,0 | 4,95 | 24,7 |
| gemma4 e2b | 101,0 | 25,5 | 6,00 | 106,1 |
| qwen3 14B | 94,5 | 21,5 | 5,02 | 23,5 |
| qwen3.5 9B | 90,0 | 16,0 | 5,46 | 37,7 |
| qwen3.5 9B + razonamiento | 89,5 | 18,0 | 5,46 | 37,2 |
| qwen3 14B + razonamiento | 87,0 | 16,0 | 5,02 | 23,4 |
| gpt-oss 20B (medium) | 86,5 | 18,0 | 4,44 | 61,6 |
| salamandra 7B | 43,0 | 13,5 | 4,99 | 46,0 |

Todos los ficheros están etiquetados como `Q4_K_M`, pero la precisión media
medida va de 4,44 a 6,00 bits por peso. Para gemma4 e2b y e4b, Ollama activa
decodificación especulativa. Las limitaciones del estudio se detallan en el
artículo.

## Contenido

| Ruta | Qué es |
|---|---|
| `indexar.py` | Trocea las páginas (`.txt` de DokuWiki) y calcula embeddings con bge-m3 |
| `servicio.py`, `firma.py`, `config.py` | Recuperación y montaje del prompt; servicio HTTP con firma HMAC |
| `comparar_modelos.py` | Pasa las mismas preguntas y fragmentos a cada configuración y genera lotes ciegos |
| `agregar_evaluacion.py` | Junta las puntuaciones con las claves y calcula el acuerdo entre evaluadores |
| `evaluacion/2026-10-14/` | Claves de etiquetado, puntuaciones (0-2 por criterio) de los cuatro evaluadores y métricas |
| `articulo/` | Fuente LaTeX, figura y PDF del artículo |

## Reproducir

Requisitos: [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com)
con `bge-m3` y los modelos que quieras comparar, y un directorio de páginas
`.txt` de DokuWiki.

```sh
uv sync
DIR_PAGINAS=/ruta/a/data/pages uv run python indexar.py
cp preguntas.ejemplo.json preguntas.json   # y escribir las preguntas propias
NOMBRE_CORPUS="Mi wiki" TEMA_CORPUS="historia" \
  uv run python comparar_modelos.py salida/ gemma4:e4b-it-q4_K_M gemma4:12b qwen3:14B@si
# puntuar salida/ciego_*.json (evaluadores humanos o automáticos) en
# salida/puntuaciones_<lote>_<evaluador>.json: [{n, r, fid, cit, cob, con}, ...]
uv run python agregar_evaluacion.py salida/
```

`modelo@si` activa el razonamiento; `modelo@low|medium|high` fija el nivel
en gpt-oss.

**Qué no se incluye.** El corpus, las preguntas y los textos completos de
las respuestas identifican la wiki y contienen páginas de acceso
restringido, así que no se publican; en el artículo y en el código aparecen
como marcadores entre corchetes. Las puntuaciones van sin las frases que los
evaluadores señalaron como no respaldadas, por el mismo motivo.

## Licencia

MIT (ver [LICENSE](LICENSE)). La plantilla `articulo/arxiv.sty` procede de
[kourgeorge/arxiv-style](https://github.com/kourgeorge/arxiv-style) (MIT).
