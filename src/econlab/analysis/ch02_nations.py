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


# the "standing five" central banks with permanent Fed swap lines (since Oct 2013)
_STANDING = {"European Central Bank", "Bank of Japan", "Bank of England",
             "Swiss National Bank", "Bank of Canada"}


def fed_swap_lines() -> dict:
    """The Fed as the world's lender of last resort: dollars lent to foreign
    central banks (FRED SWPT), the crisis peaks, and the scale vs its own balance sheet."""
    with connect() as con:
        ts = con.execute("SELECT date, value/1e9 bn FROM obs WHERE series_id='fred/SWPT' ORDER BY date").df()
        peaks = con.execute(
            "SELECT year, round(max(value)/1e9,0) bn FROM obs WHERE series_id='fred/SWPT' AND value>1e9 GROUP BY 1 ORDER BY 2 DESC LIMIT 4").df()
        fed_bs = con.execute(
            "SELECT value/1e9 FROM obs WHERE series_id='fred/WALCL' ORDER BY abs(date - DATE '2008-12-17') LIMIT 1").fetchone()[0]
    peak = float(ts["bn"].max())
    return {"ts": ts, "peak": peak, "peaks": peaks, "fed_bs_2008": float(fed_bs),
            "pct_of_fed": 100 * peak / float(fed_bs)}


def swap_recipients_2020() -> pd.DataFrame:
    """Per-central-bank PEAK dollars outstanding during the March-2020 crunch,
    computed from NY Fed operation-level data (cross-checks FRED SWPT's $449B)."""
    with connect() as con:
        return con.execute(
            "WITH days AS (SELECT unnest(generate_series(DATE '2020-03-01', DATE '2020-08-31', INTERVAL 1 DAY))::DATE d), "
            "bal AS (SELECT o.counterparty cb, days.d, sum(o.amount) outstanding FROM swap_ops o "
            "JOIN days ON days.d >= o.settlementDate AND days.d < o.maturityDate GROUP BY 1,2) "
            "SELECT cb, round(max(outstanding)/1e9,1) peak_bn FROM bal GROUP BY 1 ORDER BY 2 DESC").df()


def fig_fed_swap_lines() -> None:
    """The dollar's global backstop: the Fed's crisis lending to foreign central banks."""
    import matplotlib.pyplot as plt

    s = fed_swap_lines()
    rec = swap_recipients_2020()
    print(f"[ch02] Fed swap lines: peak ${s['peak']:.0f}B ({s['pct_of_fed']:.0f}% of the Fed's balance sheet); "
          f"2020 top drawer {rec.iloc[0]['cb']} ${rec.iloc[0]['peak_bn']}B")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.4), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.suptitle("The Fed is the world's lender of last resort — in dollars",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    ts = s["ts"]
    ax1.fill_between(ts["date"], ts["bn"], color="#0d6e78", alpha=0.85)
    ax1.set_title("Dollars the Fed had lent to foreign central banks (SWPT, $B)", fontsize=9.5, loc="left")
    ax1.set_ylabel("$ billions outstanding")
    ax1.annotate("2008: $583B\n(Lehman → unlimited\nlines, Oct 2008)", xy=(__import__("datetime").date(2008, 12, 17), 583),
                 xytext=(__import__("datetime").date(2010, 1, 1), 470), fontsize=8,
                 arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))
    ax1.annotate("2011–12\nEuro crisis\n~$109B", xy=(__import__("datetime").date(2012, 2, 1), 109),
                 xytext=(__import__("datetime").date(2013, 6, 1), 210), fontsize=8,
                 arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))
    ax1.annotate("2020: $449B\n(COVID)", xy=(__import__("datetime").date(2020, 5, 1), 449),
                 xytext=(__import__("datetime").date(2016, 6, 1), 430), fontsize=8,
                 arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))

    r = rec.iloc[::-1]
    colors = ["#b45309" if cb in _STANDING else "#0d6e78" for cb in r["cb"]]
    ax2.barh(range(len(r)), r["peak_bn"], color=colors)
    ax2.set_yticks(range(len(r)), [cb.replace("European Central Bank", "ECB").replace("Monetary Authority of ", "")
                                   .replace("Bank of ", "").replace("Banco de ", "").replace("Danmarks Nationalbank", "Denmark")
                                   .replace("Reserve Bank of ", "").replace("Norges Bank", "Norway")
                                   .replace("Swiss National Bank", "Switzerland") for cb in r["cb"]], fontsize=8)
    for i, v in enumerate(r["peak_bn"]):
        ax2.text(v + 3, i, f"${v:.0f}B", va="center", fontsize=8)
    ax2.set_title("Who drew, March 2020 — Japan + Europe took 83%", fontsize=9.5, loc="left")
    ax2.set_xlabel("peak $B outstanding")
    ax2.set_xlim(0, r["peak_bn"].max() * 1.18)
    ax2.scatter([], [], color="#b45309", marker="s", label="permanent (standing-five ally)")
    ax2.scatter([], [], color="#0d6e78", marker="s", label="temporary line")
    ax2.legend(fontsize=7.5, loc="lower right")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="x" if ax is ax2 else "y")
    fig.text(0.01, -0.02, "Source: FRED SWPT (aggregate, weekly) + NY Fed operation-level data (per central bank); peak = max simultaneous "
             "dollars outstanding (econlab). The per-bank sum reproduces SWPT's $449B 2020 peak.", fontsize=7.3, color="#57606a")
    fig.tight_layout()
    save(fig, "02_fed_swap_lines")


