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


def main() -> None:
    fig_capital_arc()
    fig_then_vs_now()


if __name__ == "__main__":
    main()
