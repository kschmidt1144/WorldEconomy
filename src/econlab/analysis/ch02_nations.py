"""Chapter 2 — Nations & macro today: growth, inflation, debt, r-g.

IMF DataMapper panel (with projections to ~2031), JST long history, FRED for
the current US splice. Projection years are shaded in figures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

LAST_ACTUAL = 2025  # WEO Apr-2026 vintage: later years are projections


def _imf(con, ind: str) -> pd.DataFrame:
    return con.execute(
        f"SELECT entity, year, value FROM obs WHERE series_id='imf/{ind}'"
    ).df()


# ---------- data ----------

def inflation_regimes() -> pd.DataFrame:
    """Share of countries in high-inflation regimes per year."""
    with connect() as con:
        inf = _imf(con, "PCPIPCH")
    out = []
    for y, s in inf.groupby("year"):
        if len(s) < 100:
            continue
        out.append(
            {"year": y, "gt10": 100 * (s.value > 10).mean(),
             "gt40": 100 * (s.value > 40).mean(), "n": len(s)}
        )
    return pd.DataFrame(out).set_index("year")


def worst_inflation_episodes(n: int = 8) -> pd.DataFrame:
    with connect() as con:
        inf = _imf(con, "PCPIPCH")
    return inf.nlargest(n, "value").reset_index(drop=True)


def debt_distribution() -> pd.DataFrame:
    """Median + IQR of general-government debt/GDP, high-income vs rest."""
    with connect() as con:
        df = con.execute(
            """
            SELECT o.year,
                   CASE WHEN e.income_group = 'High income' THEN 'High income'
                        ELSE 'Emerging & developing' END AS grp,
                   quantile_cont(o.value, 0.5) AS med,
                   quantile_cont(o.value, 0.25) AS q25,
                   quantile_cont(o.value, 0.75) AS q75,
                   count(*) AS n
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id = 'imf/GG_DEBT_GDP' AND e.kind = 'country'
              AND e.income_group IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1
            """
        ).df()
    return df


def us_r_minus_g() -> pd.DataFrame:
    """US long-rate minus nominal GDP growth, 1872->present (JST + FRED splice)."""
    with connect() as con:
        jst = con.execute(
            "SELECT year, series_id, value FROM obs WHERE entity='USA' "
            "AND series_id IN ('jst/ltrate','jst/gdp')"
        ).df().pivot(index="year", columns="series_id", values="value")
        gdp = con.execute(
            "SELECT date, value FROM obs WHERE series_id='fred/GDP' ORDER BY date"
        ).df()
        dgs = con.execute(
            "SELECT year, avg(value) AS r FROM obs WHERE series_id='fred/DGS10' GROUP BY 1"
        ).df().set_index("year")["r"]

    jst["g"] = 100 * (jst["jst/gdp"] / jst["jst/gdp"].shift(1) - 1)
    hist = (jst["jst/ltrate"] - jst["g"]).dropna()

    gdp["year"] = pd.to_datetime(gdp["date"]).dt.year
    ann = gdp.groupby("year")["value"].mean()
    g_recent = 100 * (ann / ann.shift(1) - 1)
    recent = (dgs - g_recent).dropna()
    recent = recent[recent.index > hist.index.max()]

    out = pd.concat([hist, recent]).sort_index()
    return pd.DataFrame({"rg": out, "rg_5y": out.rolling(5, center=True).mean()})


def reserve_currency_shares() -> pd.DataFrame:
    """COFER reserve-currency shares (% of allocated reserves), 1995->."""
    with connect() as con:
        df = con.execute(
            "SELECT split_part(series_id,'.',2) AS cur, year, value FROM obs "
            "WHERE series_id LIKE 'cofer/reserve_share.%' ORDER BY year"
        ).df()
    return df.pivot(index="year", columns="cur", values="value")


def global_imbalances(year: int = 2024) -> pd.DataFrame:
    """Absolute current-account balance (USD bn) = BCA%GDP x nominal GDP."""
    with connect() as con:
        df = con.execute(
            "SELECT ca.entity, ca.value/100.0 * gd.value/1e9 AS ca_bn "
            "FROM obs ca JOIN obs gd ON ca.entity=gd.entity AND ca.year=gd.year "
            "JOIN entities e ON ca.entity=e.entity "
            "WHERE ca.series_id='imf/BCA_NGDPD' AND gd.series_id='imf/NGDPD' "
            f"AND ca.year={year} AND e.kind='country'"
        ).df()
    return df.set_index("entity")["ca_bn"].sort_values()


def convergence_ladder() -> pd.DataFrame:
    """GDP per capita as % of the US, 1900->2022 (Maddison), for a spread of economies."""
    codes = ["DEU", "JPN", "GBR", "KOR", "ARG", "CHN", "IND", "NGA"]
    with connect() as con:
        df = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='maddison/gdppc' "
            f"AND entity IN ({','.join(['?'] * (len(codes) + 1))}) AND year BETWEEN 1900 AND 2022",
            codes + ["USA"],
        ).df().pivot(index="year", columns="entity", values="value")
    us = df["USA"]
    return df[codes].div(us, axis=0).mul(100).dropna(how="all")


# ---------- figures ----------

def fig_growth_landscape() -> None:
    with connect() as con:
        pc = _imf(con, "PPPPC")
        gr = _imf(con, "NGDP_RPCH")
        pop = _imf(con, "LP")
        reg = con.execute(
            "SELECT entity, region FROM entities WHERE kind='country' AND region IS NOT NULL"
        ).df()
    pc25 = pc[pc.year == 2025].set_index("entity").value
    g = gr[gr.year.between(2023, 2025)].groupby("entity").value.mean()
    p25 = pop[pop.year == 2025].set_index("entity").value
    df = pd.DataFrame({"gdppc": pc25, "growth": g, "pop": p25}).join(
        reg.set_index("entity")
    ).dropna()

    fig, ax = new_fig(
        "The development landscape, 2023-25",
        subtitle="Each bubble a country; size = population. Growth is fastest in the poor-and-catching-up middle; rich-world growth clusters near 2%.",
        ylabel="real GDP growth 2023-25, %/yr",
    )
    for i, (region, sub) in enumerate(df.groupby("region")):
        ax.scatter(sub.gdppc, sub.growth, s=np.sqrt(sub["pop"] / 1e6) * 2.2,
                   alpha=0.65, label=region, color=PALETTE[i % len(PALETTE)])
    for code in ("CHN", "IND", "USA", "DEU", "NGA", "VNM"):
        if code in df.index:
            r = df.loc[code]
            ax.annotate(code, (r.gdppc, r.growth), fontsize=8, ha="center",
                        xytext=(0, 7), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("GDP per capita 2025, PPP$ (log)")
    ax.legend(fontsize=7.5, loc="upper right", ncol=2)
    source_note(ax, "Source: computed from IMF DataMapper (econlab warehouse)")
    save(fig, "02_growth_landscape")


def fig_inflation_regimes() -> None:
    reg = inflation_regimes()
    fig, ax = new_fig(
        "The taming of inflation - and the 2022 relapse",
        subtitle="Share of ~200 countries in high-inflation regimes. 1980: three-quarters above 10%. 2010: eight percent. Shaded: IMF projections.",
        ylabel="% of countries",
    )
    ax.plot(reg.index, reg.gt10, lw=2, label="inflation > 10%")
    ax.plot(reg.index, reg.gt40, lw=2, label="inflation > 40%")
    ax.axvspan(LAST_ACTUAL + 0.5, reg.index.max(), color="#57606a", alpha=0.08)
    ax.legend()
    source_note(ax, "Source: computed from IMF DataMapper PCPIPCH (econlab warehouse)")
    save(fig, "02_inflation_regimes")


def fig_debt_distribution() -> None:
    df = debt_distribution()
    fig, ax = new_fig(
        "Government debt: the post-2008 ratchet",
        subtitle="General-government debt/GDP, median with interquartile band. Early high-income years are thin samples. Shaded: IMF projections.",
        ylabel="% of GDP",
    )
    for i, (grp, sub) in enumerate(df.groupby("grp")):
        sub = sub[sub.n >= 8]
        ax.plot(sub.year, sub.med, lw=2, color=PALETTE[i], label=f"{grp} (median)")
        ax.fill_between(sub.year, sub.q25, sub.q75, color=PALETTE[i], alpha=0.15)
    ax.axvspan(LAST_ACTUAL + 0.5, df.year.max(), color="#57606a", alpha=0.08)
    ax.legend()
    source_note(ax, "Source: computed from IMF Global Debt Database / WEO (econlab warehouse)")
    save(fig, "02_debt_distribution")


def fig_r_minus_g() -> None:
    rg = us_r_minus_g()
    fig, ax = new_fig(
        "r - g in the United States, 1872-2026",
        subtitle="10-yr rate minus nominal GDP growth (5-yr centered mean). Negative = debt melts; the postwar melt and the Volcker inversion are regimes, not noise.",
        ylabel="percentage points",
    )
    ax.plot(rg.index, rg.rg, lw=0.7, alpha=0.35, color="#57606a")
    ax.plot(rg.index, rg.rg_5y, lw=2, color="#1f6feb")
    ax.axhline(0, color="#d1242f", lw=1)
    for a, b, label, ytxt in [(1946, 1980, "repression era\nr-g ≈ -2.7", -6.5),
                              (1981, 2000, "Volcker regime\nr-g ≈ +1.7", 5.2)]:
        ax.axvspan(a, b, alpha=0.07, color="#1a7f37" if ytxt < 0 else "#d1242f")
        ax.text((a + b) / 2, ytxt, label, ha="center", fontsize=8.5, color="#57606a")
    source_note(
        ax,
        "Source: computed from JST Macrohistory (1872-2020) spliced with FRED DGS10 & nominal GDP (econlab warehouse)",
    )
    save(fig, "02_r_minus_g")


def fig_reserve_currencies() -> None:
    rc = reserve_currency_shares()
    print("[ch02] USD reserve share 1999->2025:",
          round(rc.loc[1999, "USD"], 1), "->", round(rc.loc[2025, "USD"], 1),
          "| CNY 2025:", round(rc.loc[2025, "CNY"], 1))
    fig, ax = new_fig(
        "Dollar dominance, slowly eroding — but not toward the renminbi",
        subtitle="Share of world allocated FX reserves by currency (IMF COFER). The dollar has shed ~15 points since 1999; "
        "the euro plateaued and the yuan never arrived — the loss went to 'nontraditional' currencies.",
        ylabel="% of allocated reserves",
    )
    styles = {"USD": ("#1f6feb", 2.6), "EUR": ("#8250df", 2.0), "JPY": ("#1a7f37", 1.6),
              "GBP": ("#9a6700", 1.6), "CNY": ("#d1242f", 2.0), "OTH": ("#57606a", 1.6)}
    for cur, (color, lw) in styles.items():
        if cur in rc.columns:
            s = rc[cur].dropna()
            ax.plot(s.index, s, lw=lw, color=color, label=cur)
            if cur in ("USD", "EUR", "CNY"):  # only the story-carrying labels, to avoid pile-up
                ax.annotate(f"{cur} {s.iloc[-1]:.0f}%", (s.index[-1], s.iloc[-1]),
                            xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                            color=color, va="center", fontweight="bold")
    ax.set_xlim(1995, 2030)
    ax.annotate("the renminbi has stalled\nat ~2% despite China's size", xy=(2025, 2),
                xytext=(2012, 12), fontsize=8.5, color="#d1242f",
                arrowprops=dict(arrowstyle="->", color="#d1242f"))
    ax.legend(loc="center left", fontsize=8.5, ncol=2)
    source_note(ax, "Source: computed from IMF COFER via SDMX 2.1 (econlab warehouse)")
    save(fig, "02_reserve_currencies")


def fig_global_imbalances() -> None:
    ca = global_imbalances()
    top = pd.concat([ca.head(4), ca.tail(6)]).sort_values()
    print("[ch02] US current account 2024 ($bn):", round(ca.min()))
    names = {"USA": "United States", "GBR": "UK", "BRA": "Brazil", "AUS": "Australia",
             "IND": "India", "FRA": "France", "CHN": "China", "DEU": "Germany",
             "JPN": "Japan", "TWN": "Taiwan", "NLD": "Netherlands", "KOR": "S. Korea",
             "SGP": "Singapore", "CHE": "Switzerland", "RUS": "Russia", "SAU": "Saudi Arabia"}
    labels = [names.get(e, e) for e in top.index]
    colors = ["#d1242f" if v < 0 else "#1a7f37" for v in top.values]
    fig, ax = new_fig(
        "The world's imbalances flow through one deficit: America",
        subtitle="Current-account balance 2024, US\\$ billions (IMF). Surplus nations lend to deficit nations; "
        "the US alone absorbs ~\\$1.2tn — roughly the sum of every major surplus combined.",
        ylabel=None,
    )
    ax.barh(range(len(top)), top.values, color=colors)
    ax.set_yticks(range(len(top)), labels, fontsize=9)
    ax.axvline(0, color="#24292f", lw=1)
    ax.set_xlabel("current-account balance, US$ bn (surplus ▶ / ◀ deficit)")
    for i, v in enumerate(top.values):
        ax.text(v + (30 if v > 0 else -30), i, f"{v:+,.0f}", va="center",
                ha="left" if v > 0 else "right", fontsize=8)
    ax.margins(x=0.18)
    source_note(ax, "Source: computed from IMF current-account balance × nominal GDP (econlab warehouse)")
    save(fig, "02_global_imbalances")


def fig_convergence_ladder() -> None:
    cl = convergence_ladder()
    print("[ch02] Argentina % of US: 1913 =", round(cl.loc[1913, "ARG"]),
          "-> 2022 =", round(cl.loc[2022, "ARG"]))
    fig, ax = new_fig(
        "The convergence ladder: catching up, standing still, falling behind",
        subtitle="GDP per capita as % of the United States, 1900–2022 (Maddison). Three fates: the Asian climbers, "
        "the stable frontier, and Argentina — the century's great regression.",
        ylabel="GDP per capita, % of US",
    )
    styles = {"DEU": ("#57606a", "Germany"), "JPN": ("#57606a", "Japan"),
              "GBR": ("#57606a", "Britain"), "KOR": ("#1a7f37", "S. Korea"),
              "CHN": ("#1f6feb", "China"), "IND": ("#0969da", "India"),
              "NGA": ("#9a6700", "Nigeria"), "ARG": ("#d1242f", "Argentina")}
    label_dy = {"JPN": -9, "GBR": 9, "DEU": 0}  # stagger the clustered frontier labels
    for code, (color, label) in styles.items():
        s = cl[code].dropna()
        lw = 2.6 if code == "ARG" else 1.6
        ax.plot(s.index, s, lw=lw, color=color, alpha=0.9 if code == "ARG" else 0.7)
        ax.annotate(label, (s.index[-1], s.iloc[-1]), xytext=(6, label_dy.get(code, 0)),
                    textcoords="offset points", fontsize=8.5, color=color, va="center",
                    fontweight="bold" if code == "ARG" else "normal")
    ax.annotate("Argentina 1913:\nricher than France,\n60% of US", xy=(1913, 60),
                xytext=(1925, 82), fontsize=8.5, color="#d1242f",
                arrowprops=dict(arrowstyle="->", color="#d1242f"))
    ax.set_xlim(1900, 2040)
    ax.set_ylim(0, 100)
    source_note(ax, "Source: computed from Maddison Project 2023 GDP per capita (econlab warehouse)")
    save(fig, "02_convergence_ladder")


# the three faces of US aid, for coloring the top recipients
_AID_CATEGORY = {
    "Iraq": "war / reconstruction", "Afghanistan": "war / reconstruction",
    "Ukraine": "war / reconstruction", "Sudan": "war / reconstruction",
    "Egypt, Arab Republic of": "strategic ally", "Israel": "strategic ally",
    "Jordan": "strategic ally", "Pakistan": "strategic ally", "Colombia": "strategic ally",
    "Ethiopia": "development", "Kenya": "development", "Nigeria": "development",
    "Congo, Democratic Republic of": "development", "India": "development", "Uganda": "development",
}
_AID_COL = {"war / reconstruction": "#b42318", "strategic ally": "#b45309", "development": "#0d6e78"}


def us_aid_footprint() -> dict:
    """How far US public money reaches: bilateral aid by recipient (WDI DAC),
    its geographic reach, and its weight in the recipient's own economy."""
    with connect() as con:
        base = ("obs o JOIN entities e USING(entity) WHERE o.series_id='wdi/DC.DAC.USAL.CD' "
                "AND e.kind='country' AND o.value>0")
        top = con.execute(f"SELECT e.name, sum(o.value)/1e9 bn FROM {base} GROUP BY 1 ORDER BY 2 DESC LIMIT 15").df()
        reach, total = con.execute(f"SELECT count(DISTINCT o.entity), sum(o.value)/1e9 FROM {base}").fetchone()
        ts = con.execute(f"SELECT o.year yr, sum(o.value)/1e9 bn FROM {base} GROUP BY 1 ORDER BY 1").df()
        impact = con.execute(
            "WITH aid AS (SELECT entity, avg(value) a FROM obs WHERE series_id='wdi/DC.DAC.USAL.CD' "
            "AND year BETWEEN 2015 AND 2023 AND value>0 GROUP BY 1), "
            "gdp AS (SELECT entity, avg(value) g FROM obs WHERE series_id='wdi/NY.GDP.MKTP.CD' "
            "AND year BETWEEN 2015 AND 2023 GROUP BY 1) "
            "SELECT e.name, round(100.0*aid.a/gdp.g,1) pct FROM aid JOIN gdp USING(entity) "
            "JOIN entities e USING(entity) WHERE e.kind='country' AND gdp.g>0 ORDER BY pct DESC LIMIT 12").df()
    return {"top": top, "reach": int(reach), "total": float(total), "ts": ts, "impact": impact}


