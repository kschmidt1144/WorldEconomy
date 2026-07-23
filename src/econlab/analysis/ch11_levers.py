"""Chapter 11 — Levers of the World.

The tangible levers that shift the course of the world: violence, money,
energy, food, trade & sanctions, technology. Part I asks which levers moved
history most and shows each lever's signature pull as a computed event study;
Part II maps who holds each lever today.

Computed from the warehouse wherever a connector reaches (sipri, sanctions,
cofer, tic, nyfedswaps, energy, pinksheet, shiller, maddison, baci, edgar13f);
the era scoreboard and parts of the lever map are curated with citations and
AI-panel cross-checks (the ch10 convention).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

# ---------------------------------------------------------------------------
# Curated constants (tests import these; every number carries its source)
# ---------------------------------------------------------------------------

# Era scoreboard: which lever dominated, who held it, and the signature move.
# `signature` numbers are cross-checked by the AI panel (✓ = panel agrees).
ERAS = [
    ("1500-1815", "Conquest & bullion", "Iberian crowns -> Dutch -> British navy",
     "Spain ships ~150t silver/yr at peak; Britain ends holding every ocean chokepoint"),
    ("1815-1914", "Coal, steam & the gold standard", "Britain",
     "UK: ~2% of people, 52% of world coal (1870 — computed, coalhist), clears gold via London"),
    ("1914-1945", "Oil & industrial mass", "US arsenal",
     "US out-produces the Axis ~3:1 in munitions; oil decides both world wars"),
    ("1945-1971", "Nuclear umbrella & the dollar", "US (Bretton Woods)",
     "Dollar pegged to gold, everyone pegs to the dollar; US milex > rest of West combined"),
    ("1971-1980", "The oil weapon", "OPEC",
     "1973 embargo: oil x4 in months; 1979: x2 again — importers' terms of trade collapse"),
    ("1980-2008", "Capital markets & the Washington consensus", "US Treasury + Wall Street + IMF",
     "Volcker at 20% resets every debtor; IMF conditionality rewrites ~70 economies"),
    ("2008-now", "Chips, sanctions & the platform", "US + allies / China contest",
     "SWIFT/OFAC turn finance into a weapon; one EUV monopoly gates the AI buildout"),
]

# Today's lever map: lever -> (holders, kind, instrument, grip metric, source/status)
# kind: state | private | hybrid. Metrics computed from the warehouse where noted.
LEVER_MAP = [
    ("Violence", "United States + allies", "state", "Carrier groups, bases, arms pipeline",
     "US 37% of world milex (2024); US+allies ~60%", "computed: sipri"),
    ("Money", "US Treasury + Federal Reserve", "state", "Reserve currency, swap lines, UST market",
     "USD 56% of reserves; $9.4T UST held abroad; Fed swaps = only global backstop",
     "computed: cofer, tic, nyfedswaps"),
    ("Credit", "BlackRock/Vanguard/State Street + banks", "private", "Index flows, bond gatekeeping",
     "Big Three ~$25T AUM; largest holder of ~88% of S&P 500", "computed: edgar13f (ch10)"),
    ("Energy", "OPEC+ and US shale", "hybrid", "Spare capacity, export choke",
     "OPEC+ ~46% of crude output; US the largest single producer", "computed: energy 2024"),
    ("Food", "ABCD traders + exporter states", "hybrid", "Grain logistics, export bans",
     "ABCD ~75% of grain trade; 5 exporters ~65% of wheat exports", "curated (ch10) ✓"),
    ("Sanctions", "US OFAC (+EU alignment)", "state", "SDN list, secondary sanctions, SWIFT",
     "19,170 designations in force; Russia bloc largest", "computed: sanctions 2026"),
    ("Technology", "US-NL-TW chip triangle; US-CN AI race", "hybrid", "EUV/fab/accelerator chokepoints, export controls",
     "ASML 100% EUV, TSMC ~90% leading-edge, Nvidia ~90% accelerators", "curated (ch10) ✓"),
    ("Chokepoints", "Flag states & canal/strait powers", "state", "Hormuz, Malacca, Suez, Panama",
     "~20% of world oil transits Hormuz; ~30% of container trade via Malacca", "curated ✓"),
]

# Event annotations for the price-shock studies
OIL_EVENTS = [(1973.8, "OPEC embargo"), (1979.0, "Iranian revolution"),
              (1990.6, "Kuwait"), (2008.5, "$147 peak"), (2014.9, "Shale glut"),
              (2022.2, "Ukraine")]
WHEAT_EVENTS = [(1972.5, "Soviet grain deal"), (1974.0, "World food crisis"),
                (2008.0, "Food price crisis"), (2010.8, "Russian export ban"),
                (2022.2, "Ukraine war")]


# ---------------------------------------------------------------------------
# Data functions (testable units)
# ---------------------------------------------------------------------------

def world_milex() -> pd.DataFrame:
    """World + top-power military spending, constant 2024 USD."""
    with connect() as con:
        return con.execute("""
            SELECT entity, year, value/1e9 AS bn FROM obs
            WHERE series_id='sipri/milex_constusd'
              AND entity IN ('WLD','USA','CHN','RUS','SUN')
            ORDER BY entity, year""").df()


def milex_top(year: int = 2025, n: int = 15) -> pd.DataFrame:
    """Top-n military spenders in `year` + world share."""
    with connect() as con:
        df = con.execute("""
            SELECT o.entity, e.name, o.value/1e9 AS bn
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='sipri/milex_constusd' AND o.year=? AND e.kind='country'
            ORDER BY bn DESC LIMIT ?""", [year, n]).df()
        wld = con.execute(
            "SELECT value/1e9 FROM obs WHERE series_id='sipri/milex_constusd' "
            "AND entity='WLD' AND year=?", [year]).fetchone()[0]
    df["world_share"] = df["bn"] / wld * 100
    return df


def real_price(series_id: str, base_year: int = 2025) -> pd.DataFrame:
    """Annual real price (base_year US$) of a monthly pinksheet series, CPI-deflated."""
    with connect() as con:
        px = con.execute("""
            SELECT year, avg(value) AS nominal FROM obs
            WHERE series_id=? GROUP BY year ORDER BY year""", [series_id]).df()
        cpi = con.execute("""
            SELECT year, avg(value) AS cpi FROM obs
            WHERE series_id='shiller/cpi' GROUP BY year ORDER BY year""").df()
    base = float(cpi.loc[cpi.year == base_year, "cpi"].iloc[0])
    df = px.merge(cpi, on="year")
    df["real"] = df["nominal"] * base / df["cpi"]
    return df[["year", "nominal", "real"]]


def volcker_window() -> pd.DataFrame:
    """US CPI inflation %yoy and 10y yield, 1965-1995 (annual)."""
    with connect() as con:
        df = con.execute("""
            SELECT year, avg(CASE WHEN series_id='shiller/cpi' THEN value END) AS cpi,
                   avg(CASE WHEN series_id='shiller/gs10' THEN value END) AS gs10
            FROM obs WHERE series_id IN ('shiller/cpi','shiller/gs10')
              AND year BETWEEN 1964 AND 1995
            GROUP BY year ORDER BY year""").df()
    df["infl"] = df["cpi"].pct_change() * 100
    return df


def oil_producers() -> pd.DataFrame:
    """Oil production shares: US vs OPEC-core vs Russia/USSR, 1965-2024."""
    opec = ('SAU', 'IRN', 'IRQ', 'KWT', 'ARE', 'VEN', 'NGA', 'LBY', 'DZA', 'AGO',
            'COG', 'GNQ', 'GAB')
    with connect() as con:
        df = con.execute(f"""
            WITH prod AS (
              SELECT year, entity, value FROM obs o JOIN entities e USING (entity)
              WHERE series_id='energy/oil_production' AND e.kind IN ('country','historical')),
            tot AS (SELECT year, sum(value) AS world FROM prod GROUP BY year)
            SELECT p.year,
                   100*sum(CASE WHEN p.entity='USA' THEN value END)/max(t.world) AS usa,
                   100*sum(CASE WHEN p.entity IN {opec} THEN value END)/max(t.world) AS opec,
                   100*sum(CASE WHEN p.entity IN ('RUS','SUN') THEN value END)/max(t.world) AS rus
            FROM prod p JOIN tot t USING (year)
            WHERE p.year >= 1930 GROUP BY p.year ORDER BY p.year""").df()
    return df


def dollar_grip() -> dict:
    """The money lever today: reserve share, foreign UST, swap-line peak."""
    with connect() as con:
        usd = con.execute("""
            SELECT year, value FROM obs
            WHERE series_id='cofer/reserve_share.USD' ORDER BY year""").df()
        tic = con.execute("""
            SELECT year, max(value)/1e12 AS tn FROM obs
            WHERE series_id='tic/us_treasury_holdings' AND entity='WLD'
            GROUP BY year ORDER BY year""").df()
        swaps = con.execute("""
            SELECT year, sum(value)/1e12 AS tn FROM obs
            WHERE series_id='nyfedswaps/notional_lent' GROUP BY year ORDER BY year""").df()
    return {"reserve_share": usd, "foreign_ust": tic, "swaps": swaps}


def sanctions_arc() -> pd.DataFrame:
    """Sanction cases in force by sender, 1950-2015 (EUSANCT)."""
    with connect() as con:
        return con.execute("""
            SELECT year,
                   max(CASE WHEN series_id='sanctions/in_force.US' THEN value END) AS us,
                   max(CASE WHEN series_id='sanctions/in_force.EU' THEN value END) AS eu,
                   max(CASE WHEN series_id='sanctions/in_force.UN' THEN value END) AS un
            FROM obs WHERE series_id LIKE 'sanctions/in_force.%'
            GROUP BY year ORDER BY year""").df()


def sdn_today() -> pd.DataFrame:
    """OFAC designations by target-country program (latest snapshot)."""
    with connect() as con:
        return con.execute("""
            SELECT o.entity, e.name, o.value AS entries
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='sanctions/sdn_designations'
            ORDER BY entries DESC""").df()


def tech_leader_ratio() -> pd.DataFrame:
    """GDP/cap of each era's technological leader vs world, 1700-2022 (Maddison)."""
    with connect() as con:
        df = con.execute("""
            SELECT year, entity, value FROM obs
            WHERE series_id='maddison/gdppc' AND entity IN ('GBR','USA','WLD')
              AND year >= 1700 ORDER BY year""").df()
    wide = df.pivot(index="year", columns="entity", values="value")
    # Maddison has no WLD row: build world avg from gdppc*pop is done in ch01;
    # here leader ratio vs the OTHER leader is the cleaner computed line.
    wide["gbr_over_usa"] = wide["GBR"] / wide["USA"]
    return wide


def wwii_arsenal() -> pd.DataFrame:
    """GDP of the two alliances through WWII (Maddison, 1990 int$)."""
    allies = ("USA", "GBR", "SUN")
    axis = ("DEU", "JPN", "ITA")
    with connect() as con:
        df = con.execute(f"""
            SELECT year,
              sum(CASE WHEN g.entity IN {allies} THEN g.value*p.value END)/1e9 AS allies,
              sum(CASE WHEN g.entity IN {axis} THEN g.value*p.value END)/1e9 AS axis
            FROM (SELECT * FROM obs WHERE series_id='maddison/gdppc') g
            JOIN (SELECT * FROM obs WHERE series_id='maddison/pop') p
              USING (entity, year)
            WHERE year BETWEEN 1935 AND 1950 GROUP BY year ORDER BY year""").df()
    return df


# ---------------------------------------------------------------------------
# Part I figures — the levers that moved the world
# ---------------------------------------------------------------------------

def fig_war_lever() -> None:
    df = world_milex()
    fig, ax = new_fig(
        "The war lever: what the world pays to hold it",
        "Military expenditure, constant 2024 US$ billions (SIPRI). World total meaningful from 1988.",
        "US$bn (constant 2024)")
    for ent, label, color in [("WLD", "World", PALETTE[7]), ("USA", "United States", PALETTE[0]),
                              ("CHN", "China", PALETTE[1]), ("RUS", "Russia", PALETTE[2])]:
        g = df[df.entity == ent]
        ax.plot(g.year, g.bn, label=label, lw=2.2 if ent == "WLD" else 1.6,
                color=color)
    for yr, txt in [(1989, "Cold War ends"), (2001, "9/11"), (2022, "Ukraine")]:
        ax.axvline(yr, color="#57606a", lw=0.7, ls=":", alpha=0.7)
        ax.text(yr, ax.get_ylim()[1] * 0.97, f" {txt}", fontsize=8, color="#57606a",
                rotation=90, va="top")
    ax.legend(loc="upper left")
    us25 = df[(df.entity == "USA")].iloc[-1]
    wl25 = df[(df.entity == "WLD")].iloc[-1]
    print(f"[ch11] milex {int(wl25.year)}: world ${wl25.bn:,.0f}bn, US ${us25.bn:,.0f}bn "
          f"({100*us25.bn/wl25.bn:.0f}%)")
    source_note(ax, "Source: SIPRI Military Expenditure Database (connector: sipri). Constant 2024 US$.")
    save(fig, "11_war_lever")


def fig_arsenal() -> None:
    df = wwii_arsenal()
    fig, ax = new_fig(
        "The arsenal decides: WWII as an economics problem",
        "Combined GDP of the alliances, Maddison 1990 int'l $bn — the Allies out-scale the Axis >2:1.",
        "GDP, 1990 int'l $bn")
    ax.plot(df.year, df.allies, label="Allies (US+UK+USSR)", lw=2, color=PALETTE[0])
    ax.plot(df.year, df.axis, label="Axis (DE+JP+IT)", lw=2, color=PALETTE[1])
    ax.fill_between(df.year, df.axis, df.allies, alpha=0.08, color=PALETTE[0])
    ax.axvspan(1939, 1945, color="#d1242f", alpha=0.06)
    ax.legend(loc="upper left")
    r = df[df.year == 1943].iloc[0]
    print(f"[ch11] 1943 Allies/Axis GDP ratio: {r.allies/r.axis:.1f}x")
    source_note(ax, "Source: Maddison Project 2023 (gdppc x pop). USSR via successor partition caveats in Ch.1.")
    save(fig, "11_arsenal")