def reserve_currency_contest() -> dict:
    """The dollar's slow erosion, and the myth of the RMB rival: reserve shares
    over time, and where the dollar's lost share actually went."""
    with connect() as con:
        def s(cur):
            return con.execute(
                f"SELECT year, max_by(value, COALESCE(date, make_date(year,1,1))) v "
                f"FROM obs WHERE series_id='cofer/reserve_share.{cur}' GROUP BY year ORDER BY year").df()
        usd, eur, cny = s("USD"), s("EUR"), s("CNY")
        nontrad = con.execute(
            "SELECT year, sum(v) v FROM (SELECT year, series_id, "
            "max_by(value, COALESCE(date, make_date(year,1,1))) v FROM obs WHERE series_id IN "
            "('cofer/reserve_share.CAD','cofer/reserve_share.AUD','cofer/reserve_share.CHF',"
            "'cofer/reserve_share.CNY','cofer/reserve_share.OTH') GROUP BY year, series_id) "
            "GROUP BY year ORDER BY year").df()
    cny_peak = float(cny["v"].max())
    return {"usd": usd, "eur": eur, "cny": cny, "nontrad": nontrad,
            "cny_peak": cny_peak, "cny_now": float(cny["v"].iloc[-1]),
            "usd_now": float(usd["v"].iloc[-1]), "usd_max": float(usd["v"].max())}


