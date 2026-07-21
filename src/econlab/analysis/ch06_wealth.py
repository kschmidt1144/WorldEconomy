"""Chapter 5 — Wealth & people: who owns what, and what labor keeps.

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


# the asset classes that make up household wealth, grouped for a clean stack
COMPOSITION = {
    "Equities & funds": ["corporate_equities_and_mutual_fund_shares"],
    "Private business": ["unincorporated_businesses"],
    "Pensions": ["db_pension_entitlements", "dc_pension_entitlements"],
    "Real estate": ["real_estate"],
    "Durables & other": ["consumer_durables", "other_assets"],
}
WEALTH_GROUPS = {"bottom50": "Bottom 50%", "next40": "50–90%",
                 "next9": "90–99%", "remainingtop1": "99–99.9%", "toppt1": "Top 0.1%"}


def wealth_composition(year: int = 2025) -> pd.DataFrame:
    """% of each wealth group's GROSS assets held in each asset class (DFA).

    Columns = wealth groups (poor→rich); rows = asset classes. The engine of
    the wealth gap: what the poor own (a mortgaged house) vs the rich (equity).
    """
    with connect() as con:
        raw = con.execute(
            "SELECT split_part(series_id,'.',2) asset, split_part(series_id,'.',3) grp, "
            f"avg(value) v FROM obs WHERE series_id LIKE 'dfa/nw.%' AND year={year} "
            "GROUP BY 1,2"
        ).df()
    out = {}
    for slug, label in WEALTH_GROUPS.items():
        g = raw[raw.grp == slug].set_index("asset")["v"]
        assets = g.get("assets", np.nan)
        col = {name: g.reindex(cls).sum() / assets * 100 for name, cls in COMPOSITION.items()}
        out[label] = pd.Series(col)
    return pd.DataFrame(out)[list(WEALTH_GROUPS.values())]


def billionaire_anatomy() -> dict:
    """Slice the 3,385-row Forbes snapshot four ways."""
    with connect() as con:
        b = con.execute(
            "SELECT rank, name, worth_usd/1e9 AS worth_bn, country, source FROM billionaires"
        ).df()
        gdp = con.execute(
            "SELECT e.name country, o.value/1e9 AS gdp_bn FROM obs o JOIN entities e "
            "USING(entity) WHERE o.series_id='imf/NGDPD' AND o.year=2024"
        ).df()
    by_country = b.groupby("country").agg(n=("name", "size"),
                                          wealth_bn=("worth_bn", "sum")).sort_values("n", ascending=False)
    by_industry = b.groupby("source").agg(n=("name", "size"),
                                          wealth_bn=("worth_bn", "sum")).sort_values("wealth_bn", ascending=False)
    vs_gdp = by_country.merge(gdp, left_index=True, right_on="country").set_index("country")
    vs_gdp["pct_gdp"] = 100 * vs_gdp.wealth_bn / vs_gdp.gdp_bn
    vs_gdp = vs_gdp[vs_gdp.n >= 10].sort_values("pct_gdp", ascending=False)
    return {"raw": b, "by_country": by_country, "by_industry": by_industry, "vs_gdp": vs_gdp}


def poverty_series() -> pd.DataFrame:
    """Extreme-poverty headcount (% at $3.00/day, 2021 PPP) for the world + regions."""
    ents = {"WLD": "World", "SSF": "Sub-Saharan Africa", "SAS": "South Asia",
            "EAS": "East Asia & Pacific", "LCN": "Latin America"}
    with connect() as con:
        df = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='wdi/SI.POV.DDAY' "
            f"AND entity IN ({','.join('?' * len(ents))}) ORDER BY year",
            list(ents),
        ).df()
    return df.pivot(index="year", columns="entity", values="value").rename(columns=ents)


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
    save(fig, "06_top1_ucurve")


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
    save(fig, "06_global_distribution")


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
    save(fig, "06_dfa_squeeze")


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
    save(fig, "06_labor_share")


def fig_wealth_composition() -> None:
    """The engine of the wealth gap: what each group's assets are made of."""
    import matplotlib.pyplot as plt

    comp = wealth_composition()
    print("[ch05] composition top0.1% equities %:", round(comp.loc["Equities & funds", "Top 0.1%"], 1))
    print("[ch05] composition bottom50 real-estate %:", round(comp.loc["Real estate", "Bottom 50%"], 1))

    order = ["Equities & funds", "Private business", "Pensions", "Real estate", "Durables & other"]
    colors = [PALETTE[0], PALETTE[3], PALETTE[2], PALETTE[1], PALETTE[7]]
    fig, ax = new_fig(
        "The engine of the wealth gap: what each group owns",
        subtitle="Composition of gross household assets by wealth percentile, 2025 (Fed DFA) — "
        "the poor own a mortgaged house, the rich own equity.",
        ylabel="% of the group's gross assets",
    )
    bottom = np.zeros(comp.shape[1])
    x = np.arange(comp.shape[1])
    for name, c in zip(order, colors):
        ax.bar(x, comp.loc[name], bottom=bottom, color=c, label=name, width=0.72)
        bottom += comp.loc[name].values
    ax.set_xticks(x, comp.columns)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False)
    ax.annotate("52% of the top 0.1%'s\nassets are equities", xy=(4, 26), xytext=(2.55, 84),
                fontsize=9, color="#24292f", ha="center",
                arrowprops=dict(arrowstyle="->", color="#57606a"))
    ax.text(0, 60, "the bottom\nhalf's wealth\nis mostly\na house", fontsize=8.5,
            color="white", ha="center", va="center", fontweight="bold")
    source_note(ax, "Source: computed from Fed Distributional Financial Accounts, gross assets by wealth group (econlab warehouse)")
    save(fig, "06_wealth_composition")