def fig_money_lever() -> None:
    gold = real_price("pinksheet/gold")
    v = volcker_window()
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6))
    fig.suptitle("The money lever, pulled twice", x=0.01, ha="left", fontweight="bold")
    g = gold[(gold.year >= 1965) & (gold.year <= 1985)]
    a1.plot(g.year, g.nominal, color=PALETTE[3], lw=2)
    a1.set_title("1971: the dollar leaves gold", fontsize=10, loc="left")
    a1.set_ylabel("Gold, $/oz (nominal)")
    a1.axvline(1971.6, color="#57606a", ls=":", lw=0.8)
    a1.text(1971.8, a1.get_ylim()[1] * 0.75, "Nixon closes\nthe gold window", fontsize=8)
    a1.set_xticks(range(1965, 1986, 5))
    a2.plot(v.year, v.infl, label="CPI inflation %yoy", color=PALETTE[1], lw=1.8)
    a2.plot(v.year, v.gs10, label="10y Treasury %", color=PALETTE[0], lw=1.8)
    a2.set_title("1979-82: Volcker resets the price of money", fontsize=10, loc="left")
    a2.axvspan(1979, 1982, color=PALETTE[0], alpha=0.08)
    a2.legend(fontsize=8)
    for a in (a1, a2):
        a.grid(alpha=0.25)
    gpk = g.loc[g.nominal.idxmax()]
    print(f"[ch11] gold $35 (1970) -> ${gpk.nominal:.0f} ({int(gpk.year)}); "
          f"inflation peak {v.infl.max():.1f}%, 10y peak {v.gs10.max():.1f}%")
    source_note(a1, "Source: World Bank Pink Sheet (gold), Shiller (CPI, GS10). Connectors: pinksheet, shiller.")
    fig.tight_layout()
    save(fig, "11_money_lever")


def fig_energy_lever() -> None:
    oil = real_price("pinksheet/oil")
    fig, ax = new_fig(
        "The oil weapon: the price is the lever",
        "Crude oil, real 2025 US$/bbl (annual avg of monthly Pink Sheet, CPI-deflated).",
        "2025 US$/bbl")
    ax.plot(oil.year, oil.real, lw=2, color=PALETTE[3])
    ax.fill_between(oil.year, 0, oil.real, alpha=0.06, color=PALETTE[3])
    for yr, txt in OIL_EVENTS:
        y = float(oil.loc[(oil.year - yr).abs().idxmin(), "real"])
        ax.annotate(txt, (yr, y), textcoords="offset points", xytext=(0, 14),
                    fontsize=8, ha="center", color="#24292f")
    o73, o74 = (float(oil.loc[oil.year == y, "real"].iloc[0]) for y in (1973, 1974))
    print(f"[ch11] 1973->74 real oil: ${o73:.0f} -> ${o74:.0f} (x{o74/o73:.1f} in one year)")
    source_note(ax, "Source: World Bank Pink Sheet crude average, Shiller CPI. Connectors: pinksheet, shiller.")
    save(fig, "11_energy_lever")


def fig_food_lever() -> None:
    wheat = real_price("pinksheet/wheat")
    rice = real_price("pinksheet/rice")
    fig, ax = new_fig(
        "The food lever: staple grains as an instrument",
        "Real 2025 US$/mt (annual avg, CPI-deflated). Spikes are political as often as agricultural.",
        "2025 US$/mt")
    ax.plot(wheat.year, wheat.real, lw=1.9, label="Wheat (US HRW)", color=PALETTE[3])
    ax.plot(rice.year, rice.real, lw=1.6, label="Rice (Thai 5%)", color=PALETTE[2])
    for yr, txt in WHEAT_EVENTS:
        y = float(wheat.loc[(wheat.year - yr).abs().idxmin(), "real"])
        ax.annotate(txt, (yr, y), textcoords="offset points", xytext=(0, 12),
                    fontsize=8, ha="center")
    ax.legend()
    source_note(ax, "Source: World Bank Pink Sheet, Shiller CPI. Connectors: pinksheet, shiller.")
    save(fig, "11_food_lever")


def fig_sanctions_lever() -> None:
    arc = sanctions_arc()
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), width_ratios=[3, 2])
    fig.suptitle("The blockade becomes paperwork", x=0.01, ha="left", fontweight="bold")
    a1.plot(arc.year, arc.us, label="US sender", color=PALETTE[0], lw=2)
    a1.plot(arc.year, arc.eu, label="EU sender", color=PALETTE[4], lw=1.6)
    a1.plot(arc.year, arc.un, label="UN sender", color=PALETTE[2], lw=1.6)
    a1.set_title("Sanction cases in force, 1950-2015 (EUSANCT)", fontsize=10, loc="left")
    a1.legend(fontsize=8)
    sdn = sdn_today().head(10)
    a2.barh(sdn.name[::-1], sdn.entries[::-1], color=PALETTE[0])
    a2.set_title("OFAC SDN designations today, by program target", fontsize=10, loc="left")
    for a in (a1, a2):
        a.grid(alpha=0.25)
    print(f"[ch11] US cases in force peak {arc.us.max():.0f}; SDN top target "
          f"{sdn.iloc[0]['name']} ({sdn.iloc[0].entries:.0f} entries)")
    source_note(a1, "Source: EUSANCT case-level DB; OFAC SDN list (live). Connector: sanctions.")
    fig.tight_layout()
    save(fig, "11_sanctions_lever")


def fig_tech_lever() -> None:
    wide = tech_leader_ratio()
    fig, ax = new_fig(
        "The technology lever re-ranks nations",
        "GDP per capita, Britain vs the US (Maddison): steam hands the lead to Britain, "
        "electricity & mass production hand it to America.",
        "GBR / USA GDP per capita")
    r = wide["gbr_over_usa"].dropna()
    ax.plot(r.index, r.values, lw=2, color=PALETTE[4])
    ax.axhline(1.0, color="#57606a", lw=0.8, ls="--")
    ax.axvspan(1760, 1840, color=PALETTE[4], alpha=0.06)
    ax.text(1762, ax.get_ylim()[1] * 0.95, "steam", fontsize=8, color="#57606a")
    ax.axvspan(1890, 1930, color=PALETTE[1], alpha=0.06)
    ax.text(1892, ax.get_ylim()[1] * 0.95, "electricity,\nassembly line", fontsize=8, color="#57606a")
    cross = r[r < 1].index.min()
    print(f"[ch11] US passes Britain in GDP/cap: {int(cross)}")
    source_note(ax, "Source: Maddison Project 2023. Connector: maddison.")
    save(fig, "11_tech_lever")


def _table_fig(title: str, cols: list[str], cell: list[list[str]],
               widths: list[float], wraps: list[int], name: str, note: str,
               kind_col: int | None = None) -> None:
    """Render a wrapped-text table figure (both ch11 map figures use this)."""
    import textwrap

    import matplotlib.pyplot as plt
    wrapped = [["\n".join(textwrap.wrap(str(v), w)) for v, w in zip(row, wraps)]
               for row in cell]
    nlines = [max(s.count("\n") + 1 for s in row) for row in wrapped]
    fig, ax = plt.subplots(figsize=(11.5, 0.34 * sum(nlines) + 1.2))
    ax.axis("off")
    ax.set_title(title, loc="left", fontweight="bold", pad=14)
    t = ax.table(cellText=wrapped, colLabels=cols, loc="center", cellLoc="left",
                 colWidths=widths)
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    kind_color = {"state": "#ddf4ff", "private": "#fff8c5", "hybrid": "#ffefe1"}
    for (r, c), cellobj in t.get_celld().items():
        cellobj.set_edgecolor("#d0d7de")
        cellobj.PAD = 0.03
        if r == 0:
            cellobj.set_facecolor("#f6f8fa")
            cellobj.set_text_props(fontweight="bold")
            cellobj.set_height(0.9 / (sum(nlines) + 1))
        else:
            cellobj.set_height(0.9 * nlines[r - 1] / (sum(nlines) + 1))
            if kind_col is not None and c == kind_col:
                cellobj.set_facecolor(kind_color.get(cell[r - 1][kind_col], "white"))
    source_note(ax, note)
    save(fig, name)


def fig_lever_scoreboard() -> None:
    cols = ["Era", "Dominant lever", "Held by", "The signature move"]
    cell = [[e[0], e[1], e[2], e[3]] for e in ERAS]
    _table_fig("Which lever, when — five centuries of dominant levers",
               cols, cell, [0.11, 0.20, 0.24, 0.45], [11, 22, 26, 52],
               "11_lever_scoreboard",
               "Curated from Chs. 1-10 + standard references; numbers AI-panel cross-checked (see chapter).")


# ---------------------------------------------------------------------------
# Part II figures — today's levers and who holds them
# ---------------------------------------------------------------------------

def fig_lever_map() -> None:
    cols = ["Lever", "Held by", "Kind", "Instrument", "Grip", "Basis"]
    cell = [[l[0], l[1], l[2], l[3], l[4], l[5]] for l in LEVER_MAP]
    _table_fig("The lever map, 2026 — who holds what",
               cols, cell, [0.09, 0.17, 0.07, 0.19, 0.31, 0.17],
               [11, 19, 7, 22, 36, 18], "11_lever_map",
               "Computed metrics from connectors noted in Basis; curated rows carry ch10 panel checks.",
               kind_col=2)


def fig_milex_today() -> None:
    df = milex_top(2025, 15)
    fig, ax = new_fig(
        "Who holds the violence lever, 2025",
        "Top 15 military budgets, constant 2024 US$bn (SIPRI); bar labels = share of world total.",
        None)
    colors = [PALETTE[0] if e == "USA" else (PALETTE[1] if e == "CHN" else PALETTE[7])
              for e in df.entity]
    ax.barh(df.name[::-1], df.bn[::-1], color=colors[::-1])
    for i, (bn, sh) in enumerate(zip(df.bn[::-1], df.world_share[::-1])):
        ax.text(bn, i, f"  {sh:.0f}%", va="center", fontsize=8, color="#57606a")
    ax.set_xlabel("US$bn (constant 2024)")
    top = df.iloc[0]
    rest9 = df.iloc[1:10].bn.sum()
    print(f"[ch11] US ${top.bn:,.0f}bn ({top.world_share:.0f}% of world) vs next-9 ${rest9:,.0f}bn")
    source_note(ax, "Source: SIPRI (connector: sipri).")
    save(fig, "11_milex_today")


def fig_dollar_grip() -> None:
    d = dollar_grip()
    import matplotlib.pyplot as plt
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(11.5, 4.2))
    fig.suptitle("The money lever today: three gauges of the dollar's grip",
                 x=0.01, ha="left", fontweight="bold")
    a1.plot(d["reserve_share"].year, d["reserve_share"].value, lw=2, color=PALETTE[0])
    a1.set_title("USD share of FX reserves, %", fontsize=9.5, loc="left")
    a2.plot(d["foreign_ust"].year, d["foreign_ust"].tn, lw=2, color=PALETTE[2])
    a2.set_title("Foreign-held US Treasuries, $tn", fontsize=9.5, loc="left")
    a3.bar(d["swaps"].year, d["swaps"].tn, color=PALETTE[4])
    a3.set_title("Fed swap-line lending, $tn notional/yr", fontsize=9.5, loc="left")
    for a in (a1, a2, a3):
        a.grid(alpha=0.25)
    print(f"[ch11] dollar grip: {d['reserve_share'].value.iloc[-1]:.0f}% reserves, "
          f"${d['foreign_ust'].tn.iloc[-1]:.1f}tn UST abroad")
    source_note(a1, "Sources: IMF COFER, Treasury TIC, NY Fed. Connectors: cofer, tic, nyfedswaps.")
    fig.tight_layout()
    save(fig, "11_dollar_grip")


def fig_energy_today() -> None:
    df = oil_producers()
    fig, ax = new_fig(
        "Who holds the energy lever now",
        "Share of world crude production (OWID/Energy Institute): the weapon migrated — "
        "OPEC's 1970s grip, then shale hands the swing barrel back to Texas.",
        "% of world oil production")
    ax.plot(df.year, df.opec, label="OPEC core", lw=2, color=PALETTE[3])
    ax.plot(df.year, df.usa, label="United States", lw=2, color=PALETTE[0])
    ax.plot(df.year, df.rus, label="Russia/USSR", lw=1.7, color=PALETTE[1])
    ax.axvspan(1973, 1980, color=PALETTE[3], alpha=0.07)
    ax.axvspan(2010, 2024, color=PALETTE[0], alpha=0.05)
    ax.legend()
    last = df.iloc[-1]
    print(f"[ch11] oil {int(last.year)}: OPEC {last.opec:.0f}%, US {last.usa:.0f}%, RUS {last.rus:.0f}%")
    source_note(ax, "Source: Energy Institute via OWID mirror (connector: energy).")
    save(fig, "11_energy_today")


def fig_who_gets_sanctioned() -> None:
    with connect() as con:
        yrs = con.execute("""
            SELECT o.entity, e.name, count(*) AS years_sanctioned, max(o.value) AS peak_cases
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='sanctions/targeted'
            GROUP BY 1,2 ORDER BY years_sanctioned DESC LIMIT 15""").df()
    fig, ax = new_fig(
        "Life under the lever: the most-sanctioned states",
        "Years with at least one EU/US/UN sanction case in force, 1950-2015 (EUSANCT).",
        None)
    ax.barh(yrs.name[::-1], yrs.years_sanctioned[::-1], color=PALETTE[1])
    ax.set_xlabel("Years under sanction, 1950-2015")
    print(f"[ch11] most-sanctioned: {yrs.iloc[0]['name']} ({yrs.iloc[0].years_sanctioned:.0f} years)")
    source_note(ax, "Source: EUSANCT case-level DB (connector: sanctions).")
    save(fig, "11_who_gets_sanctioned")




# ==========================================================================
# Threads 1-5 (2026-07-23): efficacy, coercion, dollar system, arsenal rule,
# erosion rates — computed findings, independently re-derived before merge.
# ==========================================================================