def fig_dollar_vs_rmb() -> None:
    """The dollar erodes — but not to the renminbi."""
    import matplotlib.pyplot as plt

    r = reserve_currency_contest()
    print(f"[ch02] reserves: USD {r['usd_max']:.0f}%→{r['usd_now']:.0f}%; "
          f"RMB peaked {r['cny_peak']:.1f}% → {r['cny_now']:.1f}% (reversed)")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle("The dollar is slowly eroding — but not to the renminbi",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    ax1.plot(r["usd"]["year"], r["usd"]["v"], lw=2.3, color="#0d6e78", label="US dollar")
    ax1.plot(r["eur"]["year"], r["eur"]["v"], lw=2, color="#57606a", label="euro")
    ax1.plot(r["nontrad"]["year"], r["nontrad"]["v"], lw=2, color="#b45309",
             label="non-traditional basket\n(CAD, AUD, CHF, CNY, other)")
    ax1.set_title("Share of world FX reserves, %", fontsize=9.5, loc="left")
    ax1.set_ylabel("% of allocated reserves")
    ax1.annotate(f"{r['usd_max']:.0f}% → {r['usd_now']:.0f}%", xy=(r["usd"]["year"].iloc[-1], r["usd_now"]),
                 xytext=(r["usd"]["year"].iloc[-1] - 9, r["usd_now"] + 6), fontsize=8.5, color="#0d6e78", fontweight="bold")
    ax1.legend(fontsize=8, loc="center left")
    ax1.set_ylim(0, 80)

    ax2.plot(r["cny"]["year"], r["cny"]["v"], lw=2.4, color="#b42318", marker="o", ms=3)
    ax2.fill_between(r["cny"]["year"], r["cny"]["v"], 0, color="#b42318", alpha=0.08)
    ax2.set_title("The renminbi: peaked in 2022, and reversed", fontsize=9.5, loc="left")
    ax2.set_ylabel("RMB share of world FX reserves, %")
    imax = r["cny"]["v"].idxmax()
    ax2.annotate(f"peak {r['cny_peak']:.1f}%", xy=(r["cny"]["year"].iloc[imax], r["cny_peak"]),
                 xytext=(r["cny"]["year"].iloc[imax] - 3.5, r["cny_peak"] + 0.3), fontsize=8.5,
                 arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))
    ax2.text(0.5, 0.08, "after joining the IMF's reserve basket in 2016, the RMB\n"
             "climbed to ~2.9% — then stalled and fell back to ~2%.\nThe dollar's lost share went to a diffuse basket, not to China.",
             transform=ax2.transAxes, fontsize=7.6, va="bottom", color="#57606a", style="italic")
    ax2.set_ylim(0, 3.4)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: IMF COFER allocated reserves by currency (econlab). 'Non-traditional' = CAD+AUD+CHF+CNY+other — "
             "the small 'safe' currencies that actually absorbed the dollar's decline.", fontsize=7.3, color="#57606a")
    fig.tight_layout()
    save(fig, "02_dollar_vs_rmb")


# ---------- the economics of war: how it "profits", and who ----------

_WWII = {"USA": "United States", "GBR": "United Kingdom", "DEU": "Germany",
         "JPN": "Japan", "FRA": "France"}
_P5 = {"USA", "RUS", "FRA", "GBR", "CHN"}   # UN Security Council permanent members


def war_gdp_divergence() -> pd.DataFrame:
    """Maddison real GDP per capita, indexed to 1938=100, 1935-1950 — the WWII
    arsenal (USA, never invaded) vs the battlefields."""
    with connect() as con:
        d = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='maddison/gdppc' "
            "AND entity IN ('USA','GBR','DEU','JPN','FRA') AND year BETWEEN 1935 AND 1950"
        ).df()
    base = d[d["year"] == 1938].set_index("entity")["value"]
    d["idx"] = [100 * v / base[e] for e, v in zip(d["entity"], d["value"])]
    return d.sort_values(["entity", "year"])


def arms_export_share() -> pd.DataFrame:
    """Cumulative SIPRI arms-export share by country, 1960-2024 — who sells war."""
    with connect() as con:
        d = con.execute(
            "SELECT e.entity, e.name, sum(o.value) v FROM obs o JOIN entities e ON o.entity=e.entity "
            "WHERE o.series_id='wdi/MS.MIL.XPRT.KD' AND e.kind='country' GROUP BY 1,2"
        ).df()
    d["pct"] = 100 * d["v"] / d["v"].sum()
    return d.sort_values("pct", ascending=False).reset_index(drop=True)


def real_oil_history() -> pd.DataFrame:
    """World crude price 1960-2025, deflated to constant 2020 USD by US CPI."""
    with connect() as con:
        oil = con.execute("SELECT year, avg(value) o FROM obs WHERE series_id='pinksheet/oil' GROUP BY 1").df()
        cpi = con.execute("SELECT year, avg(value) c FROM obs WHERE series_id='fred/CPIAUCSL' GROUP BY 1").df()
    m = oil.merge(cpi, on="year")
    base = float(m.loc[m["year"] == 2020, "c"].iloc[0])
    m["real"] = m["o"] * base / m["c"]
    return m.sort_values("year")


