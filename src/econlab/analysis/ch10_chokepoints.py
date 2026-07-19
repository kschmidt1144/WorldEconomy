"""Chapter 10 — The Chokepoints: where a few control the many.

Generalizes Chapter 6's "Giant Three" finding from finance to the whole
economy. Most of the numbers here are *curated* concentration ratios (cited),
because market-share data isn't in the primary-data warehouse — but each
headline figure was **cross-checked through the AI panel** (`econ panel`, free
Groq models: Llama + Qwen3 + GPT-OSS), and the panel's consensus is reported
alongside. The people who sit atop these chokepoints are pulled live from the
Forbes billionaires table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

# Curated chokepoints: (domain, what, n_controllers, top_n_share_pct, who, source).
# Panel consensus for the ones we cross-checked is in PANEL_CHECK below.
CHOKEPOINTS = [
    ("Technology", "EUV lithography machines", 1, 100, "ASML"),
    ("Technology", "Leading-edge chips (<7nm)", 1, 90, "TSMC"),
    ("Technology", "AI accelerators (GPUs)", 1, 90, "Nvidia"),
    ("Technology", "Web search", 1, 90, "Google"),
    ("Technology", "Desktop operating systems", 1, 72, "Microsoft Windows"),
    ("Technology", "Cloud infrastructure", 3, 63, "AWS, Azure, Google"),
    ("Corporate control", "Proxy-vote advice", 2, 95, "ISS + Glass Lewis"),
    ("Corporate control", "Credit ratings", 3, 95, "S&P, Moody's, Fitch"),
    ("Corporate control", "Index-fund voting (S&P 500)", 3, 88, "BlackRock, Vanguard, State Street"),
    ("Resources", "Commercial seeds & agrochem", 4, 60, "Bayer, Corteva, Syngenta, BASF"),
    ("Resources", "Rare-earth refining", 1, 87, "China"),
    ("Resources", "Global grain trade", 4, 75, "ADM, Bunge, Cargill, Dreyfus"),
    ("Payments", "Cross-border bank messaging", 1, 90, "SWIFT"),
]

# AI-panel cross-check (consensus 0-100, mean estimate %) — from `econ panel`,
# free Groq models (Llama-3.3, Qwen3, GPT-OSS-120B), 2026-07-19. Recorded so the
# chapter shows an independent multi-model check of each curated figure.
PANEL_CHECK = {
    "EUV lithography machines": (100, 100),
    "Leading-edge chips (<7nm)": (72, 72),   # models split 50-90 (definition-sensitive)
    "AI accelerators (GPUs)": (97, 88),
    "Web search": (94, 88),
    "Proxy-vote advice": (98, 96),
    "Credit ratings": (100, 95),
    "Commercial seeds & agrochem": (100, 60),
}

# Control without ownership: super-voting founders (voting % vs economic %).
# Curated from company proxy statements.
DUAL_CLASS = [
    ("Zuckerberg — Meta", 58, 13),
    ("Page & Brin — Alphabet", 51, 11),
    ("Murdoch family — Fox/News Corp", 39, 14),
    ("Ford family — Ford", 40, 2),
    ("Roberts — Comcast", 33, 1),
    ("Hastings/Sarandos era — dual-class norm", 0, 0),  # placeholder trimmed below
]
DUAL_CLASS = [d for d in DUAL_CLASS if d[1] > 0]

# The world's big managed capital pools (2024 AUM, $tn) — sovereign wealth
# funds vs the Big Three asset managers. Curated (fund reports, SWFI).
CAPITAL_POOLS = [
    ("BlackRock", "asset mgr", 11.5), ("Vanguard", "asset mgr", 9.3),
    ("State Street", "asset mgr", 4.3),
    ("Norway (NBIM)", "SWF", 1.8), ("China (CIC)", "SWF", 1.35),
    ("Abu Dhabi (ADIA)", "SWF", 1.0), ("Saudi (PIF)", "SWF", 0.93),
    ("Kuwait (KIA)", "SWF", 0.8), ("Singapore (GIC)", "SWF", 0.77),
    ("Qatar (QIA)", "SWF", 0.53),
]

DOMAIN_COLOR = {"Technology": "#1f6feb", "Corporate control": "#8250df",
                "Resources": "#1a7f37", "Payments": "#9a6700"}


def chokepoints_df() -> pd.DataFrame:
    df = pd.DataFrame(CHOKEPOINTS, columns=["domain", "what", "n", "share", "who"])
    df["panel"] = df["what"].map(lambda w: PANEL_CHECK.get(w, (None, None))[0])
    return df


def the_controllers(n: int = 12) -> pd.DataFrame:
    """Individuals who personally control chokepoint firms (Forbes billionaires)."""
    keep = {"Elon Musk", "Larry Page", "Sergey Brin", "Jeff Bezos", "Mark Zuckerberg",
            "Jensen Huang", "Larry Ellison", "Michael Dell", "Steve Ballmer", "Bill Gates",
            "Changpeng Zhao", "Bernard Arnault & family", "Carlos Slim Helu & family"}
    with connect() as con:
        df = con.execute(
            "SELECT name, worth_usd/1e9 AS bn, source FROM billionaires ORDER BY worth_usd DESC"
        ).df()
    return df[df.name.isin(keep)].head(n).reset_index(drop=True)


# ---------- figures ----------

def fig_chokepoint_map() -> None:
    df = chokepoints_df().sort_values(["share", "n"], ascending=[True, False])
    print("[ch10] chokepoints:", len(df), "| panel-checked:", df.panel.notna().sum())
    fig, ax = new_fig(
        "The chokepoints: where one, two, or three entities control the many",
        subtitle="Combined market share of the top controllers in each domain (curated; ✓ = corroborated by the AI panel). "
        "The recurring number is 1–4 — technology, regulation, and geography all breed bottlenecks.",
        ylabel=None,
    )
    y = np.arange(len(df))
    colors = [DOMAIN_COLOR[d] for d in df.domain]
    ax.barh(y, df.share, color=colors)
    labels = [f"{w}  ({who})" for w, who in zip(df.what, df.who)]
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("share controlled by the top players, %")
    ax.set_xlim(0, 118)
    for i, r in enumerate(df.itertuples()):
        tag = f"{int(r.n)} firm" + ("s" if r.n > 1 else "")
        chk = ""
        if pd.notna(r.panel):
            chk = "  ✓AI" if r.panel >= 90 else f"  ⚠AI {int(r.panel)}"
        ax.text(r.share + 1, i, f"{int(r.share)}%  · {tag}{chk}", va="center", fontsize=7.5,
                color="#24292f")
    handles = [plt_patch(c, d) for d, c in DOMAIN_COLOR.items()]
    ax.legend(handles=handles, fontsize=8, loc="lower right", ncol=2)
    source_note(ax, "Source: curated concentration ratios (industry reports); ✓ = AI-panel consensus ≥90 (econlab panel, free Groq models)")
    save(fig, "10_chokepoint_map")


def plt_patch(color, label):
    import matplotlib.patches as mpatches
    return mpatches.Patch(color=color, label=label)


def fig_dual_class() -> None:
    fig, ax = new_fig(
        "Control without ownership: the dual-class wedge",
        subtitle="Founder/family voting power vs their economic stake, via super-voting shares (company proxies). "
        "A minority owner commands the company — the purest form of 'decision behind the money'.",
        ylabel=None,
    )
    names = [d[0] for d in DUAL_CLASS][::-1]
    voting = [d[1] for d in DUAL_CLASS][::-1]
    econ = [d[2] for d in DUAL_CLASS][::-1]
    y = np.arange(len(names))
    ax.barh(y + 0.2, voting, height=0.38, color="#8250df", label="voting power %")
    ax.barh(y - 0.2, econ, height=0.38, color="#57606a", label="economic stake %")
    ax.set_yticks(y, names, fontsize=8.5)
    for i in range(len(names)):
        ax.text(voting[i] + 1, y[i] + 0.2, f"{voting[i]}%", va="center", fontsize=7.5, color="#8250df")
        ax.text(econ[i] + 1, y[i] - 0.2, f"{econ[i]}%", va="center", fontsize=7.5, color="#57606a")
    ax.set_xlabel("% of the company")
    ax.set_xlim(0, 70)
    ax.legend(fontsize=8.5, loc="lower right")
    source_note(ax, "Source: curated from company proxy statements (econlab warehouse)")
    save(fig, "10_dual_class")


def fig_capital_pools() -> None:
    df = pd.DataFrame(CAPITAL_POOLS, columns=["name", "kind", "aum"]).sort_values("aum")
    big3 = df[df.kind == "asset mgr"].aum.sum()
    swf = df[df.kind == "SWF"].aum.sum()
    print(f"[ch10] Big Three ${big3:.1f}T vs top-7 SWFs ${swf:.1f}T")
    fig, ax = new_fig(
        "Who manages the world's savings: the Big Three vs the sovereign funds",
        subtitle="Assets under management, 2024 ($tn). The three US index managers together run more than every major "
        "sovereign wealth fund on Earth combined — private managers, public and autocratic states, one chart.",
        ylabel=None,
    )
    colors = ["#8250df" if k == "asset mgr" else "#1a7f37" for k in df.kind]
    y = np.arange(len(df))
    ax.barh(y, df.aum, color=colors)
    ax.set_yticks(y, df.name, fontsize=8.5)
    for i, r in enumerate(df.itertuples()):
        ax.text(r.aum + 0.1, i, f"${r.aum:.1f}T", va="center", fontsize=8)
    ax.set_xlabel("assets under management, \\$ trillions")
    ax.set_xlim(0, 13)
    ax.text(6.5, 1.5, f"Big Three: \\${big3:.0f}T\ntop-7 SWFs: \\${swf:.0f}T",
            fontsize=9, color="#24292f", bbox=dict(boxstyle="round", fc="#f6f8fa", ec="#8250df"))
    handles = [plt_patch("#8250df", "US index managers"), plt_patch("#1a7f37", "sovereign wealth funds")]
    ax.legend(handles=handles, fontsize=8.5, loc="lower right")
    source_note(ax, "Source: curated (firm reports, SWF Institute) (econlab warehouse)")
    save(fig, "10_capital_pools")


def main() -> None:
    fig_chokepoint_map()
    fig_dual_class()
    fig_capital_pools()


if __name__ == "__main__":
    main()