# ----- thread: coercion -----------------------------------------------

# =========================================================================
# PASTE INTO src/econlab/analysis/ch11_levers.py
# (module already imports np, pd, connect, PALETTE, new_fig, save, source_note)
# =========================================================================

# --- 1) add with the other curated constants (after WHEAT_EVENTS) ---------

# Import-dependence blocs for the coercion map (fig 11_coercion_map) — the
# contestability column the F8 lever map lacks: on whom does the lever bite?
# US bloc = the sanctions-capable West — the states that joined the 2022-24
# Russia-sanctions / US export-control coalition (EU27 + G7 + aligned OECD + TWN).
# NOTE: CEPII's BACI country table gives Taiwan ("Other Asia, nes") no ISO3,
# so TWN carries no trade rows — US-bloc shares are understated by exactly
# Taiwan's exports (chips above all).
EU27 = ('AUT', 'BEL', 'BGR', 'HRV', 'CYP', 'CZE', 'DNK', 'EST', 'FIN', 'FRA',
        'DEU', 'GRC', 'HUN', 'IRL', 'ITA', 'LVA', 'LTU', 'LUX', 'MLT', 'NLD',
        'POL', 'PRT', 'ROU', 'SVK', 'SVN', 'ESP', 'SWE')
US_BLOC = ('USA',) + EU27 + ('GBR', 'JPN', 'KOR', 'AUS', 'CAN', 'NOR', 'CHE',
                             'NZL', 'TWN')
CHN_BLOC = ('CHN', 'HKG', 'MAC')


# --- 2) add with the data functions ---------------------------------------

def coercion_map(year: int | None = None, min_bn: float = 5.0) -> pd.DataFrame:
    """Per-importer goods-import shares sourced from each bloc (BACI).

    `year=None` -> latest year in `trade`. `min_bn` (total imports, $bn)
    drops microstates. Djibouti's ISO3 (DJI) is shadowed by the Dow Jones
    instrument slug in `entities`, so the kind filter carves it back in.
    """
    with connect() as con:
        if year is None:
            year = con.execute("SELECT max(year) FROM trade").fetchone()[0]
        df = con.execute(f"""
            SELECT t.importer AS entity,
                   coalesce(CASE WHEN t.importer='DJI' THEN 'Djibouti' END, e.name) AS name,
                   sum(t.value_usd)/1e9 AS total_bn,
                   100*sum(CASE WHEN t.exporter IN {US_BLOC} THEN t.value_usd ELSE 0 END)
                      /sum(t.value_usd) AS us_share,
                   100*sum(CASE WHEN t.exporter IN {CHN_BLOC} THEN t.value_usd ELSE 0 END)
                      /sum(t.value_usd) AS chn_share
            FROM trade t JOIN entities e ON t.importer = e.entity
            WHERE t.year = ? AND (e.kind = 'country' OR t.importer = 'DJI')
            GROUP BY 1, 2 HAVING sum(t.value_usd) >= ? * 1e9
            ORDER BY total_bn DESC""", [year, min_bn]).df()
    df["year"] = year
    df["bloc_member"] = df.entity.isin(US_BLOC + CHN_BLOC)
    return df


def coercion_shift(base_year: int = 2000, min_bn_base: float = 1.0) -> pd.DataFrame:
    """Change in bloc lean (chn_share - us_share) per importer, 2000 -> latest."""
    old = coercion_map(base_year, min_bn_base)
    new = coercion_map()
    mv = old.merge(new, on=["entity", "name"], suffixes=("_0", "_1"))
    mv["lean_0"] = mv.chn_share_0 - mv.us_share_0
    mv["lean_1"] = mv.chn_share_1 - mv.us_share_1
    mv["swing"] = mv.lean_1 - mv.lean_0
    return mv.sort_values("swing", ascending=False)


def bloc_anchor(year: int | None = None) -> dict:
    """World-total goods imports ($tn) and each bloc's supply share (%)."""
    with connect() as con:
        if year is None:
            year = con.execute("SELECT max(year) FROM trade").fetchone()[0]
        tot, us, chn = con.execute(f"""
            SELECT sum(value_usd)/1e12,
                   100*sum(CASE WHEN exporter IN {US_BLOC} THEN value_usd ELSE 0 END)/sum(value_usd),
                   100*sum(CASE WHEN exporter IN {CHN_BLOC} THEN value_usd ELSE 0 END)/sum(value_usd)
            FROM trade WHERE year = ?""", [year]).fetchone()
    return {"year": year, "total_tn": tot, "us": us, "chn": chn}


# --- 3) add with the Part II figures (and fig_coercion_map() to main()) ----

def fig_coercion_map() -> None:
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    df = coercion_map()
    yr = int(df.year.iloc[0])
    a_new, a_old = bloc_anchor(), bloc_anchor(2000)
    third = df[~df.bloc_member]
    cap_us = int((third.us_share > 50).sum())
    cap_ch = int((third.chn_share > 50).sum())
    contested = int((third.us_share.between(20, 40)
                     & third.chn_share.between(20, 40)).sum())

    fig, ax = new_fig(
        "The coercion-dependence map: who can be squeezed",
        f"Goods-import shares sourced from each bloc, {yr} (BACI). Dot size = total imports; "
        "hollow = bloc member. Arrows trace movers from their 2000 position.",
        "Imports from China bloc (CHN+HKG+MAC), %")
    ax.set_xlabel("Imports from US bloc (US+EU27+UK+JP+KR+AU+CA+NO+CH+NZ), %")

    # guides: parity diagonal, captive thresholds, the contested box
    lim = max(df.us_share.max(), df.chn_share.max()) * 1.06
    ax.plot([0, lim], [0, lim], color="#57606a", lw=0.8, ls="--", alpha=0.6)
    ax.axvline(50, color=PALETTE[0], lw=0.7, ls=":", alpha=0.6)
    ax.axhline(50, color=PALETTE[1], lw=0.7, ls=":", alpha=0.6)
    ax.add_patch(Rectangle((20, 20), 20, 20, facecolor=PALETTE[3], alpha=0.08,
                           edgecolor="none"))
    ax.text(39.4, 20.8, "contested", fontsize=8, color=PALETTE[3], ha="right")

    def _color(r):
        if r.us_share > 50:
            return PALETTE[0]
        if r.chn_share > 50:
            return PALETTE[1]
        if 20 <= r.us_share <= 40 and 20 <= r.chn_share <= 40:
            return PALETTE[3]
        return PALETTE[7]

    sz = np.clip(np.sqrt(df.total_bn) * 5, 12, 300)
    members = df[df.bloc_member]
    ax.scatter(third.us_share, third.chn_share, s=sz[third.index],
               c=[_color(r) for r in third.itertuples()], alpha=0.75, lw=0)
    ax.scatter(members.us_share, members.chn_share, s=sz[members.index],
               facecolors="none",
               edgecolors=[PALETTE[1] if e in CHN_BLOC else PALETTE[0]
                           for e in members.entity], lw=1.1, alpha=0.7)

    # arrows: the headline movers, 2000 -> latest
    mv = coercion_shift().set_index("entity")
    for e in ("RUS", "IDN", "THA", "VNM", "PAK", "SAU"):
        if e in mv.index:
            r = mv.loc[e]
            ax.annotate("", (r.us_share_1, r.chn_share_1),
                        (r.us_share_0, r.chn_share_0),
                        arrowprops=dict(arrowstyle="->", color="#57606a",
                                        lw=0.8, alpha=0.4))
    labels = {"RUS": (5, 4), "LBR": (5, -9), "VNM": (5, 4), "IND": (5, 4),
              "IDN": (5, 4), "THA": (5, 4), "ARE": (-8, -11), "SAU": (-26, 2),
              "BRA": (5, 4), "MEX": (5, 4), "PAK": (5, 4), "MNG": (5, 4),
              "IRN": (5, 4), "JPN": (5, 6), "KOR": (6, -5), "USA": (5, 4),
              "CHN": (5, 4), "DEU": (5, 4), "TUR": (5, 4)}
    for e, off in labels.items():
        r = df[df.entity == e]
        if len(r):
            r = r.iloc[0]
            ax.annotate(e, (r.us_share, r.chn_share), textcoords="offset points",
                        xytext=off, fontsize=7.5, color="#24292f")

    handles = [Line2D([], [], marker="o", ls="", color=c, label=l) for c, l in [
        (PALETTE[0], "US-bloc captive (>50%)"), (PALETTE[1], "China-bloc captive (>50%)"),
        (PALETTE[3], "contested (both 20-40%)"), (PALETTE[7], "other")]]
    ax.legend(handles=handles, fontsize=8, loc="upper right")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)

    print(f"[ch11] coercion map {yr}: US bloc supplies {a_new['us']:.0f}% of world imports "
          f"(2000: {a_old['us']:.0f}%), China bloc {a_new['chn']:.0f}% (2000: {a_old['chn']:.0f}%); "
          f"of {len(third)} third countries: {cap_us} US-captive, {cap_ch} China-captive, "
          f"{contested} contested")
    source_note(ax, "Source: CEPII BACI HS92 bilateral goods trade (connector: baci). "
                    "Taiwan absent from BACI's ISO table — US-bloc shares understated.")
    save(fig, "11_coercion_map")


# ----- thread: dollarindex --------------------------------------------

# The dollar-system membership index: tier -> who's in it, and why.
# Swap tiers curated from the Fed record, verified against the NY Fed
# operations file (data/tidy/nyfedswaps/swap_ops.parquet, 2019-2026):
#   core    = permanent standing swap lines (BoC/BoE/BoJ/ECB/SNB — temporary
#             2007-10, made standing Oct 2013; all five appear as counterparties
#             in the ops record; euro-area members ride the ECB line);
#   friend  = the nine temporary lines of Mar 19 2020 (AUS/BRA/DNK/KOR/MEX/NZL/
#             NOR/SGP/SWE — six drew, per the ops record: SGP $24.7bn,
#             KOR $19.9bn, MEX $15.2bn, DNK $8.0bn, NOR $5.4bn, AUS $1.2bn;
#             BRA/SWE/NZL were offered lines but never drew);
#   outside = large TIC-listed holders with no Fed line ever (CHN excluded by
#             design — the PBoC has never had one);
#   targeted = states with an active country-scale OFAC SDN program.
DOLLAR_SYSTEM = [
    ("JPN", "core", "standing swap (BoJ) — heaviest user, $601bn drawn 2019-26"),
    ("GBR", "core", "standing swap (BoE); custody center"),
    ("CHE", "core", "standing swap (SNB); custody center"),
    ("CAN", "core", "standing swap (BoC)"),
    ("FRA", "core", "euro area — ECB standing line"),
    ("BEL", "core", "euro area — ECB line; Euroclear custody"),
    ("LUX", "core", "euro area — ECB line; fund custody"),
    ("IRL", "core", "euro area — ECB line; fund custody"),
    ("SGP", "friend", "2020 temporary line, drew $24.7bn"),
    ("KOR", "friend", "2020 temporary line, drew $19.9bn"),
    ("MEX", "friend", "2020 temporary line, drew $15.2bn"),
    ("DNK", "friend", "2020 temporary line, drew $8.0bn"),
    ("NOR", "friend", "2020 temporary line, drew $5.4bn"),
    ("AUS", "friend", "2020 temporary line, drew $1.2bn"),
    ("BRA", "friend", "2020 line offered, never drew"),
    ("SWE", "friend", "2020 line offered, never drew"),
    ("NZL", "friend", "2020 line offered, never drew"),
    ("CHN", "outside", "no Fed line ever — excluded by design"),
    ("TWN", "outside", "no line (no Fed relationship possible)"),
    ("HKG", "outside", "no line; USD peg run on reserves instead"),
    ("IND", "outside", "no line"),
    ("SAU", "outside", "no line; petrodollar recycling instead"),
    ("ARE", "outside", "no line"),
    ("ISR", "outside", "no line"),
    ("CYM", "outside", "no line; hedge-fund custody center"),
    ("RUS", "targeted", "SDN program; dumped its ~$150bn UST 2014-18"),
    ("IRN", "targeted", "SDN program since 1979"),
    ("PRK", "targeted", "SDN program"),
    ("VEN", "targeted", "SDN program"),
    ("BLR", "targeted", "SDN program"),
    ("CUB", "targeted", "embargoed since 1962"),
    ("MMR", "targeted", "SDN program"),
]


# --- paste after sdn_today() (data functions) -------------------------------

def dollar_system() -> pd.DataFrame:
    """Membership tiers + computed UST holdings (TIC latest) and SDN entries."""
    df = pd.DataFrame(DOLLAR_SYSTEM, columns=["entity", "tier", "note"])
    with connect() as con:
        asof = con.execute(
            "SELECT max(date) FROM obs WHERE series_id='tic/us_treasury_holdings'"
        ).fetchone()[0]
        tic = con.execute("""
            SELECT entity, value/1e9 AS ust_bn FROM obs
            WHERE series_id='tic/us_treasury_holdings' AND date=?""", [asof]).df()
        sdn = con.execute("""
            SELECT entity, value AS sdn FROM obs
            WHERE series_id='sanctions/sdn_designations'""").df()
    df = df.merge(tic, on="entity", how="left").merge(sdn, on="entity", how="left")
    df.attrs["asof"] = pd.Timestamp(asof).strftime("%b %Y")
    df.attrs["world_bn"] = float(tic.loc[tic.entity == "WLD", "ust_bn"].iloc[0])
    df.attrs["floor_bn"] = float(tic[tic.entity != "WLD"].ust_bn.min())
    return df


# --- paste into Part II figures; add fig_dollar_system() to main() ----------

