"""Chapter 4 — Wealth & people: who owns what, and what labor keeps.

WID distributions (incl. the global distribution back to 1820), Fed DFA
percentile wealth, PWT labor shares.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

DECILES = ["p0p10", "p10p20", "p20p30", "p30p40", "p40p50",
           "p50p60", "p60p70", "p70p80", "p80p90", "p90p100"]


# ---------- data ----------

def top1_series(entity: str) -> pd.Series:
    with connect() as con:
        return con.execute(
            "SELECT year, value FROM obs WHERE series_id='wid/sptincj992.p99p100' "
            "AND entity=? ORDER BY year", [entity]
        ).df().set_index("year")["value"]


def global_shares() -> pd.DataFrame:
    """Global (WLD) pre-tax income shares: top 10% and bottom 50%, 1820->2023."""
    with connect() as con:
        df = con.execute(
            "SELECT year, series_id, value FROM obs WHERE entity='WLD' AND series_id IN "
            "('wid/sptincj992.p90p100','wid/sptincj992.p0p50') ORDER BY year"
        ).df().pivot(index="year", columns="series_id", values="value")
    return df.rename(columns={
        "wid/sptincj992.p90p100": "top10", "wid/sptincj992.p0p50": "bottom50"
    })


def global_elephant(y0: int = 1995, y1: int = 2023) -> pd.Series:
    """Total real income growth by global decile (+ top 1%), y0->y1.

    decile average income ∝ share × (avg income per adult); anninc is real
    constant-currency, so ratios are real growth.
    """
    with connect() as con:
        sh = con.execute(
            "SELECT year, series_id, value FROM obs WHERE entity='WLD' "
            "AND series_id LIKE 'wid/sptincj992.%'"
        ).df().pivot(index="year", columns="series_id", values="value")
        ann = con.execute(
            "SELECT year, value FROM obs WHERE entity='WLD' AND series_id='wid/anninci992.p0p100'"
        ).df().set_index("year")["value"]
    out = {}
    for grp in DECILES + ["p99p100"]:
        col = f"wid/sptincj992.{grp}"
        g = (sh.loc[y1, col] * ann[y1]) / (sh.loc[y0, col] * ann[y0]) - 1
        out[grp] = 100 * g
    return pd.Series(out)


def dfa_group_shares() -> pd.DataFrame:
    groups = {"toppt1": "Top 0.1%", "remainingtop1": "99-99.9%",
              "next9": "90-99%", "next40": "50-90%", "bottom50": "Bottom 50%"}
    with connect() as con:
        frames = {}
        for slug, label in groups.items():
            frames[label] = con.execute(
                f"SELECT year, avg(value) v FROM obs WHERE "
                f"series_id='dfa/nwshare.net_worth.{slug}' GROUP BY 1 ORDER BY 1"
            ).df().set_index("year")["v"]
    return pd.DataFrame(frames)


def labor_shares() -> pd.DataFrame:
    with connect() as con:
        df = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='pwt/labsh' "
            "AND entity IN ('USA','DEU','JPN','GBR','CHN') ORDER BY year"
        ).df()
    return df.pivot(index="year", columns="entity", values="value")


# ---------- figures ----------

def fig_top1_ucurve() -> None:
    us, fr = top1_series("USA"), top1_series("FRA")
    fig, ax = new_fig(
        "A century of the top 1% - two paths",
        subtitle="Pre-tax national income share of the top 1% (equal-split adults). The US round trip vs the European L-shape.",
        ylabel="share of national income, %",
    )
    ax.plot(us.loc[1900:].index, 100 * us.loc[1900:], lw=2, label="United States")
    ax.plot(fr.loc[1900:].index, 100 * fr.loc[1900:], lw=2, label="France")
    ax.legend()
    source_note(ax, "Source: computed from WID.world (econlab warehouse)")
    save(fig, "05_top1_ucurve")


def fig_global_distribution() -> None:
    import matplotlib.pyplot as plt

    gs = global_shares()
    el = global_elephant()
    print("[ch04] elephant 1995-2023 (% growth):", el.round(0).to_dict())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The global income distribution", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    ax1.plot(gs.index, 100 * gs.top10, lw=2, color=PALETTE[0], label="top 10% share")
    ax1.plot(gs.index, 100 * gs.bottom50, lw=2, color=PALETTE[1], label="bottom 50% share")
    ax1.set_title("Global shares, 1820-2023", fontsize=10, loc="left")
    ax1.set_ylabel("% of global income")
    ax1.legend(fontsize=9)

    x = np.arange(len(el) - 1)
    ax2.bar(x, el.iloc[:-1], color=PALETTE[0])
    ax2.bar([len(x)], el.iloc[-1], color=PALETTE[4])
    ax2.set_xticks(list(x) + [len(x)],
                   [d.replace("p", "-")[1:] for d in el.index[:-1]] + ["top 1%"],
                   rotation=45, fontsize=8)
    ax2.set_title(f"Real income growth by global decile, 1995-2023", fontsize=10, loc="left")
    ax2.set_ylabel("total real growth, %")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from WID.world global series (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "05_global_distribution")


def fig_dfa_squeeze() -> None:
    df = dfa_group_shares()
    fig, ax = new_fig(
        "US wealth shares since 1989: the squeezed middle",
        subtitle="Share of household net worth (Fed DFA, quarterly averaged to years). The gain of the top 0.1% mirrors the loss of the 50-90th percentile.",
        ylabel="% of household net worth",
    )
    for i, col in enumerate(df.columns):
        d0, d1 = df[col].dropna().iloc[0], df[col].dropna().iloc[-1]
        ax.plot(df.index, df[col], lw=2, color=PALETTE[i],
                label=f"{col} ({d0:.1f} -> {d1:.1f})")
    ax.legend(fontsize=9)
    source_note(ax, "Source: computed from Fed Distributional Financial Accounts (econlab warehouse)")
    save(fig, "05_dfa_squeeze")


def fig_labor_share() -> None:
    ls = labor_shares()
    fig, ax = new_fig(
        "Labor's slice of income, 1950-2023",
        subtitle="Compensation share of GDP (PWT). A slow, broad decline since ~1975 - a few points of GDP moved from paychecks to capital.",
        ylabel="labor share (fraction of GDP)",
    )
    names = {"USA": "United States", "DEU": "Germany", "JPN": "Japan",
             "GBR": "Britain", "CHN": "China"}
    for i, c in enumerate(["USA", "DEU", "JPN", "GBR", "CHN"]):
        ax.plot(ls.index, ls[c], lw=1.8, color=PALETTE[i], label=names[c])
    ax.legend(fontsize=9)
    source_note(ax, "Source: computed from Penn World Table 11.0 labsh (econlab warehouse)")
    save(fig, "05_labor_share")


def main() -> None:
    fig_top1_ucurve()
    fig_global_distribution()
    fig_dfa_squeeze()
    fig_labor_share()


if __name__ == "__main__":
    main()