def fig_billionaires() -> None:
    """Four cuts of the Forbes real-time snapshot."""
    import matplotlib.pyplot as plt

    a = billionaire_anatomy()
    n_total = len(a["raw"])
    print(f"[ch05] billionaires n={n_total}, US share of count:",
          round(100 * a["by_country"].loc["United States", "n"] / n_total, 1))

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle(f"Anatomy of {n_total:,} billionaires (Forbes real-time snapshot)",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # (a) by country — count
    bc = a["by_country"].head(10)[::-1]
    axes[0, 0].barh(bc.index, bc.n, color=PALETTE[0])
    axes[0, 0].set_title("Where they live (count)", fontsize=10, loc="left")

    # (b) by industry — count (sort by n to surface real industry buckets, not one-off company labels)
    bi = a["by_industry"].sort_values("n").tail(10)
    axes[0, 1].barh(bi.index, bi.n, color=PALETTE[3])
    axes[0, 1].set_title("Top source-of-wealth categories (count)", fontsize=10, loc="left")

    # (c) rank power-law, log-log
    r = a["raw"].sort_values("rank")
    axes[1, 0].loglog(r["rank"], r["worth_bn"], ".", ms=3, color=PALETTE[1], alpha=0.6)
    axes[1, 0].set_title("The power law: rank vs net worth (log-log)", fontsize=10, loc="left")
    axes[1, 0].set_xlabel("rank")
    axes[1, 0].set_ylabel("net worth ($B)")

    # (d) wealth as % of home GDP
    vg = a["vs_gdp"].head(10)[::-1]
    axes[1, 1].barh(vg.index, vg.pct_gdp, color=PALETTE[4])
    axes[1, 1].set_title("Billionaire wealth as % of home-country GDP", fontsize=10, loc="left")
    axes[1, 1].set_xlabel("% of GDP")

    for ax in axes.flat:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.2)
    fig.text(0.01, -0.01, "Source: Forbes real-time snapshot × IMF GDP (econlab warehouse). "
             "'Source' field is Forbes' own industry/company label; ≥10-billionaire countries only in panel (d).",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "06_billionaires")


def fig_poverty() -> None:
    pv = poverty_series()
    fig, ax = new_fig(
        "The other tail: extreme poverty, 1981 → today",
        subtitle="Share living under $3.00/day (2021 PPP), World Bank. The counterweight to concentration at the top — "
        "the fastest mass exit from poverty in history, led by East Asia.",
        ylabel="% of population under $3.00/day",
    )
    order = ["World", "Sub-Saharan Africa", "South Asia", "East Asia & Pacific", "Latin America"]
    for i, c in enumerate(order):
        if c in pv.columns:
            s = pv[c].dropna()
            ax.plot(s.index, s, lw=2.2 if c == "World" else 1.6,
                    color=PALETTE[i], label=c, zorder=3 if c == "World" else 2)
    ax.legend(fontsize=9)
    ax.set_ylim(0, None)
    source_note(ax, "Source: computed from World Bank WDI poverty headcount (econlab warehouse)")
    save(fig, "06_poverty")