def fig_dollar_system() -> None:
    df = dollar_system()
    wld, floor = df.attrs["world_bn"], df.attrs["floor_bn"]
    rows = ["targeted", "outside", "friend", "core"]
    color = {"core": PALETTE[0], "friend": PALETTE[2],
             "outside": PALETTE[4], "targeted": PALETTE[1]}
    shares = {t: 100 * df[df.tier == t].ust_bn.sum() / wld for t in rows}
    fig, ax = new_fig(
        "The dollar-system membership index",
        f"Fed swap-line tier vs US Treasury holdings (TIC top-20, {df.attrs['asof']}); "
        "targeted markers sized by OFAC SDN entries. Not one targeted state makes the holder list.",
        None)
    fig.set_size_inches(11, 6)
    ax.set_xscale("log")
    band_hi = 80  # unlisted states live in this left band
    tier_y = {t: i for i, t in enumerate(rows)}
    xs, ys = {}, {}
    for tier in rows:
        g = df[df.tier == tier]
        listed = g[g.ust_bn.notna()].sort_values("ust_bn", ascending=False)
        unlisted = g[g.ust_bn.isna()]
        if tier == "targeted":
            unlisted = unlisted.sort_values("sdn", ascending=False)
        pos = np.geomspace(60, 4, max(len(unlisted), 1))
        prev = None
        for _, r in listed.iterrows():
            y = tier_y[tier]
            if prev is not None and abs(np.log10(r.ust_bn) - prev) < 0.035:
                y += 0.13  # dodge near-identical holders (CAN 435.8 vs LUX 436.0)
            prev = np.log10(r.ust_bn)
            xs[r.entity], ys[r.entity] = r.ust_bn, y
        for k, (_, r) in enumerate(unlisted.iterrows()):
            xs[r.entity], ys[r.entity] = pos[k], tier_y[tier]
    ax.axvspan(1.8, band_hi, color="#57606a", alpha=0.06, zorder=0)
    ax.text(band_hi * 0.9, 3.42, f"below the TIC top-20 list (< ${floor:.0f}bn)",
            fontsize=8, color="#57606a", ha="right", style="italic")
    for i, (_, r) in enumerate(df.iterrows()):
        x, y = xs[r.entity], ys[r.entity]
        filled = not np.isnan(r.ust_bn)
        s = 40 + 8 * np.sqrt(r.sdn) if r.tier == "targeted" else 55
        ax.scatter(x, y, s=s, color=color[r.tier] if filled else "white",
                   edgecolor=color[r.tier], linewidth=1.4, zorder=3,
                   alpha=0.9 if filled else 1.0)
        above = i % 2 == 0
        ax.annotate(r.entity, (x, y), textcoords="offset points",
                    xytext=(0, 10 if above else -10), fontsize=7.5,
                    ha="center", va="bottom" if above else "top",
                    color="#24292f", zorder=4)
    ax.annotate("6,815 SDN entries;\ndumped ~$150bn UST after 2014",
                (xs["RUS"], ys["RUS"]), textcoords="offset points",
                xytext=(24, -16), fontsize=8, color=PALETTE[1], ha="left")
    ax.annotate("no swap line —\nexcluded by design",
                (xs["CHN"], ys["CHN"]), textcoords="offset points",
                xytext=(0, -30), fontsize=8, color=PALETTE[4], ha="center")
    ax.set_yticks(range(4))
    ax.set_yticklabels([
        f"Targeted\n(SDN program)\n{shares['targeted']:.0f}% of foreign UST",
        f"Outside\n(no Fed line)\n{shares['outside']:.0f}%",
        f"Friend\n(2020 temp. line)\n{shares['friend']:.0f}%",
        f"Core\n(standing line)\n{shares['core']:.0f}%"], fontsize=9)
    for t, i in tier_y.items():
        ax.axhline(i, color=color[t], lw=0.6, alpha=0.25, zorder=1)
    ax.set_xlabel(f"US Treasury holdings, $bn (log scale) — TIC major foreign holders, {df.attrs['asof']}")
    ax.set_ylim(-0.7, 3.7)
    ax.set_xlim(1.8, 2000)
    ax.set_xticks([10, 100, 1000])
    ax.set_xticklabels(["10", "100", "1,000"])
    ax.grid(axis="x", alpha=0.2)
    ax.grid(axis="y", visible=False)
    h_on = ax.scatter([], [], s=55, color="#57606a", edgecolor="#57606a")
    h_off = ax.scatter([], [], s=55, color="white", edgecolor="#57606a", linewidth=1.4)
    ax.legend([h_on, h_off], ["on the TIC top-20 list", "below the list (position notional)"],
              loc="lower right", fontsize=8, frameon=False)
    core_friend = shares["core"] + shares["friend"]
    print(f"[ch11] dollar system: swap-line perimeter holds {core_friend:.0f}% of "
          f"foreign UST (core {shares['core']:.0f}%), outside {shares['outside']:.0f}%, "
          f"targeted {shares['targeted']:.0f}% — zero on the top-20 list; RUS "
          f"{df.loc[df.entity == 'RUS', 'sdn'].iloc[0]:,.0f} SDN entries")
    source_note(ax, "Sources: NY Fed swap operations, Treasury TIC (top-20 holders; GBR/BEL/LUX/IRL/CHE/CYM "
                    "book custody money), OFAC SDN. Connectors: nyfedswaps, tic, sanctions.")
    save(fig, "11_dollar_system")


# ----- thread: arsenal ------------------------------------------------

# The arsenal rule: major interstate wars of the 20th-21st c. — sides, outcome,
# and the war's `kind` (total = both sides mobilize toward exhaustion; short =
# decided in days-weeks before economic mass can convert; limited = the bigger
# side fights an expeditionary war with capped stakes). GDP ratio computed from
# maddison at `gdp_year` (last well-measured year before/at the decisive
# lineup). Sides list PRINCIPAL belligerents only. winner: 'a'|'b'|'stalemate'|
# 'ongoing'. Codings follow standard histories; contested calls carry a note.
WAR_LEDGER = [
    # (war, start, gdp_year, side_a, ents_a, side_b, ents_b, winner, kind, note)
    ("WWI", 1914, 1913, "Entente", ("GBR", "FRA", "SUN"),
     "Central Powers", ("DEU", "AUT", "HUN", "CSK", "TUR"), "a", "total",
     "metropoles only (no empires); A-H proxied by AUT+HUN+CSK; TUR joined Nov 1914"),
    ("Winter War", 1939, 1939, "USSR", ("SUN",), "Finland", ("FIN",), "a", "total",
     "USSR took the territory it demanded; Finland kept independence (contested)"),
    ("WWII", 1939, 1943, "Allies", ("USA", "GBR", "SUN"),
     "Axis", ("DEU", "JPN", "ITA"), "a", "total",
     "via wwii_arsenal(); Maddison has no SUN rows 1941-45, so the 1943 ratio is USA+GBR only — a LOWER bound"),
    ("Korea", 1950, 1951, "UN (US+ROK+UK)", ("USA", "KOR", "GBR"),
     "China (+DPRK)", ("CHN",), "stalemate", "limited",
     "PRK unmeasured 1944-89 in Maddison; small next to CHN"),
    ("Sino-Indian", 1962, 1962, "China", ("CHN",), "India", ("IND",), "a", "short",
     "one-month border war"),
    ("Vietnam (US phase)", 1965, 1965, "United States", ("USA",),
     "Vietnam", ("VNM",), "b", "limited",
     "VNM = all Vietnam (overstates the North); US never fully mobilized"),
    ("Six-Day", 1967, 1966, "Israel", ("ISR",),
     "Egypt+Syria+Jordan", ("EGY", "SYR", "JOR"), "a", "short", "six days"),
    ("Indo-Pakistani", 1971, 1971, "India", ("IND",), "Pakistan", ("PAK",), "a",
     "short", "13 days"),
    ("Yom Kippur", 1973, 1972, "Egypt+Syria", ("EGY", "SYR"), "Israel", ("ISR",),
     "b", "short",
     "military verdict to Israel; Egypt's political aims met (contested); US airlift resupplied Israel"),
    ("Iran-Iraq", 1980, 1980, "Iran", ("IRN",), "Iraq", ("IRQ",), "stalemate",
     "total", "eight years to a status-quo-ante armistice"),
    ("Falklands", 1982, 1981, "United Kingdom", ("GBR",), "Argentina", ("ARG",),
     "a", "limited", "ten-week expeditionary war"),
    ("Gulf War", 1991, 1990, "Coalition (US+UK+FR+SA)", ("USA", "GBR", "FRA", "SAU"),
     "Iraq", ("IRQ",), "a", "limited",
     "principals of a 35-state coalition; 1990 Iraq GDP already sanctions-dented"),
    ("Kosovo", 1999, 1998, "NATO-5", ("USA", "GBR", "FRA", "DEU", "ITA"),
     "FR Yugoslavia", ("SRB",), "a", "limited",
     "air-only; SRB proxies FRY (excl. tiny MNE)"),
    ("Afghanistan", 2001, 2000, "US+UK", ("USA", "GBR"),
     "Afghanistan (Taliban)", ("AFG",), "b", "limited",
     "Taliban regime fell in weeks; the 20-year war ended in Taliban restoration, 2021"),
    ("Iraq invasion", 2003, 2002, "US+UK", ("USA", "GBR"), "Iraq", ("IRQ",), "a",
     "limited",
     "conventional phase only (regime destroyed in 3 weeks); the insurgency is a different war"),
    ("Russo-Georgian", 2008, 2007, "Russia", ("RUS",), "Georgia", ("GEO",), "a",
     "short", "five days"),
    ("Russia-Ukraine", 2022, 2021, "Russia", ("RUS",), "Ukraine", ("UKR",),
     "ongoing", "total",
     "WDI nominal 2021 GDP (Maddison ends 2022); Western materiel backs Ukraine off-ledger"),
]


# --- data function (place near wwii_arsenal) ---------------------------------

def arsenal_rule() -> pd.DataFrame:
    """GDP ratio of the two sides at the start of each WAR_LEDGER war.

    Maddison gdppc x pop (2011 int'l $) summed per side at gdp_year; the WWII
    row reuses wwii_arsenal(); Russia-Ukraine uses WDI nominal (past Maddison's
    horizon). Raises if any listed belligerent is missing from the panel year
    (silent partial sums are how coalition ratios go wrong).
    """
    ww2 = wwii_arsenal().set_index("year")
    rows = []
    with connect() as con:
        def side(ents: tuple[str, ...], year: int) -> float:
            q = f"""
                SELECT count(*), sum(g.value * p.value) / 1e9
                FROM (SELECT * FROM obs WHERE series_id='maddison/gdppc' AND year=?) g
                JOIN (SELECT * FROM obs WHERE series_id='maddison/pop' AND year=?) p USING (entity)
                WHERE g.entity IN ({','.join('?' * len(ents))})"""
            n, v = con.execute(q, [year, year, *ents]).fetchone()
            if n != len(ents):
                raise ValueError(f"{ents} at {year}: only {n} matched")
            return v

        for war, start, gy, na, ea, nb, eb, winner, kind, note in WAR_LEDGER:
            if war == "WWII":
                ga, gb = float(ww2.loc[gy, "allies"]), float(ww2.loc[gy, "axis"])
            elif war == "Russia-Ukraine":
                nom = ("SELECT value/1e9 FROM obs WHERE "
                       "series_id='wdi/NY.GDP.MKTP.CD' AND entity=? AND year=?")
                ga = con.execute(nom, [ea[0], gy]).fetchone()[0]
                gb = con.execute(nom, [eb[0], gy]).fetchone()[0]
            else:
                ga, gb = side(ea, gy), side(eb, gy)
            ratio = max(ga, gb) / min(ga, gb)
            if winner in ("a", "b"):
                won, lost = (ga, gb) if winner == "a" else (gb, ga)
                outcome = "bigger side won" if won > lost else "smaller side won"
                winner_ratio = won / lost
            else:
                outcome, winner_ratio = winner, np.nan
            rows.append((war, start, gy, na, nb, ga, gb, ratio, winner_ratio,
                         kind, outcome, note))
    return pd.DataFrame(rows, columns=[
        "war", "start", "gdp_year", "side_a", "side_b", "gdp_a", "gdp_b",
        "ratio", "winner_ratio", "kind", "outcome", "note"])


# --- figure (place after fig_arsenal; add fig_arsenal_rule() to main()) ------

def fig_arsenal_rule() -> None:
    df = arsenal_rule()
    fig, ax = new_fig(
        "Does the arsenal always decide? 17 wars on one axis",
        "GDP ratio of the sides at the start of each war (Maddison 2011 int'l $; sums of principal "
        "belligerents). Bars left of 1 = the smaller economy won anyway.",
        None)
    color = {"bigger side won": PALETTE[0], "smaller side won": PALETTE[1],
             "stalemate": PALETTE[7], "ongoing": PALETTE[3]}
    d = df.iloc[::-1]  # chronological top-to-bottom
    x = d.winner_ratio.fillna(d.ratio)  # no-verdict wars plot at bigger/smaller
    labels = [f"{w}  {s}" for w, s in zip(d.war, d.start)]
    ax.barh(labels, x, color=[color[o] for o in d.outcome], log=True)
    ax.axvline(1, color="#57606a", lw=0.9)
    for i, (v, r) in enumerate(zip(x, d.ratio)):
        ax.text(v * 1.18, i, f"{r:,.0f}x" if r >= 10 else f"{r:,.1f}x",
                va="center", ha="left", fontsize=8, color="#57606a")
    ax.set_xlabel("winner's GDP / loser's GDP (log; stalemate & ongoing shown as bigger/smaller)")
    ax.set_xlim(2e-4, 5e3)
    import matplotlib.patches as mpatches
    ax.legend(handles=[mpatches.Patch(color=c, label=l) for l, c in color.items()],
              loc="lower right", fontsize=8)
    dec = df[df.outcome.str.endswith("side won")]
    hits = (df.outcome == "bigger side won").sum()
    tot = df[(df.kind == "total") & df.outcome.str.endswith("side won")]
    print(f"[ch11] arsenal rule: bigger economy won {hits}/{len(dec)} decided wars "
          f"({100 * hits / len(dec):.0f}%); total wars "
          f"{int((tot.outcome == 'bigger side won').sum())}/{len(tot)}; "
          f"upsets: {', '.join(df.loc[df.outcome == 'smaller side won', 'war'])}")
    source_note(ax, "Source: Maddison Project 2023 (gdppc x pop, 2011 int'l $); Russia-Ukraine via WDI nominal 2021. "
                    "Sides & outcomes: standard histories (see WAR_LEDGER notes).")
    save(fig, "11_arsenal_rule")


