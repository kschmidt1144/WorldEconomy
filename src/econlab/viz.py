"""House figure style. Every report figure goes through save() so the report
directory only ever contains regenerable artifacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .config import FIGURES  # noqa: E402

plt.rcParams.update(
    {
        "figure.figsize": (10, 5.5),
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "legend.frameon": False,
    }
)

PALETTE = [
    "#1f6feb", "#d1242f", "#1a7f37", "#9a6700", "#8250df",
    "#cf222e", "#0969da", "#57606a",
]


def new_fig(title: str, subtitle: str | None = None, ylabel: str | None = None):
    fig, ax = plt.subplots()
    ax.set_title(title, loc="left", pad=26 if subtitle else 8)
    if subtitle:
        ax.text(
            0, 1.015, subtitle, transform=ax.transAxes,
            fontsize=9.5, color="#57606a", va="bottom",
        )
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_prop_cycle(color=PALETTE)
    return fig, ax


def source_note(ax, text: str) -> None:
    ax.figure.text(
        0.01, -0.02, text, fontsize=8, color="#57606a",
        ha="left", va="top", transform=ax.figure.transFigure,
    )


def save(fig, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / f"{name}.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"figure: {out.relative_to(out.parents[2])}")
    return out
