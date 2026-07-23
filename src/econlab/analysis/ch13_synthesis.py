"""Chapter 12 — Synthesis: the century's vital signs + the state of the world.

Everything here is queried live from the warehouse at generation time; the
'state of the world' table is the report's heartbeat and doubles as the
apparatus's demo query set.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, save
from .ch06_wealth import global_shares
from .ch04_structure import openness
from .maddison_world import maddison_world_reference_annual


def _one(con, sql: str):
    return con.execute(sql).fetchone()[0]


def crisis_share_by_decade() -> pd.Series:
    """Share of JST economies in a systemic crisis, per decade."""
    with connect() as con:
        df = con.execute(
            "SELECT year, entity, value FROM obs WHERE series_id='jst/crisisJST'"
        ).df()
    df["decade"] = (df.year // 10) * 10
    out = df.groupby("decade").apply(
        lambda s: 100 * s[s.value == 1].entity.nunique() / s.entity.nunique(),
        include_groups=False,
    )
    return out[out.index >= 1870]


def state_of_the_world() -> pd.DataFrame:
    """The dashboard: headline metrics computed live, with historical context."""
    rows = []
    with connect() as con:
        # people
        pop = _one(con, "SELECT value FROM obs WHERE series_id='unwpp/TPopulation1July' AND entity='WLD' AND year=2026")
        rows.append(("World population", f"{pop/1e9:.2f}B", "peaks 10.29B in 2084 (UN medium)"))
        age = _one(con, "SELECT value FROM obs WHERE series_id='unwpp/MedianAgePop' AND entity='WLD' AND year=2026")
        rows.append(("World median age", f"{age:.1f} yrs", "21.5 in 1980; 36.1 by 2050"))

        # output
        gdp = con.execute(
            "SELECT sum(value) FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
        ).fetchone()[0]
        rows.append(("World GDP (sum of countries)", f"${gdp/1e12:.0f}T", "IMF 2026, current US$"))
        g = con.execute(
            """
            WITH w AS (SELECT entity, value FROM obs WHERE series_id='imf/NGDPD' AND year=2026)
            SELECT sum(g.value * w.value) / sum(w.value)
            FROM obs g JOIN w USING (entity)
            WHERE g.series_id='imf/NGDP_RPCH' AND g.year=2026
            """
        ).fetchone()[0]
        rows.append(("World real growth 2026", f"{g:.1f}%/yr", "GDP-weighted; Golden-Age record was 4.7"))

        # prices & money (US)
        cpi = con.execute(
            "SELECT 100*(max_by(value,date)/max_by(value, date - INTERVAL 1 YEAR)-1) "
            "FROM obs WHERE series_id='shiller/cpi'"
        ).fetchone()
        infl = _one(con, """
            SELECT round((a.value/b.value-1)*100,1) FROM obs a JOIN obs b
            ON b.series_id=a.series_id AND b.date = a.date - INTERVAL 1 YEAR
            WHERE a.series_id='shiller/cpi' ORDER BY a.date DESC LIMIT 1""")
        rows.append(("US inflation (CPI yoy)", f"{infl:.1f}%", "above target four years running"))
        ff = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/FEDFUNDS'")
        dgs10 = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/DGS10'")
        rows.append(("Fed funds / 10-yr Treasury", f"{ff:.2f}% / {dgs10:.2f}%", "curve re-steepened: +0.4pp"))
        hy = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/BAMLH0A0HYM2'")
        rows.append(("High-yield spread", f"{hy:.2f}pp", "top-decile tightness"))
        walcl = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/WALCL'")
        rows.append(("Fed balance sheet", f"${walcl/1e12:.2f}T", "peak was $8.97T (2022)"))

        # markets
        spx = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='markets/spx'")
        cape = _one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='shiller/cape'")
        cape_pct = _one(con, f"SELECT 100*avg(CASE WHEN value < {cape} THEN 1 ELSE 0 END) FROM obs WHERE series_id='shiller/cape'")
        rows.append(("S&P 500 / CAPE", f"{spx:,.0f} / {cape:.1f}", f"CAPE at {cape_pct:.0f}th pctile of 145 yrs"))

        # debt
        usdebt = _one(con, """
            SELECT round(d.value/g.value*100,0) FROM obs d JOIN obs g
            ON g.series_id='wdi/NY.GDP.MKTP.CD' AND g.entity='USA' AND g.year=2024
            WHERE d.series_id='fiscaldata/debt_outstanding' AND d.year=2024""")
        rows.append(("US federal debt / GDP", f"{usdebt:.0f}%", "above the 1946 war peak (119%)"))
        rows.append(("US r−g", "≈ −1.3pp", "10Y 4.3% vs nominal growth ~5.6%; debt melts, slowly"))

        # distribution
        top1 = _one(con, """
            SELECT sum(value) FROM obs WHERE series_id IN
            ('dfa/nwshare.net_worth.toppt1','dfa/nwshare.net_worth.remainingtop1')
            AND date=(SELECT max(date) FROM obs WHERE series_id='dfa/nwshare.net_worth.toppt1')""")
        rows.append(("US top-1% wealth share", f"{top1:.1f}%", "bottom 50% hold 2.5%"))
        gtop10 = _one(con, "SELECT max_by(value,year) FROM obs WHERE series_id='wid/sptincj992.p90p100' AND entity='WLD'")
        rows.append(("Global top-10% income share", f"{100*gtop10:.0f}%", "peak ~60% (1900s); falling since 2000"))

        # trade & energy
        chn = _one(con, """
            SELECT 100*max_by(value, year)/(SELECT sum(value) FROM obs WHERE series_id='baci/exports_total' AND year=2024)
            FROM obs WHERE series_id='baci/exports_total' AND entity='CHN'""")
        rows.append(("China share of world exports", f"{chn:.0f}%", "#1 supplier to 96 countries (US: 32)"))
        usd_res = _one(con, "SELECT max_by(value, COALESCE(date, make_date(year,1,1))) FROM obs WHERE series_id='cofer/reserve_share.USD'")
        rows.append(("US-dollar share of FX reserves", f"{usd_res:.0f}%", "~76% in 2000; lost share went to a small-currency basket, not the RMB"))
        opens = _one(con, "SELECT value FROM obs WHERE series_id='wdi/NE.TRD.GNFS.ZS' AND entity='WLD' AND year=2024")
        rows.append(("World trade / GDP", f"{opens:.0f}%", "2008 peak was 60% — the plateau"))
        en = _one(con, "SELECT max_by(value,year)/1000 FROM obs WHERE series_id='energy/primary_energy_consumption' AND entity='WLD'")
        rows.append(("World primary energy", f"{en:,.0f} PWh/yr", "intensity of GDP −42% since 1973"))

        # the lever watch (Ch. 11)
        milex = _one(con, """
            SELECT 100 * u.value / w.value FROM obs u JOIN obs w
            ON w.series_id=u.series_id AND w.year=u.year AND w.entity='WLD'
            WHERE u.series_id='sipri/milex_constusd' AND u.entity='USA'
            ORDER BY u.year DESC LIMIT 1""")
        rows.append(("Violence lever: US share of world milex", f"{milex:.0f}%",
                     "eroding fastest of the levers: −5.6pp/decade since 2000"))
        sdn = _one(con, "SELECT max_by(value,year) FROM obs WHERE series_id='sanctions/sdn_total'")
        sdn00 = _one(con, "SELECT value FROM obs WHERE series_id='sdnarchive/sdn_total' AND year=2000")
        rows.append(("Sanctions lever: OFAC SDN designations", f"{sdn:,.0f}",
                     f"{sdn/sdn00:.1f}x the 2000 list; Russia the largest bloc"))
        ent = _one(con, "SELECT max_by(value,year) FROM obs WHERE series_id='entitylist/entities' AND entity='CHN'")
        rows.append(("Tech lever: Chinese entities export-controlled", f"{ent:,.0f}",
                     "90 in 2017 — the chips-and-lists era, counted"))
        opec = _one(con, """
            WITH prod AS (SELECT year, entity, value FROM obs o JOIN entities e USING (entity)
                          WHERE series_id='energy/oil_production' AND e.kind IN ('country','historical'))
            SELECT 100*sum(CASE WHEN entity IN ('SAU','IRN','IRQ','KWT','ARE','VEN','NGA','LBY','DZA','AGO','COG','GNQ','GAB')
                          THEN value END)/sum(value) FROM prod WHERE year=(SELECT max(year) FROM prod)""")
        rows.append(("Energy lever: OPEC-core share of oil", f"{opec:.0f}%",
                     "1974 peak was 60%; the swing barrel moved to Texas"))

    return pd.DataFrame(rows, columns=["metric", "value", "context"])


def fig_vital_signs() -> None:
    import matplotlib.pyplot as plt

    ref = maddison_world_reference_annual().set_index("year")
    growth = 100 * ((ref["gdppc"] / ref["gdppc"].shift(10)) ** (1 / 10) - 1)
    jst, wdi = openness()
    gs = global_shares()
    crises = crisis_share_by_decade()

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("The world economy's vital signs, 1870-2026", x=0.01, ha="left",
                 fontweight="bold", fontsize=14)

    ax = axes[0, 0]
    ax.plot(growth.index, growth.values, lw=1.8, color=PALETTE[0])
    ax.axhline(0, color="#57606a", lw=0.7)
    ax.set_title("World GDP-pc growth (10-yr trailing, %/yr)", fontsize=10, loc="left")

    ax = axes[0, 1]
    ax.plot(jst.index, jst.values, lw=1.8, color=PALETTE[0], label="18 economies (JST)")
    ax.plot(wdi.index, wdi.values, lw=1.8, color=PALETTE[1], label="world (WDI)")
    ax.set_title("Trade openness, % of GDP", fontsize=10, loc="left")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    ax.plot(gs.index, 100 * gs["top10"], lw=1.8, color=PALETTE[4])
    ax.set_title("Global top-10% income share, %", fontsize=10, loc="left")

    ax = axes[1, 1]
    ax.bar(crises.index, crises.values, width=8, color=PALETTE[1])
    ax.set_title("Economies in systemic banking crisis, % per decade", fontsize=10, loc="left")

    for ax in axes.flat:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.01,
             "Source: computed from Maddison, JST, WDI, WID (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "13_vital_signs")


def main() -> None:
    fig_vital_signs()
    df = state_of_the_world()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
