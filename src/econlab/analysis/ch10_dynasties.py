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
    save(fig, "10_rothschild_arc")


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
    save(fig, "10_then_vs_now")


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
    save(fig, "10_fugger")


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
    save(fig, "10_ten_dynasties")


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
    save(fig, "10_medici")


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
    save(fig, "10_deep_time")


def main() -> None:
    fig_capital_arc()
    fig_then_vs_now()
    fig_fugger()
    fig_medici()
    fig_ten_dynasties()
    fig_deep_time()


if __name__ == "__main__":
    main()
