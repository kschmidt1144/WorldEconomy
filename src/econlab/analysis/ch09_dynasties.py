"""Chapter 10 — Dynasties: the Rothschild ledger, 1818-2026."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

HOUSES = ["frankfurt", "london", "vienna", "naples", "paris"]
HOUSE_LABELS = {"frankfurt": "Frankfurt (†1901)", "london": "London",
                "vienna": "Vienna (seized 1938)", "naples": "Naples (†1863)",
                "paris": "Paris (nationalized 1981)"}


def capital_panel() -> pd.DataFrame:
    with connect() as con:
        df = con.execute(
            "SELECT series_id, year, value FROM obs WHERE series_id LIKE "
            "'dynasties/rothschild_capital_%' ORDER BY year"
        ).df()
    df["house"] = df.series_id.str.rsplit("_", n=1).str[-1]
    return df.pivot(index="year", columns="house", values="value").fillna(0)


def capital_vs_uk() -> pd.DataFrame:
    with connect() as con:
        return con.execute(
            """
            SELECT r.year, r.value AS capital, 100 * r.value / g.value AS pct_uk
            FROM obs r JOIN obs g
              ON g.series_id='boe/ngdp' AND g.entity='GBR' AND g.year=r.year
            WHERE r.series_id='dynasties/rothschild_capital_total' ORDER BY r.year
            """
        ).df().set_index("year")


def then_vs_now() -> pd.DataFrame:
    """Fortune as % of home GDP and % of world GDP: 1882 partnership vs 2026 individuals."""
    with connect() as con:
        gdp = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
        ).df().set_index("entity")["value"]
        world = float(gdp.sum())
        top = con.execute(
            "SELECT name, worth_usd, country FROM billionaires ORDER BY rank LIMIT 3"
        ).df()
    g = lambda ent: float(gdp[ent])  # noqa: E731
    uk = capital_vs_uk()

    # Rothschild 1882: home basis = UK share; world basis via Maddison UK/world ratio
    from .maddison_world import load_panel, maddison_world_reference_annual, successor_partition

    panel = successor_partition(load_panel())
    gbr = panel[panel.entity == "GBR"].set_index("year")
    ref = maddison_world_reference_annual().set_index("year")["gdp"]
    uk_world_1882 = float((gbr.gdppc * gbr["pop"]).loc[1882] / ref.loc[1882])

    rows = [{
        "who": "Rothschild family\n(five houses, 1882)",
        "home": float(uk.loc[1882, "pct_uk"]),
        "world": float(uk.loc[1882, "pct_uk"]) * uk_world_1882,
    }]
    home_map = {"United States": "USA", "France": "FRA"}
    for _, r in top.iterrows():
        ent = home_map.get(r["country"], "USA")
        rows.append({
            "who": r["name"].replace(" & family", "\n& family") + " (2026)",
            "home": 100 * r.worth_usd / g(ent),
            "world": 100 * r.worth_usd / world,
        })
    return pd.DataFrame(rows).set_index("who")


def fig_capital_arc() -> None:
    import matplotlib.pyplot as plt

    panel = capital_panel() / 1e6
    ratio = capital_vs_uk()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle("The Rothschild partnership, 1818-1904 — from the family's own books",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    order = ["frankfurt", "london", "vienna", "naples", "paris"]
    ax1.stackplot(panel.index, [panel[h] for h in order],
                  labels=[HOUSE_LABELS[h] for h in order],
                  colors=[PALETTE[i] for i in range(5)], alpha=0.88)
    ax1.set_title("Combined capital by house, £ millions", fontsize=10, loc="left")
    ax1.legend(fontsize=7.5, loc="upper left")
    ax1.annotate("Paris becomes\nthe center", (1876, 22), fontsize=8, color="#57606a")

    ax2.plot(ratio.index, ratio.pct_uk, lw=2.2, color=PALETTE[1], marker="o", ms=3.5)
    peak_y = ratio.pct_uk.idxmax()
    ax2.annotate(f"peak: {ratio.pct_uk.max():.1f}% of UK GDP ({peak_y})",
                 (peak_y, ratio.pct_uk.max()), xytext=(1830, 2.75), fontsize=8.5,
                 arrowprops=dict(arrowstyle="->", lw=0.8, color="#57606a"))
    ax2.set_title("Total capital as % of UK GDP (BoE millennium data)",
                  fontsize=10, loc="left")
    ax2.set_ylabel("% of UK nominal GDP")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from Ferguson (Rothschild Archive accounts) + Bank of England "
             "millennium dataset (econlab warehouse)", fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_rothschild_arc")


def fig_then_vs_now() -> None:
    tn = then_vs_now()
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5))
    fig.suptitle("Dynasty vs dynasty: peak Rothschild against today's summit",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    x = np.arange(len(tn))
    colors = [PALETTE[3]] + [PALETTE[0]] * (len(tn) - 1)
    ax1.bar(x, tn.home, color=colors)
    for i, v in enumerate(tn.home):
        ax1.text(i, v + 0.05, f"{v:.1f}%", ha="center", fontsize=9)
    ax1.set_xticks(x, tn.index, fontsize=8)
    ax1.set_title("Fortune as % of HOME-country GDP", fontsize=10, loc="left")

    ax2.bar(x, tn.world, color=colors)
    for i, v in enumerate(tn.world):
        ax2.text(i, v + 0.012, f"{v:.2f}%", ha="center", fontsize=9)
    ax2.set_xticks(x, tn.index, fontsize=8)
    ax2.set_title("Fortune as % of WORLD GDP — today's summit is relatively larger",
                  fontsize=10, loc="left")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02,
             "Source: computed from Ferguson/BoE (1882), Forbes snapshot + IMF (2026), "
             "Maddison UK/world ratio (econlab warehouse). Rothschild = business capital "
             "of a whole family; moderns = single-person net worth.",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_then_vs_now")


FAMILY_PATTERNS = {
    "Walton": (["%walton%"], "USA"),
    "Koch": (["%koch%", "%marshall%"], "USA"),
    "Ambani": (["%ambani%"], "IND"),
    "Boehringer": (["%boehringer%", "%von baumbach%"], "DEU"),
}


def modern_family_shares() -> pd.DataFrame:
    """Family sums from the billionaires table vs home GDP (%)."""
    with connect() as con:
        gdp = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
        ).df().set_index("entity")["value"]
        rows = []
        for fam, (pats, home) in FAMILY_PATTERNS.items():
            clause = " OR ".join(f"name ILIKE '{p}'" for p in pats)
            n, s = con.execute(
                f"SELECT count(*), sum(worth_usd) FROM billionaires WHERE {clause}"
            ).fetchone()
            rows.append({"family": fam, "members": n, "worth": float(s),
                         "pct_home": 100 * float(s) / float(gdp[home])})
    return pd.DataFrame(rows).set_index("family")


def dynasty_chart_data() -> pd.DataFrame:
    """% of home GDP at peak: curated historical + computed modern, one frame."""
    uk = capital_vs_uk()
    hist = [
        ("Fugger 1546", 2.0, "curated"),          # scholarly band ~1.5-2.5
        ("Vanderbilt 1877", 1.17, "curated"),
        ("Rockefeller 1913", 2.30, "curated"),
        ("Rothschild 1882", float(uk.pct_uk.max()), "computed"),
    ]
    mods = modern_family_shares()
    rows = [{"who": w, "pct": p, "basis": b} for w, p, b in hist]
    for fam, r in mods.iterrows():
        rows.append({"who": f"{fam} 2026", "pct": r.pct_home, "basis": "computed"})
    with connect() as con:
        musk, us = con.execute(
            "SELECT (SELECT max(worth_usd) FROM billionaires), "
            "(SELECT value FROM obs WHERE series_id='imf/NGDPD' AND entity='USA' AND year=2026)"
        ).fetchone()
    rows.append({"who": "Musk 2026 (one person)", "pct": 100 * musk / us, "basis": "reference"})
    return pd.DataFrame(rows).sort_values("pct")


def fig_fugger() -> None:
    with connect() as con:
        f = con.execute(
            "SELECT year, value FROM obs WHERE series_id='dynasties/fugger_capital' ORDER BY year"
        ).df()
    fig, ax = new_fig(
        "The Fugger firm, 1494-1546: the steepest fortune ever recorded",
        subtitle="Firm capital, Rhenish gulden (Ehrenberg/Häberlein inventories). 94x in 52 years — copper, silver, papal finance, and the purchase of an emperor.",
        ylabel="gulden (log scale)",
    )
    ax.plot(f.year, f.value, marker="o", ms=6, lw=2, color=PALETTE[3])
    for _, r in f.iterrows():
        ax.annotate(f"{r.value/1e6:.2f}M" if r.value >= 1e6 else f"{r.value/1e3:.0f}k",
                    (r.year, r.value), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=8.5)
    ax.axvline(1519, color="#57606a", lw=0.8, ls=":")
    ax.text(1519.5, 1.2e5, "1519: finances Charles V's\nimperial election (543,585 fl of 852k)",
            fontsize=8, color="#57606a")
    ax.axvline(1525, color="#57606a", lw=0.8, ls=":")
    ax.text(1525.5, 2.5e6, "Jakob dies 1525", fontsize=8, color="#57606a")
    ax.set_yscale("log")
    source_note(ax, "Source: curated Ehrenberg (1896)/Häberlein (2006) inventories (econlab warehouse)")
    save(fig, "09_fugger")


def fig_ten_dynasties() -> None:
    d = dynasty_chart_data()
    fig, ax = new_fig(
        "Dynasties across five centuries: peak family wealth vs home economy",
        subtitle="Hatched = curated historical estimates; solid = computed from this warehouse (Forbes sums / IMF GDP; Rothschild from Ferguson x BoE). Medici & Mitsui: see prose — power and control, not GDP shares.",
        ylabel=None,
    )
    colors = {"curated": "#9a6700", "computed": "#1f6feb", "reference": "#d1242f"}
    for i, (_, r) in enumerate(d.iterrows()):
        ax.barh(i, r.pct, color=colors[r.basis],
                hatch="//" if r.basis == "curated" else None,
                alpha=0.9 if r.basis != "reference" else 0.75)
        ax.text(r.pct + 0.04, i, f"{r.pct:.1f}%", va="center", fontsize=9)
    ax.set_yticks(range(len(d)), d.who, fontsize=9)
    ax.set_xlabel("peak family wealth, % of home-country GDP")
    source_note(
        ax,
        "Source: econlab warehouse (billionaires table + IMF + Ferguson/BoE) and curated "
        "historical estimates (MeasuringWorth GDP; Steinmetz/Häberlein band for Fugger)",
    )
    save(fig, "09_ten_dynasties")


def fig_medici() -> None:
    import matplotlib.pyplot as plt

    with connect() as con:
        m = {}
        for key in ("capital", "profit_period", "curia_deposits", "conversion_spend"):
            m[key] = con.execute(
                f"SELECT year, value FROM obs WHERE series_id='dynasties/medici_{key}' ORDER BY year"
            ).df().set_index("year")["value"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle("The Medici Bank, 1397-1494 — small capital, papal deposits, total conversion",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # left: the bank through time
    ax1.bar([1408.5, 1435], m["profit_period"].values / 1e3, width=[23, 30],
            color=PALETTE[2], alpha=0.5, label="period profits (total, k fl)")
    ax1.plot(m["capital"].index, m["capital"].values / 1e3, marker="o", ms=7,
             lw=2, color=PALETTE[0], label="bank capital (corpo, k fl)")
    ax1.scatter(m["curia_deposits"].index, m["curia_deposits"].values / 1e3,
                marker="D", s=60, color=PALETTE[3], zorder=5,
                label="Papal Curia deposits (k fl)")
    for x, y, txt in [(1434, 265, "1434: Cosimo\nrules Florence"),
                      (1455, 225, "1455: Benci dies —\nthe decline begins"),
                      (1478, 185, "1478: Pazzi plot;\nLondon lost 51.5k fl"),
                      (1494, 145, "1494: expulsion,\nbank confiscated")]:
        ax1.axvline(x, color="#57606a", lw=0.7, ls=":")
        ax1.text(x + 0.6, y, txt, fontsize=7, color="#57606a", va="top")
    ax1.set_ylabel("thousand florins")
    ax1.set_xlim(1395, 1500)
    ax1.set_title("Rome branch = 62% of profits; capital stayed tiny", fontsize=10, loc="left")
    ax1.legend(fontsize=7.5, loc="upper left")

    # right: the conversion — power cost more than the bank ever earned
    bars = {
        "Bank capital\n(c.1451)": m["capital"][1451],
        "Giovanni's estate\n(1429)": 180_000,
        "All profits\n1397-1450": float(m["profit_period"].sum()),
        "Cosimo's spend on\nbuildings/charity/taxes\n(1434-71)": m["conversion_spend"][1471],
    }
    colors = [PALETTE[0], PALETTE[7], PALETTE[2], PALETTE[1]]
    ax2.bar(range(len(bars)), [v / 1e3 for v in bars.values()], color=colors)
    for i, v in enumerate(bars.values()):
        ax2.text(i, v / 1e3 + 12, f"{v/1e3:,.0f}k", ha="center", fontsize=9.5)
    ax2.set_xticks(range(len(bars)), bars.keys(), fontsize=8)
    ax2.set_ylabel("thousand florins")
    ax2.set_title("The conversion: 1.5x the bank's lifetime profits spent on power",
                  fontsize=10, loc="left")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02,
             "Source: curated de Roover (1963, libri segreti) + Lorenzo's ricordi (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_medici")


def fig_deep_time() -> None:
    import matplotlib.pyplot as plt

    with connect() as con:
        s = con.execute(
            "SELECT name, start_year, end_year, kind, documentation FROM deep_survivors "
            "ORDER BY start_year"
        ).df()
    s["end_plot"] = s.end_year.fillna(2026)

    kind_colors = {"sacred office": PALETTE[4], "crown": PALETTE[0],
                   "family firm": PALETTE[2], "noble house": PALETTE[3],
                   "banking dynasty": PALETTE[1], "wealth class": "#d1242f"}

    fig, ax = plt.subplots(figsize=(12.5, 7))
    for i, (_, r) in enumerate(s.iterrows()):
        ax.barh(i, r.end_plot - r.start_year, left=r.start_year, height=0.62,
                color=kind_colors[r.kind],
                alpha=0.55 if r.documentation == "semi-legendary" else 0.92,
                hatch="//" if r.documentation == "semi-legendary" else None)
        years = int(r.end_plot - r.start_year)
        ax.text(r.end_plot + 15, i, f"{years:,} yrs", va="center", fontsize=8)
    ax.axvline(476, color="#d1242f", lw=1.4, ls="--")
    ax.text(476, len(s) - 0.2, " 476: fall of the\n Western Empire",
            fontsize=8.5, color="#d1242f", va="top")
    ax.axvline(603, color="#8b0000", lw=0.9, ls=":")
    ax.text(660, 2.6, "603: last record of\nthe Roman Senate", fontsize=7.5, color="#8b0000")
    ax.set_yticks(range(len(s)), s.name, fontsize=8.5)
    ax.set_xlim(-650, 2450)
    ax.set_xlabel("year")
    ax.set_title("Deep time: documented family continuity vs the fall of Rome",
                 loc="left", fontweight="bold", fontsize=13, pad=24)
    ax.text(0, 1.015,
            "Bar = documented span (hatched = semi-legendary origin). No Western family crosses "
            "the red line; the survivors of the era are Asian — a sacred office, a crown, a builder of temples.",
            transform=ax.transAxes, fontsize=9, color="#57606a")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in kind_colors.values()]
    ax.legend(handles, kind_colors.keys(), fontsize=7.5, loc="upper left", ncol=1,
              bbox_to_anchor=(0.005, 0.88))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.25, axis="x")
    fig.text(0.01, -0.01,
             "Source: curated spans (PLRE for the senatorial terminus; standard genealogical "
             "scholarship per entry — see deep_survivors table notes) (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_deep_time")


LIFELINES = [  # (name, start, dynasty-specific beats [(year, marker, label)])
    ("Bagrationi (Georgia)", 780, [(1801, "x", "Russia annexes"), (1921, ".", "Soviet exile")]),
    ("Welf (→ Hanover)", 819, [(1714, "o", "George I: British crown")]),
    ("Staffelter Hof (wine)", 862, []),
    ("Capetians", 866, [(987, "o", "Hugh Capet crowned"), (1328, ".", "→ Valois"),
                        (1589, ".", "→ Bourbon"), (1793, "x", "Louis XVI guillotined"),
                        (1975, "o", "restored: Spain")]),
    ("Massimo (Rome)", 1000, [(1467, "o", "hosts Italy's first printing press")]),
    ("Colonna (Rome)", 1078, [(1303, ".", "the slap of Anagni"), (1417, "o", "Pope Martin V"),
                              (1571, ".", "Lepanto"), (1870, "x", "papal Rome falls")]),
    ("Orsini (Rome)", 1100, []),
    ("Ricasoli (wine)", 1141, []),
    ("Frescobaldi", 1300, [(1311, "x", "English crown defaults")]),
    ("Rothschild (for scale)", 1760, []),
]

WORLD_EVENTS = [
    (1066, "1066 Conquest"), (1096, "First Crusade"), (1215, "Magna Carta"),
    (1453, "Constantinople falls"), (1492, "Columbus"), (1517, "Reformation"),
    (1720, "South Sea Bubble"), (1848, "Revolutions"), (1929, "Crash"),
]
WORLD_BANDS = [
    (1347, 1351, "#d1242f", 0.25, "Black Death"),
    (1337, 1453, "#9a6700", 0.10, "Hundred Years' War"),
    (1618, 1648, "#9a6700", 0.15, "Thirty Years' War"),
    (1789, 1815, "#8250df", 0.12, "Revolution & Napoleon"),
    (1914, 1918, "#d1242f", 0.18, None),
    (1939, 1945, "#d1242f", 0.18, "World Wars"),
]


def fig_millennium_walk() -> None:
    import matplotlib.pyplot as plt

    with connect() as con:
        pop = con.execute(
            "SELECT year, value FROM obs WHERE series_id='boe/pop_england' ORDER BY year"
        ).df().set_index("year")["value"]
        cpi = con.execute(
            "SELECT year, value FROM obs WHERE series_id='boe/cpi' ORDER BY year"
        ).df().set_index("year")["value"]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13.5, 9), sharex=True, height_ratios=[1, 1.2]
    )
    fig.suptitle("Walking the millennium: the oldest Western lines, and what they lived through",
                 x=0.01, ha="left", fontweight="bold", fontsize=14)

    # --- top: dynasty lifelines
    for i, (name, start, beats) in enumerate(LIFELINES):
        y = len(LIFELINES) - i
        ax1.plot([start, 2026], [y, y], lw=2.2, color=PALETTE[i % len(PALETTE)], alpha=0.85)
        ax1.text(start - 12, y, name, ha="right", va="center", fontsize=8)
        for by, mk, lbl in beats:
            ax1.scatter([by], [y], marker=mk, s=46 if mk == "x" else 30,
                        color="#d1242f" if mk == "x" else "#1f2328", zorder=5)
    ax1.set_ylim(0.2, len(LIFELINES) + 0.8)
    ax1.set_yticks([])
    ax1.set_title("Documented lifelines (× = near-death events: default, guillotine, annexation)",
                  fontsize=9.5, loc="left")

    # --- bottom: the warehouse witnesses
    ax2.plot(pop.index, pop.values / 1e6, lw=1.8, color=PALETTE[2],
             label="England population, M (BoE, 1086→)")
    ax2.set_yscale("log")
    ax2.set_ylabel("England population, millions (log)", color=PALETTE[2])
    ax2b = ax2.twinx()
    ax2b.plot(cpi.index, cpi.values, lw=1.4, color=PALETTE[0],
              label="UK consumer prices (2015=100, log)")
    ax2b.set_yscale("log")
    ax2b.set_ylabel("price level, 2015=100 (log)", color=PALETTE[0])
    ax2.annotate("Black Death:\n−46% in 3 years", (1351, 2.6), xytext=(1390, 1.55),
                 fontsize=8.5, color="#d1242f",
                 arrowprops=dict(arrowstyle="->", color="#d1242f", lw=0.9))
    ax2b.annotate("1913 prices BELOW 1815 —\nthe gold-standard century", (1913, 1.24),
                  xytext=(1610, 14), fontsize=8.5, color=PALETTE[0],
                  arrowprops=dict(arrowstyle="->", color=PALETTE[0], lw=0.9))
    ax2.set_title("The warehouse as witness: population and prices under the same sky",
                  fontsize=9.5, loc="left")

    # --- shared shocks
    for a, b, c, alpha, lbl in WORLD_BANDS:
        for ax in (ax1, ax2):
            ax.axvspan(a, b, color=c, alpha=alpha)
        if lbl:
            ax2.text((a + b) / 2, ax2.get_ylim()[0] * 1.25, lbl, rotation=90,
                     fontsize=7, color="#57606a", ha="center", va="bottom")
    for x, lbl in WORLD_EVENTS:
        ax1.axvline(x, color="#57606a", lw=0.5, ls=":", alpha=0.7)
        ax2.axvline(x, color="#57606a", lw=0.5, ls=":", alpha=0.7)
        ax1.text(x, len(LIFELINES) + 0.65, lbl, rotation=90, fontsize=6.5,
                 color="#57606a", ha="center", va="top")

    ax2.set_xlim(700, 2080)
    ax2.set_xlabel("year")
    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax2.grid(alpha=0.2)
    fig.text(0.01, 0.005,
             "Source: lifelines curated (deep_survivors); population & CPI computed from the "
             "BoE millennium dataset in this warehouse. Price factor 1209→2015: 1,214×.",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_millennium_walk")


EAST_LIFELINES = [
    ("Ecumenical Patriarchate", 381, 2026, [], "solid"),
    ("St Catherine's, Sinai", 548, 2026, [], "solid"),
    ("Great Lavra, Athos", 963, 2026, [], "solid"),
    ("Macedonian dynasty", 867, 1056, [(1025, ".", "Basil II: apogee")], "solid"),
    ("Komnenos", 1081, 1185, [], "solid"),
    ("  …Trebizond branch", 1204, 1461, [(1461, "x", "executed 1463")], "solid"),
    ("Angelos", 1185, 1204, [(1204, "x", "Fourth Crusade sack")], "solid"),
    ("Laskaris (Nicaea)", 1204, 1261, [], "solid"),
    ("Palaiologos", 1259, 1453, [(1453, "x", "Constantine XI dies at the walls")], "solid"),
    ("Kantakouzenos → Cantacuzino", 1100, 2026,
     [(1347, "o", "John VI: emperor"), (1578, "x", "strangled; fortune seized"),
      (1678, "o", "Prince of Wallachia")], "solid"),
    ("House of Osman", 1299, 2026,
     [(1453, "o", "takes Constantinople"), (1922, "x", "sultanate abolished"),
      (2009, ".", "'last Ottoman' dies, NYC")], "solid"),
    ("Camondo (bankers)", 1802, 1945, [(1945, "x", "family murdered in the Holocaust")], "solid"),
]

EAST_EVENTS = [
    (330, "Constantinople founded"), (537, "Hagia Sophia"), (1071, "Manzikert"),
    (1453, "1453"), (1571, "Lepanto"), (1683, "Vienna"), (1839, "Tanzimat"),
    (1875, "Ottoman default"), (1908, "Young Turks"),
]
EAST_BANDS = [
    (1204, 1261, "#d1242f", 0.15, "Latin occupation"),
    (1821, 1830, "#1a7f37", 0.15, "Greek independence"),
    (1912, 1923, "#d1242f", 0.18, "collapse & exchange"),
]


def fig_byzantine_walk() -> None:
    import matplotlib.pyplot as plt

    with connect() as con:
        gd = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='maddison/gdppc' "
            "AND entity IN ('GRC','TUR') AND year >= 300 ORDER BY year"
        ).df()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13.5, 9), sharex=True,
                                   height_ratios=[1.15, 1])
    fig.suptitle("The Eastern mirror: Byzantium through the Ottomans",
                 x=0.01, ha="left", fontweight="bold", fontsize=14)

    for i, (name, start, end, beats, _doc) in enumerate(EAST_LIFELINES):
        y = len(EAST_LIFELINES) - i
        ax1.plot([start, end], [y, y], lw=2.2, color=PALETTE[i % len(PALETTE)], alpha=0.85)
        ax1.text(start - 12, y, name, ha="right", va="center", fontsize=8)
        for by, mk, lbl in beats:
            ax1.scatter([by], [y], marker=mk, s=48 if mk == "x" else 30,
                        color="#d1242f" if mk == "x" else "#1f2328", zorder=5)
    # the idea migrates: Sophia Palaiologina to Moscow, 1472
    ax1.annotate("1472: Sophia Palaiologina → Moscow\n('Third Rome', the double eagle)",
                 (1472, 4), xytext=(1560, 6.2), fontsize=7.5, color="#57606a",
                 arrowprops=dict(arrowstyle="->", lw=0.8, color="#57606a"))
    ax1.set_ylim(0.2, len(EAST_LIFELINES) + 0.9)
    ax1.set_yticks([])
    ax1.set_title("Imperial houses die with the state; offices, monasteries, and two impossible "
                  "families cross everything", fontsize=9.5, loc="left")

    colors = {"GRC": PALETTE[0], "TUR": PALETTE[1]}
    names = {"GRC": "Greece", "TUR": "Turkey/Anatolia"}
    for ent, sub in gd.groupby("entity"):
        ax2.plot(sub.year, sub.value, marker="o", ms=2.5, lw=1.4,
                 color=colors[ent], label=f"{names[ent]} GDP per capita (2011$)")
    ax2.set_yscale("log")
    ax2.set_ylabel("GDP per capita, 2011$ (log)")
    ax2.annotate("the Ottoman flatline:\n$768 (1500) → $974 (1820)",
                 (1660, 900), xytext=(1330, 3800), fontsize=8.5, color=PALETTE[1],
                 arrowprops=dict(arrowstyle="->", lw=0.9, color=PALETTE[1]))
    ax2.legend(fontsize=8.5, loc="upper left")
    ax2.set_title("The warehouse as witness (Maddison): Roman prosperity, medieval loss, "
                  "Ottoman stasis, republican takeoff", fontsize=9.5, loc="left")

    for a, b, c, alpha, lbl in EAST_BANDS:
        for ax in (ax1, ax2):
            ax.axvspan(a, b, color=c, alpha=alpha)
        ax2.text((a + b) / 2, 420, lbl, rotation=90, fontsize=7, color="#57606a",
                 ha="center", va="bottom")
    for x, lbl in EAST_EVENTS:
        for ax in (ax1, ax2):
            ax.axvline(x, color="#57606a", lw=0.5, ls=":", alpha=0.7)
        ax1.text(x, len(EAST_LIFELINES) + 0.8, lbl, rotation=90, fontsize=6.5,
                 color="#57606a", ha="center", va="top")

    ax2.set_xlim(280, 2100)
    ax2.set_xlabel("year")
    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax2.grid(alpha=0.2)
    fig.text(0.01, 0.005,
             "Source: lifelines curated (deep_survivors + Byzantine prosopography); GDP pc "
             "computed from Maddison 2023 in this warehouse.",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_byzantine_walk")


def fig_royal_lines() -> None:
    import matplotlib.pyplot as plt

    with connect() as con:
        rl = con.execute(
            "SELECT realm, house, start_year, end_year, fate FROM royal_lines"
        ).df()
    rl["end_plot"] = rl.end_year.fillna(2026)
    realms = ["Monaco", "Italy (Savoy)", "Poland", "Russia", "Sweden", "Denmark",
              "Portugal", "Spain", "Austria", "HRE / Germany", "Britain", "France"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10.5), sharex=True,
                                   height_ratios=[3.2, 1])
    fig.suptitle("The crowns of Europe, 476 → today: every ruling house of twelve realms",
                 x=0.01, ha="left", fontweight="bold", fontsize=14)

    house_colors = {}
    for yi, realm in enumerate(realms):
        sub = rl[rl.realm == realm].sort_values("start_year")
        for k, (_, r) in enumerate(sub.iterrows()):
            color = PALETTE[(hash(r.house) + k) % len(PALETTE)]
            house_colors[r.house] = color
            ax1.barh(yi, r.end_plot - r.start_year, left=r.start_year, height=0.62,
                     color=color, alpha=0.85, edgecolor="white", lw=0.6)
            width = r.end_plot - r.start_year
            if width > 95:
                ax1.text(r.start_year + width / 2, yi, r.house, ha="center",
                         va="center", fontsize=6.6, color="white", fontweight="bold")
            if r.fate in ("revolution", "abolished", "partitioned", "conquest",
                          "dissolved") and r.end_year is not None:
                ax1.scatter([r.end_year], [yi], marker="x", s=55, color="#d1242f",
                            zorder=6, lw=2)
            if r.end_year is None:
                ax1.annotate("", xy=(2075, yi), xytext=(2028, yi),
                             arrowprops=dict(arrowstyle="-|>", color="#1a7f37", lw=1.6))
    ax1.set_yticks(range(len(realms)), realms, fontsize=9)
    ax1.set_ylim(-0.6, len(realms) - 0.2)
    ax1.set_title("× = crown destroyed (revolution, abolition, partition, conquest) · "
                  "green arrow = still reigning", fontsize=9.5, loc="left")
    for x, lbl in [(732, "Tours"), (800, "Charlemagne crowned"), (1066, "Hastings"),
                   (1517, "Reformation"), (1648, "Westphalia"), (1789, "French Revolution"),
                   (1918, "1918")]:
        ax1.axvline(x, color="#57606a", lw=0.5, ls=":", alpha=0.6)
        ax1.text(x, len(realms) - 0.28, lbl, rotation=90, fontsize=6.5,
                 color="#57606a", ha="center", va="top")

    # bottom: how many of the twelve wear crowns, per year (computed from the table)
    years = np.arange(476, 2027)
    crowned = np.zeros(len(years))
    for _, r in rl.iterrows():
        crowned += ((years >= r.start_year) & (years <= r.end_plot)).astype(int) * 0
    for realm in realms:
        sub = rl[rl.realm == realm]
        active = np.zeros(len(years), dtype=bool)
        for _, r in sub.iterrows():
            active |= (years >= r.start_year) & (years <= r.end_plot)
        crowned += active
    ax2.fill_between(years, crowned, color=PALETTE[0], alpha=0.25, step="mid")
    ax2.plot(years, crowned, lw=1.8, color=PALETTE[0])
    ax2.annotate("the extinction event:\n1795-1946, eleven crowned → five",
                 (1930, 7.2), xytext=(1520, 3.2), fontsize=8.5, color="#d1242f",
                 arrowprops=dict(arrowstyle="->", color="#d1242f", lw=0.9))
    ax2.set_ylabel("realms with a\nreigning house")
    ax2.set_ylim(0, 12.6)
    ax2.set_xlim(430, 2100)
    ax2.set_xlabel("year")
    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.2, axis="x")
    fig.text(0.01, 0.005,
             "Source: curated royal_lines table (standard reference dates; interregna as gaps); "
             "count strip computed from the table (econlab warehouse).",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_royal_lines")


def main() -> None:
    fig_capital_arc()
    fig_then_vs_now()
    fig_fugger()
    fig_medici()
    fig_ten_dynasties()
    fig_deep_time()
    fig_millennium_walk()
    fig_byzantine_walk()
    fig_royal_lines()


if __name__ == "__main__":
    main()