def fig_war_gdp() -> None:
    """Resolve the paradox: war ruins where it is fought and enriches who supplies it."""
    import matplotlib.pyplot as plt

    d = war_gdp_divergence()
    end = d[d["year"] == 1946].set_index("entity")["idx"]
    print(f"[ch02] WWII GDP/capita 1938->1946: USA {end['USA']:.0f}, GBR {end['GBR']:.0f}, "
          f"FRA {end['FRA']:.0f}, JPN {end['JPN']:.0f}, DEU {end['DEU']:.0f} (1938=100)")

    fig, ax = plt.subplots(figsize=(10.5, 6))
    fig.suptitle("Same war, opposite fates: destruction for the battlefield, a boom for the arsenal",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)
    styles = {"USA": ("#0d6e78", 3.2), "GBR": ("#1a7f37", 2.0), "FRA": ("#9a6700", 1.8),
              "JPN": ("#b45309", 2.0), "DEU": ("#b42318", 2.4)}
    for e, lab in _WWII.items():
        s = d[d["entity"] == e]
        col, lw = styles[e]
        ax.plot(s["year"], s["idx"], color=col, lw=lw, label=lab)
        last = s[s["year"] == 1946]
        if len(last):
            ax.annotate(f"{lab}: {last['idx'].iloc[0]:.0f}", xy=(1946, last["idx"].iloc[0]),
                        xytext=(1946.25, last["idx"].iloc[0]), fontsize=8.5, color=col,
                        va="center", fontweight="bold" if e in ("USA", "DEU") else "normal")
    ax.axhline(100, color="#57606a", lw=0.8, ls=":")
    ax.axvspan(1939, 1945, color="#8593a0", alpha=0.10)
    ax.text(1942, ax.get_ylim()[1] * 0.97, "World War II", ha="center", fontsize=8.5, color="#57606a")
    ax.set_ylabel("real GDP per capita, 1938 = 100")
    ax.set_xlim(1935, 1949.5)
    ax.set_title("The USA — never bombed, the world's supplier — grew through the war; "
                 "Germany and Japan were flattened", fontsize=9.3, loc="left")
    source_note(ax, "Maddison Project 2023, real GDP per capita (2011 intl. $). "
                    "Germany's 1944 peak (122) is war mobilization — then defeat cut it to 44 by 1946.")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "02_war_gdp")


