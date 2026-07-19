"""Chapter 5 — Structural forces: demography, energy, and the shape of trade."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note


# ---------- data ----------

def median_ages() -> pd.DataFrame:
    with connect() as con:
        df = con.execute(
            "SELECT entity, year, value FROM obs WHERE series_id='unwpp/MedianAgePop' "
            "AND entity IN ('CHN','IND','USA','JPN','KOR','NGA','WLD') ORDER BY year"
        ).df()
    return df.pivot(index="year", columns="entity", values="value")


def energy_intensity() -> pd.Series:
    """World primary energy (TWh) per billion of real world GDP (2015$)."""
    with connect() as con:
        en = con.execute(
            "SELECT year, value FROM obs WHERE series_id='energy/primary_energy_consumption' "
            "AND entity='WLD'"
        ).df().set_index("year")["value"]
        gdp = con.execute(
            "SELECT year, value FROM obs WHERE series_id='wdi/NY.GDP.MKTP.KD' AND entity='WLD'"
        ).df().set_index("year")["value"]
    common = en.index.intersection(gdp.index)
    return (en[common] / (gdp[common] / 1e9)).rename("twh_per_bn")


def energy_vs_income() -> pd.DataFrame:
    with connect() as con:
        e = con.execute(
            "SELECT entity, max_by(value, year) v FROM obs "
            "WHERE series_id='energy/energy_per_capita' GROUP BY 1"
        ).df().set_index("entity")["v"]
        pc = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='imf/PPPPC' AND year=2025"
        ).df().set_index("entity")["value"]
        pop = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='imf/LP' AND year=2025"
        ).df().set_index("entity")["value"]
    return pd.DataFrame({"energy_pc": e, "gdppc": pc, "pop": pop}).dropna()


def export_shares() -> pd.DataFrame:
    with connect() as con:
        ex = con.execute(
            "SELECT year, entity, value FROM obs WHERE series_id='baci/exports_total'"
        ).df()
    tot = ex.groupby("year")["value"].sum()
    out = {}
    for c in ("CHN", "USA", "DEU", "JPN"):
        s = ex[ex.entity == c].set_index("year")["value"]
        out[c] = 100 * s / tot
    return pd.DataFrame(out)


def top_supplier_counts() -> pd.DataFrame:
    """For each year: number of countries whose largest import supplier is X."""
    with connect() as con:
        tr = con.execute("SELECT year, exporter, importer, value_usd FROM trade").df()
    rows = []
    for y, s in tr.groupby("year"):
        top = s.loc[s.groupby("importer")["value_usd"].idxmax()]
        counts = top["exporter"].value_counts()
        rows.append({"year": y, "CHN": int(counts.get("CHN", 0)),
                     "USA": int(counts.get("USA", 0)), "DEU": int(counts.get("DEU", 0))})
    return pd.DataFrame(rows).set_index("year")


def openness() -> tuple[pd.Series, pd.Series]:
    """(JST 18-economy mean 1870-2015, WDI world trade/GDP 1970->)."""
    with connect() as con:
        jo = con.execute(
            "SELECT entity, year, series_id, value FROM obs WHERE series_id IN "
            "('jst/exports','jst/imports','jst/gdp')"
        ).df()
        wdi = con.execute(
            "SELECT year, value FROM obs WHERE series_id='wdi/NE.TRD.GNFS.ZS' AND entity='WLD' "
            "ORDER BY year"
        ).df().set_index("year")["value"]
    jp = jo.pivot_table(index=["entity", "year"], columns="series_id", values="value").dropna()
    jp["open"] = 100 * (jp["jst/exports"] + jp["jst/imports"]) / jp["jst/gdp"]
    jst = jp.groupby("year")["open"].mean()
    return jst, wdi


def commodity_real_index(base: int = 1960) -> pd.DataFrame:
    """Real (CPI-deflated) commodity prices, indexed to base=100.

    Equal-weight index over a broad industrial+agricultural basket, plus real
    oil on its own — the raw material of the commodity-supercycle story.
    """
    basket = ["oil", "copper", "aluminum", "iron_ore", "nickel",
              "wheat", "maize", "cotton", "coffee", "sugar"]
    with connect() as con:
        nom = con.execute(
            "SELECT replace(series_id,'pinksheet/','') AS c, year, avg(value) v "
            "FROM obs WHERE series_id LIKE 'pinksheet/%' GROUP BY 1,2"
        ).df().pivot(index="year", columns="c", values="v")
        cpi = con.execute(
            "SELECT year, avg(value) v FROM obs WHERE series_id='shiller/cpi' GROUP BY 1"
        ).df().set_index("year")["v"]
    cpi = cpi / cpi.loc[base]
    real = nom.div(cpi, axis=0)
    indexed = real.div(real.loc[base]).mul(100)
    out = pd.DataFrame(index=indexed.index)
    out["basket"] = indexed[basket].mean(axis=1)
    out["oil"] = indexed["oil"]
    return out.dropna(subset=["basket"])


# ---------- figures ----------

def fig_median_age() -> None:
    ma = median_ages()
    fig, ax = new_fig(
        "The age of aging, 1950-2100",
        subtitle="Median age, UN medium variant (projection right of the line). Korea reaches 57, China 52 by 2050; Nigeria stays under 25.",
        ylabel="median age, years",
    )
    names = {"CHN": "China", "IND": "India", "USA": "United States", "JPN": "Japan",
             "KOR": "South Korea", "NGA": "Nigeria", "WLD": "World"}
    for i, c in enumerate(["CHN", "KOR", "JPN", "USA", "IND", "NGA", "WLD"]):
        lw = 3 if c == "WLD" else 1.7
        ax.plot(ma.index, ma[c], lw=lw, color=PALETTE[i % len(PALETTE)],
                label=names[c], ls="-" if c != "WLD" else "--")
    ax.axvline(2024, color="#57606a", lw=0.8, ls=":")
    ax.legend(fontsize=8.5, ncol=2)
    source_note(ax, "Source: computed from UN WPP 2024 (econlab warehouse)")
    save(fig, "08_median_age")


def fig_energy() -> None:
    import matplotlib.pyplot as plt

    scat = energy_vs_income()
    inten = energy_intensity()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Energy is what development is made of", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    ax1.scatter(scat.gdppc, scat.energy_pc, s=np.sqrt(scat["pop"] / 1e6) * 2.5,
                alpha=0.6, color=PALETTE[0])
    for code in ("USA", "CHN", "IND", "NGA", "DEU", "ISL"):
        if code in scat.index:
            r = scat.loc[code]
            ax1.annotate(code, (r.gdppc, r.energy_pc), fontsize=8,
                         xytext=(0, 6), textcoords="offset points", ha="center")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("GDP per capita 2025, PPP$ (log)")
    ax1.set_ylabel("energy use per person, kWh/yr (log)")
    ax1.set_title("No rich low-energy countries exist", fontsize=10, loc="left")

    ax2.plot(inten.index, inten.values, lw=2, color=PALETTE[2])
    ax2.set_title("Energy per unit of world GDP (-42% since 1973)", fontsize=10, loc="left")
    ax2.set_ylabel("TWh per $bn of GDP (2015$)")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from OWID-energy (EI/Ember), IMF, World Bank (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "08_energy")


def fig_china_shock() -> None:
    import matplotlib.pyplot as plt

    sh = export_shares()
    ts = top_supplier_counts()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The China trade shock, in two charts", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    for i, c in enumerate(["CHN", "USA", "DEU", "JPN"]):
        ax1.plot(sh.index, sh[c], lw=2, color=PALETTE[i], label=c)
    ax1.set_title("Share of world goods exports", fontsize=10, loc="left")
    ax1.set_ylabel("% of world exports")
    ax1.legend(fontsize=9)

    for i, c in enumerate(["CHN", "USA", "DEU"]):
        ax2.plot(ts.index, ts[c], lw=2, color=PALETTE[i], label=c)
    ax2.set_title("Countries whose #1 import supplier is…", fontsize=10, loc="left")
    ax2.set_ylabel("number of countries")
    ax2.legend(fontsize=9)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from CEPII BACI bilateral flows (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "08_china_shock")


def fig_globalization_waves() -> None:
    jst, wdi = openness()
    fig, ax = new_fig(
        "Two waves of globalization - and today's plateau",
        subtitle="Trade openness. Blue: mean of 18 (mostly rich) economies, JST. Red: world trade/GDP, World Bank. Different universes - the shapes, not the levels, are the story.",
        ylabel="(exports + imports) / GDP, %",
    )
    ax.plot(jst.index, jst.values, lw=2, color=PALETTE[0],
            label="18-economy mean (JST, 1870-2015)")
    ax.plot(wdi.index, wdi.values, lw=2, color=PALETTE[1],
            label="world (WDI, 1970-2024)")
    for x, label in [(1913, "1913 peak"), (1938, "autarky trough"), (2008, "2008 peak")]:
        ax.axvline(x, color="#57606a", lw=0.7, ls=":")
        ax.text(x, ax.get_ylim()[1] * 0.97, label, rotation=90, va="top",
                fontsize=8, color="#57606a")
    ax.legend(fontsize=9, loc="upper left")
    source_note(ax, "Source: computed from JST Macrohistory + World Bank WDI (econlab warehouse)")
    save(fig, "08_globalization_waves")


def fig_commodity_supercycles() -> None:
    ci = commodity_real_index()
    peak2008 = ci.loc[2008, "oil"]
    print(f"[ch08] real commodity basket 1960=100 -> 2025={ci['basket'].iloc[-1]:.0f}; "
          f"real oil 2008 peak={peak2008:.0f}")
    fig, ax = new_fig(
        "Commodity supercycles around a flat real trend",
        subtitle="Real (CPI-deflated) commodity prices, 1960 = 100. After 65 years of booming demand the broad basket ends "
        "near where it began (97) — the supercycles are violent deviations around a flat-to-falling real trend.",
        ylabel="real price index, 1960 = 100",
    )
    ax.plot(ci.index, ci["basket"], lw=2.6, color=PALETTE[2],
            label="broad basket (10 commodities, equal-weight)")
    ax.plot(ci.index, ci["oil"], lw=1.4, color=PALETTE[1], alpha=0.75, label="crude oil (real)")
    ax.axhline(100, color="#57606a", lw=0.9, ls=":")
    ax.annotate("1970s oil shocks", (1980, 812), xytext=(1963, 760), fontsize=8.5, color="#57606a",
                arrowprops=dict(arrowstyle="->", color="#57606a"))
    ax.annotate("2000s China\nsupercycle", (2011, 839), xytext=(2001, 700), fontsize=8.5, color="#57606a",
                arrowprops=dict(arrowstyle="->", color="#57606a"))
    ax.annotate("1999: the real low\n(basket 42% below 1960)", (1999, 58), xytext=(1999, 250),
                fontsize=8.5, color="#1a7f37", ha="center",
                arrowprops=dict(arrowstyle="->", color="#1a7f37"))
    ax.legend(fontsize=9, loc="upper right")
    source_note(ax, "Source: computed from World Bank Pink Sheet deflated by US CPI (Shiller) (econlab warehouse)")
    save(fig, "08_commodity_supercycles")


def main() -> None:
    fig_median_age()
    fig_energy()
    fig_china_shock()
    fig_commodity_supercycles()
    fig_globalization_waves()


if __name__ == "__main__":
    main()
