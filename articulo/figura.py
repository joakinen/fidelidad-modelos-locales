"""Figura 1: fidelidad frente a velocidad de generación.

    uv run --with matplotlib python figura.py
"""

import matplotlib.pyplot as plt

AZUL, NARANJA, AGUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"

# (etiqueta, tok/s, fidelidad media /28, familia, razonamiento, desplazamiento etiqueta)
PUNTOS = [
    ("gemma4 26B-a4b", 53.7, 26.0, AZUL, False, (6, 6)),
    ("gemma4 e4b", 70.0, 28.0, AZUL, False, (6, -2)),
    ("gemma4 12B", 25.2, 26.0, AZUL, False, (6, 5)),
    ("gemma4 12B + raz.", 24.7, 25.0, AZUL, True, (6, -9)),
    ("gemma4 e2b", 106.1, 25.5, AZUL, False, (-10, 7)),
    ("qwen3 14B", 23.5, 21.5, NARANJA, False, (6, 2)),
    ("qwen3.5 9B", 37.7, 16.0, NARANJA, False, (7, 0)),
    ("qwen3.5 9B + raz.", 37.2, 18.0, NARANJA, True, (6, 3)),
    ("qwen3 14B + raz.", 23.4, 16.0, NARANJA, True, (6, -10)),
    ("gpt-oss 20B", 61.6, 18.0, AGUA, True, (6, 2)),
    ("salamandra 7B", 46.0, 13.5, AGUA, False, (6, 2)),
]

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman"],
        "font.size": 8.5,
        "axes.edgecolor": TINTA_2,
        "axes.labelcolor": TINTA,
        "xtick.color": TINTA_2,
        "ytick.color": TINTA_2,
        "pdf.fonttype": 42,
    }
)

fig, ax = plt.subplots(figsize=(5.6, 3.3))
ax.grid(True, color=REJILLA, linewidth=0.6)
ax.set_axisbelow(True)
for lado in ("top", "right"):
    ax.spines[lado].set_visible(False)

for etiqueta, x, y, color, razona, (dx, dy) in PUNTOS:
    ax.scatter(
        x,
        y,
        s=46,
        facecolor="white" if razona else color,
        edgecolor=color,
        linewidth=1.8 if razona else 1.2,
        zorder=3,
    )
    ax.annotate(
        etiqueta,
        (x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=7.5,
        color=TINTA,
        ha="right" if dx < 0 else "left",
        va="center",
    )

ax.set_xlabel("Velocidad de generación (tokens/s, Mac mini M4 Pro)")
ax.set_ylabel("Fidelidad a los fragmentos (máx. 28)")
ax.set_xlim(15, 118)
ax.set_ylim(12, 29.5)

# Leyenda: familia (color) y razonamiento (relleno), sin depender solo del color.
leyenda = [
    plt.Line2D([], [], marker="o", ls="", markerfacecolor=AZUL, markeredgecolor=AZUL, label="gemma4"),
    plt.Line2D([], [], marker="o", ls="", markerfacecolor=NARANJA, markeredgecolor=NARANJA, label="qwen"),
    plt.Line2D([], [], marker="o", ls="", markerfacecolor=AGUA, markeredgecolor=AGUA, label="otros"),
    plt.Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=TINTA_2, label="con razonamiento"),
]
ax.legend(handles=leyenda, loc="lower right", frameon=False, fontsize=7.5, labelcolor=TINTA)

fig.tight_layout()
fig.savefig("figura1.pdf")
fig.savefig("figura1.png", dpi=200)