# ----- thread: erosion ------------------------------------------------

#     connect, PALETTE, new_fig, save, source_note, and reuses oil_producers) ---

# Contestability panel: window for the 25-year erosion fit and the recent check.
EROSION_START, EROSION_RECENT = 2000, 2015

# The plumbing has no share series to fit — curated row for the erosion figure.
# 11 CBs / $1.09tn computed from data/tidy/nyfedswaps/swap_ops.parquet (2020);
# 5 standing lines = ECB/BoJ/BoE/SNB/BoC, still drawing weekly ops in 2026;
# CNY 2.0% from cofer/reserve_share.CNY (2025). GFC-era network of 14 CBs: Fed history.
EROSION_PLUMBING = ("Fed swap network: 11 CBs drew $1.09tn in 2020; 5 standing lines "
                    "still operate in 2026 — no rival exists (CNY = 2.0% of reserves)")


def erosion_series() -> dict[str, pd.DataFrame]:
    """Lever-grip shares as (year, share%) series — the contestability panel.

    Reserves  cofer/reserve_share.USD (1995->)
    Milex     sipri USA / WLD, constant-$ (1988->)
    UST held abroad  TIC WLD (ticarchive 2002-21 + tic 2025-> splice) over
                     fiscaldata/debt_outstanding — % of federal debt held abroad
    OPEC oil  reuses oil_producers() (OPEC-core share, 1965->)
    GDP       maddison gdppc*pop, kind='country' (PPP-flavoured 2011 int$)
    Imports   BACI: USA imports / world imports (1995->)
    """
    with connect() as con:
        usd = con.execute("""
            SELECT year, value AS share FROM obs
            WHERE series_id='cofer/reserve_share.USD' ORDER BY year""").df()
        mil = con.execute("""
            SELECT year,
                   100*max(CASE WHEN entity='USA' THEN value END)
                      /max(CASE WHEN entity='WLD' THEN value END) AS share
            FROM obs WHERE series_id='sipri/milex_constusd' AND entity IN ('USA','WLD')
            GROUP BY year HAVING share IS NOT NULL ORDER BY year""").df()
        ust = con.execute("""
            WITH fh AS (
              SELECT year, max(value) AS held FROM obs
              WHERE series_id IN ('ticarchive/holdings','tic/us_treasury_holdings')
                AND entity='WLD' GROUP BY year)
            SELECT f.year, 100*f.held/d.value AS share
            FROM fh f JOIN (SELECT year, value FROM obs
                            WHERE series_id='fiscaldata/debt_outstanding') d USING (year)
            ORDER BY year""").df()
        gdp = con.execute("""
            WITH g AS (
              SELECT o.year, o.entity, o.value*p.value AS gdp
              FROM (SELECT * FROM obs WHERE series_id='maddison/gdppc') o
              JOIN (SELECT * FROM obs WHERE series_id='maddison/pop') p
                USING (entity, year)
              JOIN entities e ON e.entity=o.entity WHERE e.kind='country')
            SELECT year, 100*sum(CASE WHEN entity='USA' THEN gdp END)/sum(gdp) AS share
            FROM g WHERE year >= 1950 GROUP BY year ORDER BY year""").df()
        imp = con.execute("""
            SELECT year,
                   100*sum(CASE WHEN importer='USA' THEN value_usd END)/sum(value_usd) AS share
            FROM trade GROUP BY year ORDER BY year""").df()
    opec = oil_producers()[["year", "opec"]].rename(columns={"opec": "share"})
    opec = opec[opec.year >= 1965].reset_index(drop=True)
    return {"Money (reserve share)": usd, "Violence (milex share)": mil,
            "Money (UST held abroad)": ust, "Energy (OPEC-core oil)": opec,
            "Scale (GDP share, PPP)": gdp, "Trade (import share)": imp}


def erosion_rates(start: int = EROSION_START, recent: int = EROSION_RECENT) -> pd.DataFrame:
    """The erosion table: then->now, OLS pts/decade (25y + recent), verdict."""
    def fit(d: pd.DataFrame, y0: int) -> float:
        d = d[(d.year >= y0) & d.share.notna()]
        return float(np.polyfit(d.year, d.share, 1)[0] * 10)

    rows = []
    for lever, df in erosion_series().items():
        d = df[(df.year >= start) & df.share.notna()]
        s25, s10 = fit(df, start), fit(df, recent)
        if s25 > 1 and s10 < -1:
            verdict = "hump - now eroding"
        elif s25 <= -3:
            verdict = "eroding fast"
        elif s25 <= -1:
            verdict = "eroding slowly"
        elif s25 < 1:
            verdict = "stable"
        else:
            verdict = "strengthening"
        rows.append((lever, int(d.year.iloc[0]), d.share.iloc[0],
                     int(d.year.iloc[-1]), d.share.iloc[-1], s25, s10, verdict))
    return pd.DataFrame(rows, columns=["lever", "y0", "then", "y1", "now",
                                       "pts_decade", "pts_decade_recent", "verdict"])


def fig_erosion_rates() -> None:
    rates, series = erosion_rates(), erosion_series()
    fig, ax = new_fig(
        "Contestability is a rate: how fast each grip actually slips",
        "Drift of each US/incumbent lever share since 2000, percentage points "
        "(first year = 0); labels = OLS slope 2000->latest.",
        "pts drift since 2000")
    ends = []
    for (_, r), color in zip(rates.iterrows(), PALETTE):
        d = series[r.lever]
        d = d[(d.year >= EROSION_START) & d.share.notna()]
        drift = d.share - d.share.iloc[0]
        ax.plot(d.year, drift, lw=1.9, color=color)
        ends.append([float(drift.iloc[-1]), float(d.year.iloc[-1]), r, color])
    ends.sort(key=lambda e: e[0], reverse=True)   # stagger clustered right labels
    for i in range(1, len(ends)):
        ends[i][0] = min(ends[i][0], ends[i - 1][0] - 1.7)
    for y, yr, r, color in ends:
        ax.annotate(f"{r.lever}  {r.pts_decade:+.1f}/dec ({r.verdict})",
                    (yr, y), textcoords="offset points", xytext=(6, 0),
                    fontsize=8, va="center", color=color)
    ax.axhline(0, color="#57606a", lw=0.8, ls="--")
    ax.set_xlim(EROSION_START, 2037)              # room for the labels
    ax.set_ylim(min(e[0] for e in ends) - 5, None)
    ax.text(0.015, 0.03, f"The no-slope row: {EROSION_PLUMBING}.",
            transform=ax.transAxes, fontsize=8, color="#57606a",
            bbox=dict(boxstyle="round,pad=0.4", fc="#f6f8fa", ec="#d0d7de"))
    t = rates.set_index("lever")
    print(f"[ch11] erosion pts/dec 2000->: reserves {t.loc['Money (reserve share)','pts_decade']:+.1f}, "
          f"milex {t.loc['Violence (milex share)','pts_decade']:+.1f}, "
          f"UST-abroad {t.loc['Money (UST held abroad)','pts_decade']:+.1f} "
          f"(recent {t.loc['Money (UST held abroad)','pts_decade_recent']:+.1f}), "
          f"OPEC {t.loc['Energy (OPEC-core oil)','pts_decade']:+.1f}, "
          f"GDP {t.loc['Scale (GDP share, PPP)','pts_decade']:+.1f}, "
          f"imports {t.loc['Trade (import share)','pts_decade']:+.1f}")
    source_note(ax, "Sources: IMF COFER, SIPRI, TIC + FiscalData, Energy Institute/OWID, "
                    "Maddison, BACI. Connectors: cofer, sipri, tic+ticarchive+fiscaldata, energy, maddison, baci.")
    save(fig, "11_erosion_rates")

# --- and register in main(): add `fig_erosion_rates()` after fig_who_gets_sanctioned() ---


# ----- thread: efficacy -----------------------------------------------

# --- data function: place with the other ch11 data functions (after sdn_today) ---

EUSANCT_END = 2015  # EUSANCT coverage horizon: open-ended cases censored here


def sanctions_efficacy() -> pd.DataFrame:
    """EUSANCT imposed cases (n=209) with outcome and covariate cuts.

    Outcome `win` = EUSANCT `sanctions_success`: coded 1 exactly when the
    case's finaloutcome is 6/7 (target concession or negotiated settlement
    after imposition), 0 for 8-11 (sender capitulation, stalemate, ongoing).
    The episode-level `success` column agrees in 208/209 cases. Target GDP at
    imposition joins Maddison gdppc x pop (2011 int'l $), latest year within
    5 years before the start year.
    """
    from ..config import TIDY

    c = pd.read_parquet(TIDY / "sanctions" / "sanction_cases.parquet").copy()
    c["win"] = c["sanctions_success"].astype(float)

    # (a) sender coalition, mutually exclusive
    c["n_senders"] = c["senders"].str.count("-") + 1
    c["coalition"] = np.select(
        [c["senders"] == "US", c["n_senders"] == 1, c["n_senders"] == 2],
        ["US alone", "EU or UN alone", "Two senders"], default="US+EU+UN")

    # (b) duration; open-ended cases censored at the panel horizon
    c["censored"] = c["end"].isna()
    c["dur"] = c["end"].fillna(EUSANCT_END) - c["start"]
    c["dur_b"] = pd.cut(c["dur"], [-1, 1, 4, 14, np.inf],
                        labels=["<2 yr", "2-5 yr", "5-15 yr", "15+ yr"])

    # (c) target economy size at imposition (Maddison, 2011 int'l $)
    with connect() as con:
        mad = con.execute("""
            SELECT g.entity, g.year, g.value * p.value AS gdp
            FROM (SELECT * FROM obs WHERE series_id='maddison/gdppc') g
            JOIN (SELECT * FROM obs WHERE series_id='maddison/pop') p
              USING (entity, year)
            WHERE g.year >= 1945 ORDER BY entity, year""").df()
    lookup = {(e, y): v for e, y, v in mad.itertuples(index=False)}

    def gdp_at(entity, year):
        if pd.isna(entity):
            return np.nan
        for y in range(int(year), int(year) - 6, -1):
            if (entity, y) in lookup:
                return lookup[(entity, y)]
        return np.nan

    c["gdp"] = [gdp_at(e, y) for e, y in zip(c["entity"], c["start"])]
    matched = c["gdp"].notna()
    c.loc[matched, "size_q"] = pd.qcut(
        c.loc[matched, "gdp"], 4,
        labels=["Q1 smallest", "Q2", "Q3", "Q4 largest"])

    # (d) era of imposition
    c["era"] = pd.cut(c["start"], [0, 1989, 2000, 2100],
                      labels=["Cold War (-1989)", "1990s (1990-2000)",
                              "Post-2001 (2001-15)"])
    return c


# --- figure: place after fig_who_gets_sanctioned(); add fig_sanctions_efficacy()
# --- to main() right after fig_who_gets_sanctioned() ---

def fig_sanctions_efficacy() -> None:
    c = sanctions_efficacy()

    def rates(col, order):
        g = c.dropna(subset=[col]).groupby(col, observed=True)["win"]
        return [(str(k), 100 * g.mean()[k], int(g.count()[k])) for k in order]

    blocks = [
        ("Sender coalition", PALETTE[0], rates(
            "coalition", ["US alone", "EU or UN alone", "Two senders", "US+EU+UN"])),
        ("Duration", PALETTE[3], rates(
            "dur_b", ["<2 yr", "2-5 yr", "5-15 yr", "15+ yr"])),
        ("Target GDP at start", PALETTE[2], rates(
            "size_q", ["Q1 smallest", "Q2", "Q3", "Q4 largest"])),
        ("Era imposed", PALETTE[4], rates(
            "era", ["Cold War (-1989)", "1990s (1990-2000)", "Post-2001 (2001-15)"])),
    ]

    overall = 100 * c["win"].mean()
    fig, ax = new_fig(
        "Reliably impoverish, unreliably persuade — computed",
        "Share of imposed sanction cases ending in target concession/settlement "
        "(EUSANCT, 209 cases 1950-2015). Dashed line = all cases.",
        None)
    fig.set_size_inches(10, 7.2)
    ys, labels, y = [], [], 0
    for name, color, rows in blocks:
        ax.text(0, y, name, fontweight="bold", fontsize=9.5, va="center",
                color="#24292f")
        y -= 1
        for label, rate, n in rows:
            ax.plot([0, rate], [y, y], color=color, lw=1.1, alpha=0.35)
            ax.scatter(rate, y, s=60, color=color, zorder=3)
            ax.text(rate + 1.5, y, f"{rate:.0f}%  (n={n})", fontsize=8,
                    va="center", color="#57606a")
            ys.append(y)
            labels.append(label)
            y -= 1
        y -= 0.6  # gap between blocks
    ax.axvline(overall, color="#57606a", ls="--", lw=0.9)
    ax.text(overall + 1, y + 0.7, f"all cases {overall:.0f}%", fontsize=8,
            color="#57606a")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Success rate, % of cases")
    ax.grid(axis="y", alpha=0)

    uni = c[c.n_senders == 1]
    multi = c[c.n_senders >= 2]
    print(f"[ch11] sanctions efficacy: overall {overall:.0f}%; unilateral "
          f"{100*uni.win.mean():.0f}% vs multilateral {100*multi.win.mean():.0f}%; "
          f"smallest-quartile targets {100*c[c.size_q=='Q1 smallest'].win.mean():.0f}% "
          f"vs largest {100*c[c.size_q=='Q4 largest'].win.mean():.0f}%; "
          f"never-ended cases {100*c[c.censored].win.mean():.0f}%")
    source_note(ax, "Source: EUSANCT case-level DB (success = finaloutcome 6/7); "
                    "target GDP from Maddison gdppc x pop. Connectors: sanctions, maddison.")
    save(fig, "11_sanctions_efficacy")




# ==========================================================================
# Threads 7-13 figures + curated tables 15-17 (2026-07-23)
# ==========================================================================