def fig_us_aid_reach() -> None:
    """Trace the money outward: where $7T of US aid went, and where it mattered most."""
    import matplotlib.pyplot as plt

    r = us_aid_footprint()
    print(f"[ch02] US bilateral aid: {r['reach']} countries, ${r['total']:,.0f}B since 1960; "
          f"most-dependent {r['impact'].iloc[0]['name']} {r['impact'].iloc[0]['pct']}% of GDP")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.6))
    fig.suptitle(f"US public money reaches {r['reach']} countries — and for the smallest, it is a fifth of the economy",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    top = r["top"].iloc[::-1]
    cats = [_AID_CATEGORY.get(n, "development") for n in top["name"]]
    ax1.barh(range(len(top)), top["bn"], color=[_AID_COL[c] for c in cats])
    ax1.set_yticks(range(len(top)), [n.split(",")[0] for n in top["name"]], fontsize=8.5)
    for i, bn in enumerate(top["bn"]):
        ax1.text(bn + 0.4, i, f"${bn:.0f}B", va="center", fontsize=8)
    ax1.set_title(f"Where it went — top recipients, 1960–2023 (${r['total']:,.0f}B total)", fontsize=9.5, loc="left")
    ax1.set_xlabel("cumulative US bilateral aid, $ billions")
    ax1.set_xlim(0, top["bn"].max() * 1.13)
    for c, col in _AID_COL.items():
        ax1.scatter([], [], color=col, marker="s", label=c)
    ax1.legend(fontsize=7.5, loc="lower right")

    imp = r["impact"].iloc[::-1]
    ax2.barh(range(len(imp)), imp["pct"], color="#0d6e78")
    ax2.set_yticks(range(len(imp)), [n.split(",")[0].replace(", Fed. Rep.", "") for n in imp["name"]], fontsize=8.5)
    for i, p in enumerate(imp["pct"]):
        ax2.text(p + 0.25, i, f"{p:.0f}%", va="center", fontsize=8)
    ax2.set_title("Where it mattered most — US aid as a share of the recipient's GDP (2015–23)", fontsize=9.5, loc="left")
    ax2.set_xlabel("% of recipient GDP")
    ax2.set_xlim(0, imp["pct"].max() * 1.15)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="x")
    fig.text(0.01, -0.02, "Source: World Bank WDI — net bilateral aid flows from the United States (DC.DAC.USAL.CD) ÷ GDP (econlab). "
             "This is development (ODA) aid; military financing (FMF) and the Fed's dollar swap lines are separate channels, not shown.",
             fontsize=7.3, color="#57606a")
    fig.tight_layout()
    save(fig, "02_us_aid_reach")


def main() -> None:
    fig_growth_landscape()
    fig_us_aid_reach()
    fig_convergence_ladder()
    fig_inflation_regimes()
    fig_reserve_currencies()
    fig_global_imbalances()
    fig_debt_distribution()
    fig_r_minus_g()


if __name__ == "__main__":
    main()