def fig_arms_trade() -> None:
    """Who profits from selling war: the arms trade is a five-nation oligopoly."""
    import matplotlib.pyplot as plt

    a = arms_export_share()
    top = a.head(8).iloc[::-1]
    p5_share = a[a["entity"].isin(_P5)]["pct"].sum()
    with connect() as con:
        mil = con.execute(
            "SELECT e.name, o.value v FROM obs o JOIN entities e ON o.entity=e.entity "
            "WHERE o.series_id='wdi/MS.MIL.XPND.CD' AND o.year=2022 AND e.kind='country' "
            "ORDER BY o.value DESC LIMIT 7"
        ).df()
    mil = mil.iloc[::-1]
    print(f"[ch02] arms exports: US {a.iloc[0]['pct']:.0f}%, top5 {a.head(5)['pct'].sum():.0f}%, "
          f"UNSC-P5 {p5_share:.0f}%; 2022 US military spend ${mil['v'].max()/1e9:.0f}bn")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.suptitle("Who profits from selling war: five nations control four-fifths of the arms trade",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.8)

    cols = ["#b42318" if e in _P5 else "#8593a0" for e in top["entity"]]
    ax1.barh(range(len(top)), top["pct"], color=cols)
    ax1.set_yticks(range(len(top)), top["name"], fontsize=8.5)
    for i, (v, e) in enumerate(zip(top["pct"], top["entity"])):
        ax1.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=8,
                 fontweight="bold" if e == "USA" else "normal")
    ax1.set_title("Share of all arms exports, 1960–2024", fontsize=9.3, loc="left")
    ax1.set_xlabel("% of world arms exports (SIPRI trend-indicator value)")
    ax1.set_xlim(0, 52)
    ax1.scatter([], [], color="#b42318", marker="s", label="UN Security Council\npermanent member")
    ax1.scatter([], [], color="#8593a0", marker="s", label="other")
    ax1.legend(fontsize=7.6, loc="lower right")
    ax1.text(0.98, 0.42, f"The 5 permanent members\nof the Security Council —\nthe body charged with world\npeace — sell {p5_share:.0f}% of its weapons",
             transform=ax1.transAxes, ha="right", va="top", fontsize=8, color="#b42318",
             bbox=dict(boxstyle="round", fc="#fbeae7", ec="#b42318", alpha=0.9))

    ax2.barh(range(len(mil)), mil["v"] / 1e9, color="#0d6e78")
    ax2.set_yticks(range(len(mil)), mil["name"], fontsize=8.5)
    for i, v in enumerate(mil["v"] / 1e9):
        ax2.text(v + 8, i, f"{v:.0f}", va="center", fontsize=8)
    ax2.set_title("Military spending, 2022 (USD billion)", fontsize=9.3, loc="left")
    ax2.set_xlabel("annual military expenditure, USD bn")
    ax2.set_xlim(0, 980)
    ax2.text(0.97, 0.30, "The US alone outspends\nthe next nine nations combined",
             transform=ax2.transAxes, ha="right", va="top", fontsize=8, color="#0d6e78")

    source_note(ax1, "SIPRI arms transfers & military expenditure via World Bank WDI. Cumulative export share 1960–2024; spending is 2022.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "02_arms_trade")


def fig_war_oil() -> None:
    """War is the oil shock — the fragility a household feels at the pump."""
    import matplotlib.pyplot as plt

    m = real_oil_history()
    # (year, label, text_x, text_y_fraction, h-align) — staggered so labels never collide
    wars = [(1973, "Yom Kippur War\n+ Arab embargo", 1966.5, 0.74, "center"),
            (1979, "Iranian Revolution\n& Iran–Iraq War", 1981.5, 0.99, "center"),
            (1990, "Gulf War", 1990, 0.58, "center"),
            (2003, "Iraq War", 2003, 0.58, "center"),
            (2022, "Russia–Ukraine", 2022, 0.99, "center")]
    peak74 = m.loc[m["year"].between(1973, 1975), "real"].max() / m.loc[m["year"] == 1972, "real"].iloc[0]
    print(f"[ch02] real oil (2020$): 1972 ${m.loc[m['year']==1972,'real'].iloc[0]:.0f} -> "
          f"1974 ${m.loc[m['year']==1974,'real'].iloc[0]:.0f} ({peak74:.1f}x on the '73 war); "
          f"peak ${m['real'].max():.0f} in {int(m.loc[m['real'].idxmax(),'year'])}")

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.suptitle("War is the oil shock: nearly every price spike traces to a war",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)
    ax.plot(m["year"], m["real"], color="#1a1a1a", lw=2)
    ax.fill_between(m["year"], m["real"], 0, color="#b45309", alpha=0.10)
    top = m["real"].max()
    for yr, lab, tx, tf, ha in wars:
        ax.axvline(yr, color="#b42318", lw=0.9, ls="--", alpha=0.7)
        yv = m.loc[m["year"] == yr, "real"].iloc[0]
        ax.annotate(lab, xy=(yr, yv), xytext=(tx, top * tf), fontsize=7.8, ha=ha, va="top",
                    color="#b42318", arrowprops=dict(arrowstyle="-", color="#b42318", lw=0.7))
    # honesty: the one big spike that was NOT a war — text tucked in open space, no data-crossing
    y08 = m.loc[m["year"] == 2008, "real"].iloc[0]
    ax.annotate("2008: demand &\nspeculation (not a war)", xy=(2008, y08), xytext=(1994, top * 0.86),
                fontsize=7.6, ha="center", va="top", color="#57606a",
                arrowprops=dict(arrowstyle="-", color="#57606a", lw=0.7, connectionstyle="arc3,rad=-0.15"))
    ax.set_ylabel("crude oil price, constant 2020 USD / barrel")
    ax.set_xlim(1960, 2026)
    ax.set_ylim(0, top * 1.12)
    ax.set_title("Real crude price, 1960–2025 — every war is a spike, though not every spike is a war",
                 fontsize=9.3, loc="left")
    source_note(ax, "World Bank Pink Sheet crude (average), deflated by US CPI to 2020 dollars. "
                    "The 2025 Israel–Iran flare-up briefly moved oil again — the same reflex, live.")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "02_war_oil")