# ---------------------------------------------------------------------------
# RESERVE CURRENCIES BEFORE COFER — the sterling->dollar succession, 1899-1994.
# Curated anchor points, each row cited in-row. Bridges to the warehouse COFER
# series (cofer/reserve_share.*, 1995->).
#
# UNITS: share_pct = % of KNOWN/IDENTIFIED official foreign-exchange holdings,
# NOT of total reserves. Gold dominated until ~1970: FX was ~20% of official
# reserves in 1913 (Lindert), swung 8-42% interwar (E&F), and passed gold for
# good only in 1970 (Schenk).
#
# CONVENTION BREAKS (flagged per row):
#  * 1899/1913: shares computed from Lindert's dollar amounts over KNOWN
#    official holdings; ~1/3 of official FX was unallocated by currency.
#  * 1924/1928/1938: scholarly reconstructions/estimates, not census data.
#  * 1970: derived from IMF AR 1976 Table 15 (incl. identified Eurodollars).
#  * 1973-1994: IMF Annual Report share tables; the 1980-1994 rows use the
#    IMF's headline convention counting ECUs issued against dollars as dollars.
#  * BRIDGE WARNING: warehouse cofer/reserve_share.USD opens 1995 at 73.5% of
#    allocated reserves — overstated pre-1999 because the legacy-euro
#    currencies (DEM/FRF/NLG/ECU, ~22% of identified holdings in 1994) are
#    absent from its denominator; the IMF's own end-1995 print is ~58-59% USD.
#
# Sources: Lindert (1969) Tab.3; Eichengreen & Flandreau (2009) [E&F];
# Eichengreen, Chitu & Mehl (2014, ECB WP 1715) [ECM]; Triffin (1968);
# Schenk (2009; 2010, The Decline of Sterling); IMF Annual Reports 1976
# (Tab.15), 1981 (Tab.20), 1991 (Tab.1.2), 1995 (Tab.I.2); IMF COFER.
# ---------------------------------------------------------------------------
RESERVE_SUCCESSION = [
    # (year, currency, share_pct, source)
    (1899, "GBP", 63.4, "Lindert 1969 Tab.3: $105.1M of $165.9M known official FX"),
    (1899, "FRF", 16.4, "Lindert 1969 Tab.3: $27.2M/$165.9M"),
    (1899, "DEM", 14.6, "Lindert 1969 Tab.3 (marks): $24.2M/$165.9M"),
    (1913, "GBP", 47.7, "Lindert 1969 Tab.3: $425.4M of $892.7M known official FX"),
    (1913, "FRF", 30.8, "Lindert 1969 Tab.3: $275.1M/$892.7M (Russian balances in Paris)"),
    (1913, "DEM", 15.3, "Lindert 1969 Tab.3 (marks): $136.9M/$892.7M"),
    (1924, "USD", 40.0, "approx — E&F 2009: USD passes GBP ~1924; ECM 2014: 'each roughly 40%' in the 1920s"),
    (1924, "GBP", 40.0, "approx — E&F 2009 / ECM 2014 (see USD row)"),
    (1928, "USD", 43.0, "approx — Fed Board 1928: ~$1.0bn of ~$2.3bn global FX, endorsed by E&F 2009"),
    (1938, "GBP", 70.0, "Triffin 1968 estimate (via E&F 2009) — of an FX pool collapsed to ~8% of reserves"),
    (1947, "GBP", 87.0, "IMF estimate, via Schenk 2010 — mostly blocked wartime sterling balances"),
    (1950, "GBP", 55.0, "Schenk 2010: 'over 55%' of world FX reserves"),
    (1965, "GBP", 30.0, "Schenk 2010: 'close to 30%', stable through the 1960s despite 1967 devaluation"),
    (1970, "USD", 75.3, "derived, IMF AR1976 Tab.15: (US claims 23.8 + Eurodollars 10.4)/45.4 SDR bn"),
    (1970, "GBP", 12.6, "derived, IMF AR1976 Tab.15: 5.7/45.4 SDR bn (Schenk's SDR series: 15%)"),
    (1973, "USD", 84.5, "IMF AR1981 Tab.20 (1973:Q1)"),
    (1973, "GBP",  5.9, "IMF AR1981 Tab.20 (1973:Q1)"),
    (1973, "DEM",  6.7, "IMF AR1981 Tab.20 (1973:Q1)"),
    (1976, "USD", 86.7, "IMF AR1981 Tab.20 (1976:Q4) — the dollar's identified-share peak"),
    (1976, "GBP",  2.1, "IMF AR1981 Tab.20 (1976:Q4)"),
    (1980, "USD", 73.1, "IMF AR1981 Tab.20 (1980:Q4; ECU-vs-USD swaps counted as USD)"),
    (1980, "GBP",  3.0, "IMF AR1981 Tab.20 (1980:Q4, ex-ECU column)"),
    (1980, "DEM", 14.0, "IMF AR1981 Tab.20 (1980:Q4, ex-ECU column)"),
    (1985, "USD", 65.0, "IMF AR1991 Tab.1.2 (ECU-vs-USD as USD; 55.3% if ECU separate, AR1995)"),
    (1985, "GBP",  3.0, "IMF AR1991 Tab.1.2"),
    (1985, "DEM", 15.2, "IMF AR1991 Tab.1.2"),
    (1985, "JPY",  8.0, "IMF AR1991 Tab.1.2"),
    (1990, "USD", 56.4, "IMF AR1991 Tab.1.2 (49.1% if ECU separate, AR1995)"),
    (1990, "GBP",  3.2, "IMF AR1991 Tab.1.2"),
    (1990, "DEM", 19.7, "IMF AR1991 Tab.1.2"),
    (1990, "JPY",  9.1, "IMF AR1991 Tab.1.2"),
    (1994, "USD", 63.3, "IMF AR1995 Tab.I.2 memo col. (ECU-vs-USD as USD; 57.1% if ECU separate)"),
    (1994, "GBP",  3.6, "IMF AR1995 Tab.I.2"),
    (1994, "DEM", 14.8, "IMF AR1995 Tab.I.2"),
    (1994, "JPY",  8.1, "IMF AR1995 Tab.I.2"),
    # ---- bridge: warehouse COFER series takes over at 1995 ----
    # Official IMF COFER end-1995: USD ~58-59% of allocated reserves; the
    # warehouse's 73.5% is a pre-1999 denominator artifact (see header).
]

# Narrative waypoints for annotating the figure.
RESERVE_SUCCESSION_EVENTS = [
    (1872, "US passes UK in total GDP (Maddison; warehouse crossover 1860s-1872)"),
    (1914, "WWI: Britain's creditor position liquidated; New York opens for business"),
    (1924, "USD first passes GBP in reserves (E&F 2009)"),
    (1928, "GBP briefly re-led on the Bank of France's sterling hoard (E&F 2009)"),
    (1931, "UK leaves gold; gold bloc dumps sterling AND dollars"),
    (1933, "US devalues; GBP regains the reserve lead through the late 1930s (E&F 2009)"),
    (1944, "Bretton Woods: USD formally the system's anchor"),
    (1955, "USD durably passes GBP (Schenk 2010: ~1955; ECM 2014: early 1950s)"),
    (1968, "Sterling Agreements: UK guarantees dollar value of GBP reserves to slow the exit"),
    (1976, "Sterling crisis; 1977 facility ends GBP's reserve role (Schenk 2010)"),
    (1999, "Euro absorbs DEM/FRF/NLG/ECU; COFER convention break"),
]


# =====================================================================
# Item 16 — NUCLEAR WARHEADS (the 1945-1971 era lever)
#
# Definitions (used consistently):
#   * "Military stockpile"  = warheads in military custody assigned to
#     operational forces (deployed + reserve). USA/USSR columns below.
#   * "Total inventory"     = stockpile + retired warheads intact and
#     awaiting dismantlement. The world column below, and NUCLEAR_TODAY.
#   Jan 2026 world: total inventory 12,187; military stockpiles 9,745;
#   deployed 4,012; ~2,100-2,200 on high alert (SIPRI YB 2026 ch.8).
#
# Sources:
#   [FAS26]  FAS "Status of World Nuclear Forces" (Kristensen, Korda,
#            Johns, Knight-Boyle, Kohn), estimates as of early 2026.
#            https://fas.org/initiative/status-world-nuclear-forces/
#   [SIPRI26] SIPRI Yearbook 2026, ch. 8 "World Nuclear Forces"
#            (Kristensen & Korda), table 8A.1 (Jan 2026) — numerically
#            identical to [FAS26]; same authors.
#   [NK10]   Norris & Kristensen, "Global nuclear weapons inventories,
#            1945-2010", Bull. Atomic Scientists 66(4), 2010 — US peak
#            31,255 (1967, official DOD declassified); Soviet 1986 in
#            that vintage: 45,000.
#   [OWID26] FAS historical series, machine-readable mirror at Our
#            World in Data "nuclear-warhead-stockpiles" (retrieved
#            2026-07-22). Country cols = stockpiles; World col = total
#            inventory (incl. retired) -> world > US+USSR+others.
#   [CRS25]  CRS In Focus IF12735, "U.S. Extended Deterrence and
#            Regional Nuclear Capabilities", current version 2026-07-10.
#
# Caveats: all figures are ESTIMATES, not counts (arsenals are state
# secrets); Soviet 1986 peak is 40,159 in the current FAS series but
# 45,000 in [NK10] — treat as ~40,000-45,000. 1945 world anchored at
# the canonical 2 [NK10] (the OWID world-inventory col shows 6).
# ---------------------------------------------------------------------

# (year, world_total_inventory, usa_stockpile, ussr_rus_stockpile, source)
NUCLEAR_ARC = [
    (1945,      2,      2,      0, "Norris & Kristensen, BAS 2010"),
    (1950,    374,    299,      5, "FAS series via OWID 2026"),
    (1955,  3_267,  2_422,    200, "FAS series via OWID 2026"),
    (1960, 22_144, 18_638,  1_627, "FAS series via OWID 2026"),
    (1965, 38_419, 31_139,  6_144, "FAS series via OWID 2026"),
    (1967, 39_990, 31_255,  8_400, "US peak (DOD declassified; N&K BAS 2010)"),
    (1970, 38_799, 26_008, 11_736, "FAS series via OWID 2026"),
    (1975, 47_769, 27_519, 19_235, "FAS series via OWID 2026"),
    (1980, 55_352, 24_104, 30_665, "FAS series via OWID 2026"),
    (1986, 70_374, 23_317, 40_159, "world+USSR peak (FAS ~70,300; N&K 2010: USSR 45,000)"),
    (1990, 61_229, 21_392, 32_980, "FAS series via OWID 2026"),
    (1995, 42_366, 10_904, 18_179, "FAS series via OWID 2026"),
    (2000, 34_004, 10_577, 12_188, "FAS series via OWID 2026"),
    (2005, 28_358,  8_360,  7_000, "FAS series via OWID 2026"),
    (2010, 21_234,  5_066,  5_215, "FAS series via OWID 2026"),
    (2015, 15_795,  4_571,  4_500, "FAS series via OWID 2026"),
    (2020, 13_145,  3_750,  4_310, "FAS series via OWID 2026"),
    (2026, 12_187,  3_700,  4_400, "FAS 2026 = SIPRI YB 2026 t.8A.1 (Jan 2026)"),
]

# (country_iso3, total_inventory_jan2026, source) — total inventory incl.
# retired-awaiting-dismantlement. Military stockpiles where different:
# RUS 4,400 (+1,020 retired) · USA 3,700 (+1,342) · FRA 290 (+80).
# Sums to 12,187 exactly. FAS 2026 and SIPRI YB 2026 table 8A.1 agree.
NUCLEAR_TODAY = [
    ("RUS", 5_420, "FAS 2026 / SIPRI YB 2026"),
    ("USA", 5_042, "FAS 2026 / SIPRI YB 2026"),
    ("CHN",   620, "FAS 2026 / SIPRI YB 2026 (DoD: ~1,000 operational by 2030)"),
    ("FRA",   370, "FAS 2026 / SIPRI YB 2026 (290 stockpile + 80 retired)"),
    ("GBR",   225, "FAS 2026 / SIPRI YB 2026"),
    ("IND",   190, "FAS 2026 / SIPRI YB 2026"),
    ("PAK",   170, "FAS 2026 / SIPRI YB 2026"),
    ("ISR",    90, "FAS 2026 / SIPRI YB 2026 (high uncertainty)"),
    ("PRK",    60, "FAS 2026 / SIPRI YB 2026 (high uncertainty)"),
]

# China stockpile trajectory — fastest-growing arsenal [FAS/OWID 2026]
NUCLEAR_CHN_TRAJECTORY = [
    (2019, 290), (2020, 350), (2021, 370), (2022, 390),
    (2023, 410), (2024, 500), (2025, 600), (2026, 620),
]

# The umbrella: states under US extended deterrence ("nuclear umbrella").
# 31 non-US NATO members (NATO = 32 incl. USA since Sweden, 2024)
# + Japan + South Korea + Australia = 34. Official phrasing: "over 30
# U.S. 'allies and partners'" [CRS25, quoting stated US policy].
NUCLEAR_UMBRELLA_STATES = (
    34, "31 non-US NATO + JPN, KOR, AUS; CRS IF12735 (2025): 'over 30 allies and partners'"
)

# Cumulative production & cost of the lever:
#  >128,000 warheads built since 1945 — USA 55%, USSR/Russia 43% [FAS26]
#  US program cost 1940-96: $5.48T constant-1996 USD (~$5.8T incl.
#  projected cleanup/dismantlement) — Schwartz, Atomic Audit, Brookings 1998
NUCLEAR_CUMULATIVE_BUILT = 128_000        # Kristensen & Norris, BAS 69(5) 2013, lower bound
NUCLEAR_US_COST_1940_96_T1996USD = 5.48   # Schwartz/Brookings 1998

