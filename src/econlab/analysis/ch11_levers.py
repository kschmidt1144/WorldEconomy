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
     "UK: ~2% of people, ~45% of world coal (1870), gold standard clears via London"),
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


if __name__ == "__main__":
    main()
