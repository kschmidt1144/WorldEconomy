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


def main() -> None:
    fig_growth_landscape()
    fig_inflation_regimes()
    fig_debt_distribution()
    fig_r_minus_g()


if __name__ == "__main__":
    main()