# ---------------------------------------------------------------------------
# Appendix — the intangible levers, proxied (religion / ideology / narrative).
# These levers are real but unmeasured; every row below is a PROXY — reach or
# installed base, never persuasion or belief intensity — and each row names
# what its proxy misses. Sources in-row; ranges given where authorities
# disagree (they do, and the gaps are part of the lesson).
# Sources: Meta Q1 2026 results (DAP quote verified); Reuters/CNBC Sep 2025
# (Instagram 3B); Tencent Q1 2026 (WeChat); Google 2023 (last official YouTube
# logged-in figure) + third-party est. 2026; Statista/DataReportal (TikTok
# est.); StatCounter 2026 (search); Nielsen via Pew Network News Fact Sheet
# (1980 vs 2022); Noam, *Media Ownership and Concentration in America* (OUP
# 2009); Free Press pay-TV census; Medill *State of Local News 2025*;
# Bloomberg/CNBC Mar 2026 (Nexstar–TEGNA close + judicial stay); Pew *Global
# Religious Landscape* Jun 2025 (2020 data); World Christian Database (Zurlo &
# Johnson, Jan 2025); Agenzia Fides Oct 2025 (2023 data); Pew RLS 2023-24;
# Pew *Age Gap in Religion* 2018; Pew *Being Christian in W. Europe* 2018.

# (a) ATTENTION — who intermediates it.
#     (channel, reach, as-of, source, proxy limit)
ATTENTION = [
    ("Meta family (FB/IG/WhatsApp/Messenger)",
     "3.56B daily active people (+4% y/y) — ~43% of humanity, every day",
     "Mar 2026", "Meta Q1 2026 results",
     "company-defined dedup; a daily login is not a changed mind"),
    ("Instagram", "3.0B monthly actives", "Sep 2025",
     "Zuckerberg announcement (Reuters/CNBC)", "company claim, not audited"),
    ("YouTube", "~2.5-2.9B monthly (third-party est.)", "2026",
     "est. (Statista/DataReportal); Google last confirmed 2B+ logged-in monthly (2023)",
     "no official MAU series exists; estimates spread ~15%"),
    ("TikTok", "~1.6-2.0B monthly (est.); last official figure 1B (Sep 2021)",
     "2025-26",
     "Statista 1.59B (early 2025); DataReportal ad reach 1.94B (Oct 2025)",
     "company silent since 2021; ad reach counts accounts, not people"),
    ("WeChat/Weixin", "1.43B monthly actives", "Q1 2026",
     "Tencent Q1 2026 results",
     "near-universal inside China; the only non-US platform at this scale"),
    ("Google search", "~90% of worldwide search referrals", "H1 2026",
     "StatCounter (90.0-90.4% in 2026; dipped below 90% late 2024, first time since 2015)",
     "referral-share methodology; misses in-app and AI-assistant search"),
    ("TV-era anchor: US network evening news",
     "52.1M nightly in 1980 (~23% of all Americans) -> ~19M in 2022 (~6%)",
     "1980 vs 2022", "Nielsen via Pew Network News Fact Sheet",
     "the old chokepoint, for scale: three anchors once briefed a quarter of the nation nightly"),
]

# (b) NARRATIVE — who owns the pipes.
#     (row, number, as-of, source, status / proxy limit)
NARRATIVE = [
    ("Folk claim: '6 companies control 90% of US media'",
     "UNSUPPORTED at that breadth — we cut it",
     "2012-era meme",
     "traces to Bagdikian's *Media Monopoly* lineage + a 2012 Business Insider graphic",
     "no scholarship supports 90% economy-wide; sector-level concentration is real (next rows)"),
    ("What scholarship supports: top-5 firms' share of US mass-media revenue",
     "13% (1984) -> 26% (2005) — rising, not hegemonic",
     "2005 (latest comparable)",
     "Noam, Media Ownership and Concentration in America (OUP 2009)",
     "revenue share across ~100 media industries; Buckweitz & Noam extend the series to 2022 (GMIC USA report, 2024) — direction holds"),
    ("Where the big-6 claim nearly held: pay-TV channels",
     "big six held stakes in 143 of 184 channels (~77%)",
     "mid-2010s", "Free Press channel census",
     "one sector; an ownership stake is not editorial control"),
    ("News deserts: US counties with NO local news source",
     "213 counties (up from 206 a year earlier); 1,500+ more counties down to ONE outlet",
     "2025", "Medill State of Local News 2025",
     "~50M Americans with little or no local news; 249 more counties on the watch list"),
    ("Local newspapers lost",
     "~3,500 closed since 2005 (~40% of all local papers); circulation 120M -> 38M",
     "2005-2025", "Medill State of Local News 2025",
     "counts outlets, not coverage quality"),
    ("Local TV: Nexstar (TEGNA deal closed Mar 2026)",
     "259 stations post-divestiture, 44 states, ~80% raw US TV-household reach (54.5% with UHF discount)",
     "Mar 2026", "Bloomberg/CNBC; FCC Media Bureau waived the 39% national cap (delegated authority, no Commission vote)",
     "integration currently FROZEN by a federal judicial stay — reach on paper, contested in court"),
    ("Local TV: Sinclair",
     "185 full-power stations, 86 markets, ~40% of US TV households",
     "2026", "company profile (PitchBook; Britannica)",
     "second-largest station group; reach, not viewership"),
]

# (c) BELIEF — religion's installed base.
#     (row, number, as-of, source, proxy limit)
BELIEF = [
    ("Christianity",
     "2.3B adherents (28.8%, Pew 2020) — or 2.65B (32.3%) per World Christian Database mid-2025",
     "2020 / 2025", "Pew Global Religious Landscape 2025; WCD (Zurlo & Johnson 2025)",
     "self-ID surveys vs affiliation registers: the ~0.3B gap IS the measurement problem"),
    ("Islam",
     "2.0B (25.6%, Pew 2020); fastest-growing: +347M over 2010-20 — more than all other groups combined",
     "2020", "Pew Global Religious Landscape 2025 (WCD mid-2025: 2.06B — sources agree here)",
     "growth is almost entirely demography (fertility), not conversion"),
    ("Religiously unaffiliated",
     "1.9B (24.2%, Pew) — now the 3rd-largest bloc; WCD counts only 0.9B 'nonreligionists'",
     "2020 / 2025", "Pew 2025; WCD 2025",
     "the table's biggest disagreement — hinges almost entirely on how China is classified"),
    ("Hinduism / Buddhism",
     "1.2B (14.9%) / 324M (4.1%); Buddhists the only major group Pew finds shrinking (343M->324M, -5%)",
     "2020", "Pew Global Religious Landscape 2025 (WCD counts Buddhists 538M and growing — methods differ)",
     "disaffiliation in East Asia + low fertility; WCD's broader affiliation count disagrees"),
    ("Catholic Church — installed base",
     "1.406B baptized (17.8% of humanity), +~16M in one year",
     "2023", "Annuarium Statisticum Ecclesiae via Agenzia Fides (Oct 2025)",
     "baptized is not practicing — see the attendance gradient below"),
    ("Catholic Church — institutional reach",
     "229,090 schools (~64.6M pupils) + 103,951 health/charity institutions incl. 5,377 hospitals, 13,895 dispensaries",
     "2023", "Agenzia Fides Catholic Church Statistics 2025",
     "plausibly the largest non-state education + health network on earth; counts institutions, not influence"),
    ("Secularization gradient (attendance)",
     "sub-Saharan Africa ~79% weekly; US 25% weekly (33% monthly); W. Europe median 22% even MONTHLY; China 1% weekly",
     "2018-24", "Pew Age Gap in Religion (2018); Pew RLS 2023-24; Pew Being Christian in W. Europe (2018)",
     "attendance is not belief; survey years and instruments differ across regions"),
    ("Where the believers are",
     "68.9% of all Christians now live in the Global South (17.6% in 1900)",
     "2025", "World Christian Database (Zurlo & Johnson 2025)",
     "the lever did not weaken — it migrated south"),
]


# ---- connector-thread data functions + figures ----------------------------

def sdn_history() -> pd.DataFrame:
    """SDN totals 2000-2024 (Wayback archive) spliced with the live 2026 list."""
    with connect() as con:
        return con.execute("""
            SELECT year, max(CASE WHEN series_id='sdnarchive/sdn_total' THEN value END) AS archive,
                   max(CASE WHEN series_id='sanctions/sdn_total' THEN value END) AS live
            FROM obs WHERE entity='WLD'
              AND series_id IN ('sdnarchive/sdn_total','sanctions/sdn_total')
            GROUP BY year ORDER BY year""").df()


def fig_sanctions_history() -> None:
    import matplotlib.pyplot as plt
    h = sdn_history()
    with connect() as con:
        tgt = con.execute("""
            SELECT year, entity, value FROM obs
            WHERE series_id IN ('sdnarchive/sdn_designations','sanctions/sdn_designations')
              AND entity IN ('RUS','IRN','CUB','YUG','PRK','VEN')
            ORDER BY entity, year""").df()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    fig.suptitle("The financial weapon's arsenal, counted yearly since 2000",
                 x=0.01, ha="left", fontweight="bold")
    tot = pd.concat([h.dropna(subset=["archive"]).assign(v=lambda d: d.archive),
                     h.dropna(subset=["live"]).assign(v=lambda d: d.live)])
    a1.plot(tot.year, tot.v, lw=2, color=PALETTE[0], marker="o", ms=3)
    a1.axvspan(2024.5, 2026.5, color="#57606a", alpha=0.06)
    a1.set_title("Total SDN designations (Wayback archive + live list)", fontsize=9.5, loc="left")
    a1.annotate("2022:\nRussia wave", (2022, float(tot[tot.year == 2022].v.iloc[0])),
                textcoords="offset points", xytext=(-52, 18), fontsize=8)
    for ent, color in [("RUS", PALETTE[1]), ("IRN", PALETTE[3]), ("CUB", PALETTE[2]),
                       ("YUG", PALETTE[7]), ("PRK", PALETTE[4]), ("VEN", PALETTE[5])]:
        g = tgt[tgt.entity == ent]
        a2.plot(g.year, g.value, lw=1.6, label=ent, color=color)
    a2.set_title("Designations by target-country program", fontsize=9.5, loc="left")
    a2.legend(fontsize=8, ncol=2)
    for a in (a1, a2):
        a.grid(alpha=0.25)
    t00 = float(tot[tot.year == 2000].v.iloc[0]); t26 = float(tot[tot.year == 2026].v.iloc[0])
    print(f"[ch11] SDN history: {t00:,.0f} (2000) -> {t26:,.0f} (2026) — {t26/t00:.1f}x")
    source_note(a1, "Source: OFAC SDN list — pinned Wayback snapshots (connector: sdnarchive) + live list (sanctions). "
                    "1994-99 unarchived; 2025 gap (no machine-readable capture).")
    fig.tight_layout()
    save(fig, "11_sanctions_history")


def food_concentration() -> pd.DataFrame:
    """Top-5 exporter share of world exports per staple crop, per year (FAOSTAT)."""
    crops = ["wheat", "maize", "rice", "soybeans"]
    out = []
    with connect() as con:
        for c in crops:
            df = con.execute(f"""
                WITH x AS (SELECT year, entity, value FROM obs
                           WHERE series_id='faostat/export_qty.{c}' AND entity != 'WLD'),
                     w AS (SELECT year, value AS world FROM obs
                           WHERE series_id='faostat/export_qty.{c}' AND entity='WLD')
                SELECT x.year, 100 * sum(x.value) / max(w.world) AS cr5
                FROM (SELECT year, entity, value,
                             row_number() OVER (PARTITION BY year ORDER BY value DESC) rk
                      FROM x) x JOIN w USING (year)
                WHERE x.rk <= 5 GROUP BY x.year ORDER BY x.year""").df()
            df["crop"] = c
            out.append(df)
    return pd.concat(out, ignore_index=True)


def fig_food_concentration() -> None:
    df = food_concentration()
    fig, ax = new_fig(
        "The food lever, concentration computed",
        "Top-5 exporter share of world export volume per staple (FAOSTAT, 1961-2024) — "
        "the curated '~65% of wheat' claim, replaced by the series itself.",
        "top-5 exporter share, %")
    for crop, color in [("wheat", PALETTE[3]), ("maize", PALETTE[2]),
                        ("rice", PALETTE[4]), ("soybeans", PALETTE[0])]:
        g = df[df.crop == crop]
        ax.plot(g.year, g.cr5, lw=1.8, label=crop, color=color)
    for yr in (1973, 2008, 2022):
        ax.axvline(yr, color="#57606a", lw=0.7, ls=":", alpha=0.6)
    ax.set_ylim(30, 100)
    ax.legend(ncol=4)
    w23 = float(df[(df.crop == "wheat") & (df.year == 2023)].cr5.iloc[0])
    s23 = float(df[(df.crop == "soybeans") & (df.year == 2023)].cr5.iloc[0])
    print(f"[ch11] food CR5 2023: wheat {w23:.0f}%, soybeans {s23:.0f}%")
    source_note(ax, "Source: FAOSTAT TCL export quantities (connector: faostat).")
    save(fig, "11_food_concentration")


def mineral_grip() -> pd.DataFrame:
    """Top-producer (CR1) share per USGS commodity, latest common year."""
    with connect() as con:
        return con.execute("""
            WITH m AS (
              SELECT series_id, entity, year, value FROM obs
              WHERE series_id LIKE 'usgs/%' AND year=2024),
            w AS (SELECT series_id, value AS world FROM m WHERE entity='WLD'),
            c AS (SELECT m.series_id, m.entity, m.value / w.world AS share
                  FROM m JOIN w USING (series_id) WHERE m.entity != 'WLD')
            SELECT series_id, entity AS top_producer, share
            FROM (SELECT *, row_number() OVER (PARTITION BY series_id ORDER BY share DESC) rk FROM c)
            WHERE rk = 1 ORDER BY share DESC""").df()