# commodities grouped by category, and the war windows (baseline year, start (y,m), end (y,m))
_WAR_COMMODITY_GROUPS = [
    ("Energy", [("oil", "Crude oil"), ("natgas_us", "Natural gas"), ("coal", "Coal")]),
    ("Grains", [("wheat", "Wheat"), ("maize", "Maize"), ("rice", "Rice")]),
    ("Metals", [("copper", "Copper"), ("aluminum", "Aluminum"), ("nickel", "Nickel"), ("iron_ore", "Iron ore")]),
    ("Precious", [("gold", "Gold"), ("silver", "Silver")]),
    ("Softs", [("sugar", "Sugar"), ("cotton", "Cotton"), ("coffee", "Coffee")]),
]
_WARS_COMMODITY = [
    ("1973–74\nOPEC embargo", 1972, (1973, 9), (1974, 12)),
    ("1979–80\nIran / Iran–Iraq", 1978, (1979, 1), (1980, 12)),
    ("1990\nGulf War", 1989, (1990, 7), (1991, 3)),
    ("2022\nUkraine", 2021, (2022, 1), (2022, 12)),
]


def war_commodity_shocks() -> pd.DataFrame:
    """Real (2020$) commodity price move from each war's pre-war baseline to its
    in-window peak — do wars spike food and metals, or only oil?"""
    with connect() as con:
        cpi = con.execute("SELECT year(date) y, month(date) m, value c FROM obs "
                          "WHERE series_id='fred/CPIAUCSL' AND date IS NOT NULL").df()
    base2020 = cpi[cpi.y == 2020]["c"].mean()
    rows = []
    for group, comms in _WAR_COMMODITY_GROUPS:
        for slug, label in comms:
            with connect() as con:
                d = con.execute(f"SELECT year(date) y, month(date) m, value p FROM obs "
                                f"WHERE series_id='pinksheet/{slug}' AND date IS NOT NULL").df()
            d = d.merge(cpi, on=["y", "m"], how="left")
            d["real"] = d["p"] * base2020 / d["c"]
            d = d.dropna(subset=["real"])
            d["ym"] = d.y * 100 + d.m
            rec = {"group": group, "commodity": label}
            for wname, by, s, e in _WARS_COMMODITY:
                base = d[d.y == by]["real"].mean()
                peak = d[(d.ym >= s[0] * 100 + s[1]) & (d.ym <= e[0] * 100 + e[1])]["real"].max()
                rec[wname] = 100 * (peak - base) / base if base else None
            rows.append(rec)
    return pd.DataFrame(rows)