# Forbes World's Billionaires, annual aggregates (count, combined net worth $T) —
# curated from Forbes/Wikipedia (Forbes.com is a JS SPA, not connectorizable); the
# warehouse `billionaires` source holds the current cut, this is the historical arc.
BILLIONAIRE_HISTORY = [
    (2000, 322, 0.9), (2005, 691, 2.2), (2010, 1011, 3.6), (2015, 1826, 7.1),
    (2020, 2095, 8.0), (2024, 2781, 14.2), (2025, 3028, 16.1), (2026, 3428, 20.1),
]


def billionaire_ascent() -> pd.DataFrame:
    df = pd.DataFrame(BILLIONAIRE_HISTORY, columns=["year", "count", "wealth_t"])
    with connect() as con:
        gdp = con.execute("SELECT year, sum(value)/1e12 wgdp FROM obs o JOIN entities e USING(entity) "
                          "WHERE series_id='imf/NGDPD' AND e.kind='country' GROUP BY year").df()
    df = df.merge(gdp, on="year", how="left")
    df["pct_gdp"] = 100 * df["wealth_t"] / df["wgdp"]
    return df


def fig_billionaire_ascent() -> None:
    """Turn the single Forbes snapshot into a time series: billionaire wealth vs world GDP."""
    import matplotlib.pyplot as plt

    d = billionaire_ascent()
    print(f"[ch06] billionaires: {d.iloc[0]['count']:.0f} worth ${d.iloc[0]['wealth_t']:.1f}T ({d.iloc[0]['pct_gdp']:.0f}% of world GDP) "
          f"→ {d.iloc[-1]['count']:.0f} worth ${d.iloc[-1]['wealth_t']:.0f}T ({d.iloc[-1]['pct_gdp']:.0f}%)")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle("The billionaire ascent: combined wealth up ~22× since 2000, from ~2% to ~16% of world GDP",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.4)

    ax1.bar(d.year, d.wealth_t, width=2.6, color="#9a6700")
    for _, r in d.iterrows():
        ax1.text(r.year, r.wealth_t + 0.4, f"${r.wealth_t:.0f}T", ha="center", fontsize=7.6)
    axc = ax1.twinx()
    axc.plot(d.year, d["count"], color="#1f6feb", lw=2, marker="o", ms=4)
    axc.set_ylabel("number of billionaires", color="#1f6feb", fontsize=9)
    axc.tick_params(axis="y", colors="#1f6feb")
    axc.set_ylim(0, 3800)
    ax1.set_title("Combined net worth ($T, bars) and count (line)", fontsize=9.3, loc="left")
    ax1.set_ylabel("combined net worth, $ trillion")
    ax1.set_ylim(0, 22)

    ax2.plot(d.year, d.pct_gdp, color="#b42318", lw=2.6, marker="o", ms=4)
    ax2.fill_between(d.year, d.pct_gdp, 0, color="#b42318", alpha=0.08)
    for _, r in d.iterrows():
        ax2.text(r.year, r.pct_gdp + 0.4, f"{r.pct_gdp:.0f}%", ha="center", fontsize=7.8)
    ax2.set_title("Billionaire wealth as a share of world GDP", fontsize=9.3, loc="left")
    ax2.set_ylabel("% of world GDP")
    ax2.set_ylim(0, 18)

    source_note(ax1, "Forbes World's Billionaires annual aggregates (count & combined net worth), 2000–2026; world GDP from IMF "
                     "(econlab warehouse). 2000 figures approximate. Combined billionaire wealth grew from ~2% of world output to ~16% in a quarter-century.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "06_billionaire_ascent")


def main() -> None:
    fig_top1_ucurve()
    fig_global_distribution()
    fig_dfa_squeeze()
    fig_wealth_composition()
    fig_billionaires()
    fig_billionaire_ascent()
    fig_poverty()
    fig_labor_share()


if __name__ == "__main__":
    main()
