"""Draw the README's benchmark charts from results.json.

    python docs/benchmarks/make_charts.py      # needs matplotlib
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).parent
OUT = HERE.parent / "images"
DATA = json.loads((HERE / "results.json").read_text(encoding="utf-8"))

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#2a78d6"
CONTEXT = ["#898781", "#c3c2b7"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 12,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": MUTED,
})


def chart(title, subtitle, source):
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    fig.text(0.075, 0.95, title, fontsize=18, fontweight="bold", va="top")
    fig.text(0.075, 0.89, subtitle, fontsize=12, color=INK_2, va="top")
    fig.text(0.075, 0.03, source, fontsize=9.5, color=MUTED, va="bottom")
    fig.subplots_adjust(left=0.075, right=0.985, top=0.75, bottom=0.17)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(axis="both", length=0, pad=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def bars(ax, positions, series, colors, fmt, top, emphasis=None):
    n = len(series)
    slot = 0.78 / n
    for i, (label, values) in enumerate(series):
        xs = [p + (i - (n - 1) / 2) * slot for p in positions]
        ax.bar(xs, values, slot - 0.05, color=colors[i], edgecolor=colors[i], linewidth=3,
               joinstyle="round", label=label, zorder=3)
        strong = emphasis is None or i == emphasis
        for x, v in zip(xs, values):
            ax.text(x, v + top * 0.018, fmt(v), ha="center", va="bottom", zorder=4,
                    fontsize=10.5 if strong else 9.5,
                    fontweight="bold" if strong and emphasis is not None else "normal",
                    color=INK if strong else MUTED)
    ax.set_ylim(0, top)
    ax.set_xlim(positions[0] - 0.55, positions[-1] + 0.55)


def legend(ax, ncol):
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.03), ncol=ncol, frameon=False, fontsize=11.5,
              handlelength=0.9, handleheight=0.9, columnspacing=1.8, borderaxespad=0)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, facecolor=SURFACE)
    plt.close(fig)
    print(OUT / name)


pct = lambda v: f"{v * 100:.0f}%"
percent_axis = FuncFormatter(lambda v, _: f"{v * 100:.0f}%")
gpu = DATA["evaluated_on"]

det = DATA["detection"]
sets = list(det["datasets"])
models = list(det["models"].values())
fig, ax = chart(
    "Text-line detection",
    "F1 score: how well the detected lines match the labelled ones (higher is better)",
    f"Validation sets: KhmerST, HierText and synthetic pages. Evaluated on an {gpu}.",
)
bars(ax, list(range(len(sets))), [(m["label"], [m[s]["hmean"] for s in sets]) for m in models],
     [ACCENT, *CONTEXT], pct, 1.1, emphasis=0)
ax.set_xticks(range(len(sets)), [det["datasets"][s] for s in sets], fontsize=12.5)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.yaxis.set_major_formatter(percent_axis)
legend(ax, 3)
save(fig, "bench-detection.png")

rec = DATA["recognition"]
scripts = list(rec["scripts"])
v4 = rec["models"]["v4"]["val"]
positions = [0, 1, 2, 3, 4.35]
fig, ax = chart(
    "Text-line recognition",
    "Share of lines read exactly right, by script (higher is better)",
    f"3,878 real validation lines. Evaluated on an {gpu}.",
)
bars(ax, positions, [(m["label"], [m["val"][s]["acc"] for s in scripts]) for m in rec["models"].values()],
     [ACCENT, CONTEXT[0]], pct, 1.1, emphasis=0)
ax.set_xticks(positions, [f"{rec['scripts'][s]}\n{v4[s]['n']:,} lines" for s in scripts], fontsize=12)
ax.get_xticklabels()[-1].set_fontweight("bold")
ax.get_xticklabels()[-1].set_color(INK)
ax.axvline(3.68, color=GRID, linewidth=1, zorder=1)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.yaxis.set_major_formatter(percent_axis)
legend(ax, 2)
save(fig, "bench-recognition.png")

speed = DATA["speed"]
images = list(speed["images"])
backends = list(speed["backends"].values())
top = max(b[i] for b in backends for i in images) * 1.14
fig, ax = chart(
    "Speed by backend",
    "Seconds to read one image, once the models are loaded (lower is better)",
    f"{speed['machine']}.",
)
bars(ax, list(range(len(images))), [(b["label"], [b[i] for i in images]) for b in backends],
     [ACCENT, *CONTEXT], lambda v: f"{v:.1f} s" if v >= 1 else f"{v:.2f} s", top, emphasis=0)
ax.set_xticks(range(len(images)), [speed["images"][i] for i in images], fontsize=12.5)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} s"))
legend(ax, 3)
save(fig, "bench-speed.png")