def fig_war_commodities() -> None:
    """Widen 'war = oil shock' to every commodity: which wars spike food and metals too?"""
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    df = war_commodity_shocks()
    wars = [w[0] for w in _WARS_COMMODITY]
    M = df[wars].to_numpy(dtype=float)
    print(f"[ch02] war commodities | 1990 Gulf: oil {df.loc[df.commodity=='Crude oil', wars[2]].iloc[0]:.0f}% vs "
          f"wheat {df.loc[df.commodity=='Wheat', wars[2]].iloc[0]:.0f}%; 2022 Ukraine: coal "
          f"{df.loc[df.commodity=='Coal', wars[3]].iloc[0]:.0f}%, wheat {df.loc[df.commodity=='Wheat', wars[3]].iloc[0]:.0f}%")

    fig, ax = plt.subplots(figsize=(9.5, 8))
    fig.suptitle("Widen 'war = oil shock' to every commodity: a war spikes food only when a belligerent grows it",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)
    norm = TwoSlopeNorm(vmin=-40, vcenter=0, vmax=150)
    ax.imshow(np.clip(M, -40, 150), cmap="RdBu_r", norm=norm, aspect="auto")
    ax.set_xticks(range(len(wars)), wars, fontsize=8.6)
    ax.xaxis.tick_top()
    ylabels = [c for _, comms in _WAR_COMMODITY_GROUPS for _, c in comms]
    ax.set_yticks(range(len(df)), ylabels, fontsize=8.3)
    for i in range(len(df)):
        for j in range(len(wars)):
            v = M[i, j]
            ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=7.8,
                    color="white" if (v > 80 or v < -25) else "#1a1a1a")
    # group separators + labels
    row = 0
    for group, comms in _WAR_COMMODITY_GROUPS:
        if row:
            ax.axhline(row - 0.5, color="white", lw=2.5)
        ax.text(-0.72, row + (len(comms) - 1) / 2, group, rotation=90, va="center", ha="center",
                fontsize=8.2, color="#57606a", fontweight="bold")
        row += len(comms)
    ax.set_xlim(-1.1, len(wars) - 0.5)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    source_note(ax, "World Bank Pink Sheet monthly prices, deflated to 2020 USD by US CPI; real % move from the pre-war-year "
                    "average to the in-window peak month. 1990 lights up energy only; 2022 (Russia+Ukraine grow wheat & mine nickel) lights up all five.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "02_war_commodities")


def fig_peace_dividend() -> None:
    """The cost side of war: military burden fell after the Cold War — but the US re-armed."""
    import matplotlib.pyplot as plt

    with connect() as con:
        d = con.execute("SELECT entity, year, value FROM obs WHERE series_id='wdi/MS.MIL.XPND.GD.ZS' "
                        "AND entity IN ('USA','WLD') AND year BETWEEN 1960 AND 2023").df()
    us = d[d.entity == "USA"].sort_values("year")
    wl = d[d.entity == "WLD"].sort_values("year")
    print(f"[ch02] peace dividend: US mil {us[us.year==1988].value.iloc[0]:.1f}%(1988)→"
          f"{us[us.year==1999].value.iloc[0]:.1f}%(1999)→{us[us.year==2010].value.iloc[0]:.1f}%(2010)")

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    fig.suptitle("The cost side: the Cold War's end paid a 'peace dividend' — then the US alone re-armed",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.4)
    ax.plot(us["year"], us["value"], lw=2.6, color="#b42318", label="United States")
    ax.plot(wl["year"], wl["value"], lw=2.2, color="#0d6e78", label="World")
    ax.axvspan(1989, 2000, color="#8593a0", alpha=0.10)
    ax.annotate("Cold War ends:\nUS 6.1% → 3.1% (−49%)", xy=(1988, 6.07), xytext=(1968, 6.4),
                fontsize=8.3, color="#b42318", arrowprops=dict(arrowstyle="-", color="#b42318", lw=0.7))
    ax.annotate("post-9/11 rebound\nUS 4.9% (2010)", xy=(2010, 4.90), xytext=(2011, 5.6),
                fontsize=8.3, color="#b42318", arrowprops=dict(arrowstyle="-", color="#b42318", lw=0.7))
    ax.annotate("the world never re-armed\n(~2.2%)", xy=(2016, 2.2), xytext=(2000.5, 1.15),
                fontsize=8.3, color="#0d6e78", arrowprops=dict(arrowstyle="-", color="#0d6e78", lw=0.7))
    ax.set_ylabel("military spending, % of GDP")
    ax.set_xlim(1960, 2023)
    ax.set_ylim(0, 7)
    ax.legend(fontsize=9, loc="upper right")
    ax.set_title("Military spending as a share of GDP, 1960–2022", fontsize=9.3, loc="left")
    source_note(ax, "World Bank / SIPRI military expenditure (% of GDP). The 1990s 'peace dividend' cut the US burden by "
                    "half and the world's by ~38%; only the US rebuilt it after 2001.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "02_peace_dividend")


def main() -> None:
    fig_growth_landscape()
    fig_us_aid_reach()
    fig_fed_swap_lines()
    fig_dollar_vs_rmb()
    fig_war_gdp()
    fig_arms_trade()
    fig_war_oil()
    fig_war_commodities()
    fig_peace_dividend()
    fig_convergence_ladder()
    fig_inflation_regimes()
    fig_reserve_currencies()
    fig_global_imbalances()
    fig_debt_distribution()
    fig_r_minus_g()


if __name__ == "__main__":
    main()