def fig_mineral_grip() -> None:
    df = mineral_grip()
    df["label"] = (df.series_id.str.replace("usgs/mine_prod.", "", regex=False)
                     .str.replace("usgs/refinery_prod.", "", regex=False)
                     .str.replace("_", " ") +
                   df.series_id.str.contains("refinery").map({True: " (refined)", False: ""}))
    fig, ax = new_fig(
        "The mineral grip: one producer, most of the supply",
        "Largest producer's share of world output per commodity, 2024 (USGS Mineral "
        "Commodity Summaries). Red = that producer is China.",
        None)
    colors = [PALETTE[1] if e == "CHN" else PALETTE[7] for e in df.top_producer]
    ax.barh(df.label[::-1], 100 * df.share[::-1], color=colors[::-1])
    for i, (sh, e) in enumerate(zip(df.share[::-1], df.top_producer[::-1])):
        ax.text(100 * sh + 1, i, f"{e} {100*sh:.0f}%", va="center", fontsize=8, color="#57606a")
    ax.set_xlim(0, 108)
    ax.set_xlabel("top producer's share of world output, %")
    n_chn = int((df.top_producer == "CHN").sum())
    print(f"[ch11] mineral grip: China is top producer in {n_chn}/{len(df)} commodities; "
          f"max {df.label.iloc[0]} {100*df.share.iloc[0]:.0f}%")
    source_note(ax, "Source: USGS MCS data release (connector: usgs). Mine production unless marked refined; "
                    "refining is MORE concentrated than mining for most of these.")
    save(fig, "11_mineral_grip")


def fig_arms_pipeline() -> None:
    with connect() as con:
        df = con.execute("""
            SELECT year, entity, value FROM obs
            WHERE series_id='armstransfers/tiv_exports'
              AND entity IN ('USA','SUN','RUS','FRA','GBR','CHN','WLD')
            ORDER BY year""").df()
    wide = df.pivot(index="year", columns="entity", values="value").fillna(0)
    wide["RUS_ALL"] = wide.get("SUN", 0) + wide.get("RUS", 0)
    roll = wide.rolling(5, min_periods=3).sum()
    fig, ax = new_fig(
        "Who arms the world",
        "Share of world arms exports, 5-year rolling TIV (SIPRI arms transfers, 1950-2025).",
        "% of world TIV exports, 5-yr window")
    for col, label, color in [("USA", "United States", PALETTE[0]),
                              ("RUS_ALL", "USSR/Russia", PALETTE[1]),
                              ("FRA", "France", PALETTE[4]),
                              ("GBR", "United Kingdom", PALETTE[7]),
                              ("CHN", "China", PALETTE[2])]:
        ax.plot(roll.index, 100 * roll[col] / roll["WLD"], lw=1.8, label=label, color=color)
    ax.legend(ncol=3)
    us_now = float((100 * roll["USA"] / roll["WLD"]).iloc[-1])
    ru_now = float((100 * roll["RUS_ALL"] / roll["WLD"]).iloc[-1])
    print(f"[ch11] arms exports latest 5yr: US {us_now:.0f}%, Russia {ru_now:.0f}%")
    source_note(ax, "Source: SIPRI Arms Transfers Database TIV (connector: armstransfers). "
                    "TIV measures capability volume, not dollars.")
    save(fig, "11_arms_pipeline")


def fig_imf_reach() -> None:
    with connect() as con:
        new = con.execute("""
            SELECT year, value FROM obs
            WHERE series_id='imflending/arrangements_new' AND entity='WLD' ORDER BY year""").df()
        reach = con.execute("""
            SELECT count(DISTINCT entity) FROM obs
            WHERE series_id='imflending/under_program' AND year BETWEEN 1980 AND 1999""").fetchone()[0]
    fig, ax = new_fig(
        "The IMF's pen: conditionality as a lever",
        "New IMF lending arrangements approved per year, 1952-2026. The era-scoreboard's "
        "'rewrote ~70 economies' understated it.",
        "new arrangements per year")
    ax.bar(new.year, new.value, color=PALETTE[0], width=0.8)
    for yr, txt in [(1983, "debt crisis"), (1997, "Asia"), (2009, "GFC"), (2020, "COVID")]:
        v = float(new[new.year == yr].value.iloc[0])
        ax.annotate(txt, (yr, v), textcoords="offset points", xytext=(0, 8),
                    fontsize=8, ha="center")
    ax.text(0.02, 0.95, f"1980-99: {reach} distinct countries\nunder an IMF program",
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(fc="#f6f8fa", ec="#d0d7de"))
    print(f"[ch11] IMF reach 1980-99: {reach} countries")
    source_note(ax, "Source: IMF lending-arrangements ledger (connector: imflending).")
    save(fig, "11_imf_reach")


def fig_entity_list() -> None:
    with connect() as con:
        df = con.execute("""
            SELECT year, entity, value FROM obs
            WHERE series_id='entitylist/entities' AND entity IN ('CHN','RUS','WLD')
            ORDER BY year""").df()
    fig, ax = new_fig(
        "The export-control lever: the Entity List",
        "BIS Entity List entries (15 CFR 744 Supp. 4), July-1 snapshots via eCFR point-in-time.",
        "listed entities")
    for ent, label, color in [("WLD", "All countries", PALETTE[7]),
                              ("CHN", "China", PALETTE[1]), ("RUS", "Russia", PALETTE[0])]:
        g = df[df.entity == ent]
        ax.plot(g.year, g.value, lw=2 if ent == "WLD" else 1.8, label=label, color=color, marker="o", ms=3)
    ax.annotate("Huawei +\naffiliates", (2019, float(df[(df.entity == "CHN") & (df.year == 2019)].value.iloc[0])),
                textcoords="offset points", xytext=(8, -18), fontsize=8)
    ax.annotate("invasion\nwave", (2022, float(df[(df.entity == "RUS") & (df.year == 2022)].value.iloc[0])),
                textcoords="offset points", xytext=(8, 6), fontsize=8)
    ax.legend()
    c17 = float(df[(df.entity == "CHN") & (df.year == 2017)].value.iloc[0])
    c26 = float(df[(df.entity == "CHN") & (df.year == 2026)].value.iloc[0])
    print(f"[ch11] Entity List CHN: {c17:.0f} (2017) -> {c26:.0f} (2026)")
    source_note(ax, "Source: eCFR versioner API (connector: entitylist). Point-in-time history starts 2017.")
    save(fig, "11_entity_list")


# ---- curated-table figures (items 15-17) ----------------------------------

def fig_reserve_succession() -> None:
    cur = pd.DataFrame(RESERVE_SUCCESSION, columns=["year", "ccy", "share", "src"])
    with connect() as con:
        cofer = con.execute("""
            SELECT year, replace(series_id, 'cofer/reserve_share.', '') AS ccy, value AS share
            FROM obs WHERE series_id IN ('cofer/reserve_share.USD','cofer/reserve_share.GBP')
              AND year >= 1999 ORDER BY year""").df()
    fig, ax = new_fig(
        "The only complete handover in the data: sterling to dollar",
        "Share of known/identified official FX holdings (curated anchors, 1899-1994; convention "
        "breaks flagged) spliced to IMF COFER allocated shares (1999-2025).",
        "% of identified official FX reserves")
    for ccy, color in [("GBP", PALETTE[1]), ("USD", PALETTE[0]),
                       ("FRF", PALETTE[7]), ("DEM", PALETTE[2]), ("JPY", PALETTE[4])]:
        g = cur[cur.ccy == ccy].sort_values("year")
        if len(g):
            ax.plot(g.year, g.share, lw=1.8, marker="o", ms=4, color=color, label=ccy, ls="--")
        h = cofer[cofer.ccy == ccy]
        if len(h):
            ax.plot(h.year, h.share, lw=2, color=color)
    ax.axvspan(1914, 1945, color="#d1242f", alpha=0.05)
    for yr, txt in [(1924, "USD first passes GBP"), (1944, "Bretton Woods"),
                    (1955, "USD durably ahead"), (1976, "sterling's end"), (1999, "euro/COFER")]:
        ax.axvline(yr, color="#57606a", lw=0.6, ls=":", alpha=0.6)
        ax.text(yr + 0.7, 2, txt, rotation=90, fontsize=7, color="#57606a",
                ha="left", va="bottom")
    ax.set_ylim(0, 100)
    ax.legend(ncol=5, loc="upper right", fontsize=8)
    print("[ch11] reserve succession: US #1 economy ~1880, #1 reserve currency durably ~1955 — a ~75-year lag")
    source_note(ax, "Curated: Lindert 1969, Eichengreen-Flandreau 2009, Eichengreen-Chitu-Mehl 2014, Schenk 2010, "
                    "IMF Annual Reports; dashed = curated anchors, solid = COFER (connector: cofer). "
                    "Shares are of IDENTIFIED holdings; gold dominated reserves before ~1970.")
    save(fig, "11_reserve_succession")


def fig_nuclear_arc() -> None:
    import matplotlib.pyplot as plt
    arc = pd.DataFrame(NUCLEAR_ARC, columns=["year", "world", "usa", "sun", "src"])
    today = pd.DataFrame(NUCLEAR_TODAY, columns=["entity", "n", "src"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6), width_ratios=[3, 2])
    fig.suptitle("The lever that ended total war", x=0.01, ha="left", fontweight="bold")
    a1.fill_between(arc.year, arc.world, color=PALETTE[7], alpha=0.15, label="World inventory")
    a1.plot(arc.year, arc.world, lw=1.5, color=PALETTE[7])
    a1.plot(arc.year, arc.usa, lw=1.8, color=PALETTE[0], label="US stockpile")
    a1.plot(arc.year, arc.sun, lw=1.8, color=PALETTE[1], label="USSR/Russia stockpile")
    a1.annotate("world peak 70,374 (1986)", (1986, 70374), textcoords="offset points",
                xytext=(-95, -2), fontsize=8)
    a1.annotate("US peak 31,255 (1967)", (1967, 31255), textcoords="offset points",
                xytext=(-100, 6), fontsize=8)
    a1.set_title("Warheads, 1945-2026 (estimates)", fontsize=9.5, loc="left")
    a1.legend(fontsize=8)
    colors = [PALETTE[1] if e in ("RUS", "CHN", "PRK") else PALETTE[0] for e in today.entity]
    a2.barh(today.entity[::-1], today.n[::-1], color=colors[::-1])
    for i, v in enumerate(today.n[::-1]):
        a2.text(v + 60, i, f"{v:,}", va="center", fontsize=8, color="#57606a")
    a2.set_title("Total inventory, Jan 2026", fontsize=9.5, loc="left")
    a2.set_xlim(0, 6300)
    for a in (a1, a2):
        a.grid(alpha=0.25)
    print(f"[ch11] nuclear: {NUCLEAR_CUMULATIVE_BUILT:,}+ built since 1945; world peak 70,374 (1986); "
          f"today 12,187 across 9 states; umbrella covers {NUCLEAR_UMBRELLA_STATES[0]} US allies")
    source_note(a1, "Curated: FAS Status of World Nuclear Forces / SIPRI YB 2026 (identical, same authors); "
                    "Norris & Kristensen BAS. All figures are estimates — arsenals are state secrets.")
    fig.tight_layout()
    save(fig, "11_nuclear_arc")


def fig_attention_belief() -> None:
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    fig.suptitle("Appendix — the intangible levers, proxied (reach, not persuasion)",
                 x=0.01, ha="left", fontweight="bold")
    platforms = [("Meta family (daily)", 3.56), ("Instagram (monthly)", 3.0),
                 ("YouTube (monthly, est.)", 2.7), ("TikTok (monthly, est.)", 1.8),
                 ("WeChat (monthly)", 1.43)]
    labels = [p[0] for p in platforms][::-1]
    vals = [p[1] for p in platforms][::-1]
    a1.barh(labels, vals, color=[PALETTE[2], PALETTE[1], PALETTE[7], PALETTE[0], PALETTE[0]])
    for i, v in enumerate(vals):
        a1.text(v + 0.05, i, f"{v}B", va="center", fontsize=8, color="#57606a")
    a1.set_title("Attention: platform actives, billions (2025-26 filings/estimates)",
                 fontsize=9.5, loc="left")
    a1.set_xlim(0, 4.3)
    rel = [("Christianity", 2.3, 2.65), ("Islam", 2.0, 2.06), ("Unaffiliated", 1.9, 0.9),
           ("Hinduism", 1.2, None), ("Buddhism", 0.324, 0.538)]
    labels2 = [r[0] for r in rel][::-1]
    pew = [r[1] for r in rel][::-1]
    a2.barh(labels2, pew, color=PALETTE[4])
    for i, r in enumerate(rel[::-1]):
        a2.text(r[1] + 0.04, i, f"{r[1]}B", va="center", fontsize=8, color="#57606a")
        if r[2] is not None:
            a2.plot([r[2]], [i], marker="D", color=PALETTE[3], ms=5)
    a2.set_title("Belief: adherents, billions (Pew 2020; diamonds = WCD 2025 where they disagree)",
                 fontsize=9.5, loc="left")
    a2.set_xlim(0, 3.2)
    for a in (a1, a2):
        a.grid(alpha=0.25, axis="x")
    print("[ch11] intangibles: Meta reaches ~43% of humanity DAILY; Pew-vs-WCD disagree by 1.0B on the unaffiliated")
    source_note(a1, "Curated appendix: company filings, StatCounter, Pew 2025, World Christian Database 2025, "
                    "Agenzia Fides. Every number is a REACH proxy — none measures persuasion.")
    fig.tight_layout()
    save(fig, "11_attention_belief")


def main() -> None:
    fig_war_lever()
    fig_arsenal()
    fig_money_lever()
    fig_energy_lever()
    fig_food_lever()
    fig_sanctions_lever()
    fig_tech_lever()
    fig_lever_scoreboard()
    fig_lever_map()
    fig_milex_today()
    fig_dollar_grip()
    fig_energy_today()
    fig_who_gets_sanctioned()
    fig_sanctions_efficacy()
    fig_coercion_map()
    fig_dollar_system()
    fig_arsenal_rule()
    fig_erosion_rates()
    fig_sanctions_history()
    fig_food_concentration()
    fig_mineral_grip()
    fig_arms_pipeline()
    fig_imf_reach()
    fig_entity_list()
    fig_reserve_succession()
    fig_nuclear_arc()
    fig_attention_belief()


if __name__ == "__main__":
    main()
