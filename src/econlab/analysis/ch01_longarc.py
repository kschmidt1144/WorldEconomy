"""Chapter 1 — The Long Arc: growth over two millennia.

All computations from the warehouse (Maddison panel + reference aggregate,
UN WPP projections). Key methodological choices, documented in the chapter:

- Bloc shares use Maddison's own world aggregate as denominator (1820->2022)
  and our successor-partitioned, span-interpolated bloc sums as numerators.
- Convergence uses the rolling poor-vs-rich growth gap as the primary
  statistic (robust to the composition traps that poison 1990-based betas),
  with sigma reported both unweighted and population-weighted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import new_fig, save, source_note
from .maddison_world import (
    SUCCESSORS,
    load_panel,
    maddison_world_reference_annual,
    successor_partition,
    world_gdp_annual,
)

WEU = {"GBR", "FRA", "DEU", "ITA", "ESP", "PRT", "NLD", "BEL", "CHE", "AUT",
       "SWE", "NOR", "DNK", "FIN", "IRL", "GRC"}
OFFSHOOTS = {"USA", "CAN", "AUS", "NZL"}
BLOCS: dict[str, set[str]] = {
    "China": {"CHN"},
    "India": {"IND"},
    "Western Europe": WEU,
    "Western Offshoots": OFFSHOOTS,
    "Japan": {"JPN"},
}

ERAS = [(1820, 1870), (1870, 1913), (1913, 1950), (1950, 1973),
        (1973, 2000), (2000, 2022)]

FSU_TRANSITION = (
    set(SUCCESSORS["SUN"]) | set(SUCCESSORS["YUG"]) | set(SUCCESSORS["CSK"])
    | {"SUN", "YUG", "CSK"}
)


def _cagr(v1: float, v0: float, years: int) -> float:
    return 100 * ((v1 / v0) ** (1 / years) - 1)


# ---------- data functions ----------

def bloc_shares_annual() -> pd.DataFrame:
    """Share of world GDP per bloc, annual 1820->2022 (% of Maddison world)."""
    ref = maddison_world_reference_annual().set_index("year")["gdp"]
    out = {}
    for name, members in BLOCS.items():
        s = world_gdp_annual(members=members).set_index("year")["gdp"]
        out[name] = 100 * s / ref.reindex(s.index)
    return pd.DataFrame(out)


def growth_eras() -> pd.Series:
    """World GDP-per-capita growth by era, %/yr; includes the deep past."""
    ref = maddison_world_reference_annual().set_index("year")["gdppc"]
    panel = successor_partition(load_panel())
    s1 = panel[panel.year == 1]
    deep = (s1.gdppc * s1["pop"]).sum() / s1["pop"].sum()  # covered economies
    vals = {"1-1820": _cagr(ref[1820], deep, 1819)}
    for a, b in ERAS:
        vals[f"{a}-{b}"] = _cagr(ref[b], ref[a], b - a)
    return pd.Series(vals)


def rolling_growth_gap(window: int = 15, step: int = 5) -> pd.DataFrame:
    """Poorest-quartile minus richest-quartile mean growth over rolling windows.

    Transition economies excluded from windows starting >= 1990 (their
    collapse is regime change, not development dynamics).
    """
    panel = successor_partition(load_panel())
    p = panel.pivot_table(index="entity", columns="year", values="gdppc")
    rows = []
    for a in range(1950, 2023 - window, step):
        b = a + window
        sub = p[[a, b]].dropna()
        if a >= 1990:
            sub = sub[~sub.index.isin(FSU_TRANSITION)]
        q25, q75 = sub[a].quantile([0.25, 0.75])
        g = 100 * ((sub[b] / sub[a]) ** (1 / window) - 1)
        rows.append(
            {
                "start": a,
                "end": b,
                "gap": g[sub[a] <= q25].mean() - g[sub[a] >= q75].mean(),
                "n": len(sub),
            }
        )
    return pd.DataFrame(rows)


def sigma_paths() -> pd.DataFrame:
    """Cross-country dispersion of log GDP pc, 1950->2022, on the balanced
    (1950 & 2022) country set: unweighted and population-weighted."""
    panel = successor_partition(load_panel())
    p = panel.pivot_table(index="entity", columns="year", values="gdppc")
    w = panel.pivot_table(index="entity", columns="year", values="pop")
    common = p[[1950, 2022]].dropna().index
    rows = []
    for y in range(1950, 2023):
        v = np.log(p.loc[common, y].dropna())
        if len(v) < 50:
            continue
        wy = w.loc[v.index, y]
        m = np.average(v, weights=wy)
        rows.append(
            {
                "year": y,
                "unweighted": float(v.std()),
                "pop_weighted": float(np.sqrt(np.average((v - m) ** 2, weights=wy))),
            }
        )
    return pd.DataFrame(rows).set_index("year")


def decomposition() -> pd.DataFrame:
    """World GDP growth = population growth + GDP-pc growth, by era,
    plus the UN-projected population term for 2022->2100."""
    ref = maddison_world_reference_annual().set_index("year")
    rows = []
    for a, b in ERAS:
        rows.append(
            {
                "era": f"{a}-{b}",
                "pop": _cagr(ref.loc[b, "pop"], ref.loc[a, "pop"], b - a),
                "gdppc": _cagr(ref.loc[b, "gdppc"], ref.loc[a, "gdppc"], b - a),
            }
        )
    with connect() as con:
        wpp = con.execute(
            "SELECT year, value FROM obs WHERE series_id='unwpp/TPopulation1July' "
            "AND entity='WLD' AND year IN (2022, 2100)"
        ).df().set_index("year")["value"]
    rows.append(
        {"era": "2022-2100\n(UN medium)", "pop": _cagr(wpp[2100], wpp[2022], 78),
         "gdppc": np.nan}
    )
    return pd.DataFrame(rows).set_index("era")


def world_population_peak() -> tuple[int, float]:
    with connect() as con:
        df = con.execute(
            "SELECT year, value FROM obs WHERE series_id='unwpp/TPopulation1July' "
            "AND entity='WLD' ORDER BY year"
        ).df()
    i = df["value"].idxmax()
    return int(df.loc[i, "year"]), float(df.loc[i, "value"])


# ---------- figures ----------

def fig_bloc_shares() -> None:
    shares = bloc_shares_annual()
    fig, ax = new_fig(
        "Who makes the world's output: 1820-2022",
        subtitle=(
            "Share of world GDP (2011 PPP$). China+India: 45% -> 9% (1950s trough) -> 29%. "
            "The West peaked on the eve of WWI, not in 1950."
        ),
        ylabel="% of world GDP",
    )
    for name in BLOCS:
        ax.plot(shares.index, shares[name], lw=1.8, label=name)
    ax.legend(loc="upper center", ncol=3, fontsize=9)
    ax.set_ylim(0, 45)
    source_note(
        ax,
        "Source: computed from Maddison Project 2023 — bloc sums (successor-partitioned, "
        "span-interpolated) over Maddison's world aggregate (econlab warehouse)",
    )
    save(fig, "01_bloc_shares")


def fig_growth_eras() -> None:
    eras = growth_eras()
    fig, ax = new_fig(
        "World growth per person, by era",
        subtitle=(
            "GDP per capita, %/yr. Eighteen centuries of ~zero; the 1950-73 Golden Age is "
            "still the record; 2000-22 is second — the China effect."
        ),
        ylabel="% per year",
    )
    bars = ax.bar(eras.index, eras.values, color="#1f6feb")
    bars[3].set_color("#d1242f")  # golden age
    for rect, v in zip(bars, eras.values):
        ax.text(rect.get_x() + rect.get_width() / 2, v + 0.05, f"{v:.2f}",
                ha="center", fontsize=9)
    ax.tick_params(axis="x", labelsize=9)
    source_note(ax, "Source: computed from Maddison Project 2023 (econlab warehouse)")
    save(fig, "01_growth_eras")


def fig_convergence() -> None:
    gap = rolling_growth_gap()
    sig = sigma_paths()
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("When did poor countries start catching up?", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    colors = ["#d1242f" if g < 0 else "#1a7f37" for g in gap["gap"]]
    ax1.bar(gap["start"] + 7.5, gap["gap"], width=4.2, color=colors)
    ax1.axhline(0, color="#57606a", lw=0.8)
    ax1.set_title("Poorest-quartile minus richest-quartile growth\n(15-yr windows)",
                  fontsize=10, loc="left")
    ax1.set_ylabel("pp per year")
    ax1.set_xlabel("window midpoint")

    ax2.plot(sig.index, sig["unweighted"], lw=1.8, label="unweighted (each country = 1)")
    ax2.plot(sig.index, sig["pop_weighted"], lw=1.8, label="population-weighted")
    ax2.set_title("Dispersion of log GDP pc (σ), balanced panel", fontsize=10, loc="left")
    ax2.legend(fontsize=9)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(
        0.01, -0.02,
        "Source: computed from Maddison Project 2023. Windows starting ≥1990 exclude "
        "transition (ex-USSR/Yugoslav/Czechoslovak) economies (econlab warehouse)",
        fontsize=8, color="#57606a",
    )
    fig.tight_layout()
    save(fig, "01_convergence")


def fig_decomposition() -> None:
    d = decomposition()
    fig, ax = new_fig(
        "Where world growth comes from - and what's left",
        subtitle=(
            "World GDP growth = population + GDP per person (%/yr). The population term "
            "shrinks to 0.31%/yr over 2022-2100 (UN medium) - future growth is productivity or nothing."
        ),
        ylabel="% per year",
    )
    x = np.arange(len(d))
    ax.bar(x, d["pop"], label="population", color="#9a6700")
    ax.bar(x, d["gdppc"].fillna(0), bottom=d["pop"], label="GDP per person", color="#1f6feb")
    # the unknown future productivity term
    last = len(d) - 1
    recent = d["gdppc"].iloc[-2]
    ax.bar([last], [recent], bottom=d["pop"].iloc[-1], color="#1f6feb", alpha=0.25,
           hatch="//", label="productivity: to be earned")
    ax.text(last, d["pop"].iloc[-1] + recent / 2, "?", ha="center", fontsize=16,
            fontweight="bold", color="#1f6feb")
    ax.set_xticks(x, d.index, fontsize=8.5)
    ax.legend(fontsize=9)
    source_note(
        ax,
        "Source: computed from Maddison Project 2023 + UN WPP 2024 medium variant (econlab warehouse)",
    )
    save(fig, "01_decomposition")


# when each country "boarded the train": first year GDP/capita crossed a fixed
# real threshold (~escape from Malthus) and the region each belongs to
TAKEOFF_SET = {
    "NLD": "W. Europe", "GBR": "W. Europe", "USA": "Anglo-offshoots",
    "FRA": "W. Europe", "DEU": "W. Europe", "ARG": "Latin America",
    "ITA": "W. Europe", "ESP": "W. Europe", "JPN": "Asia", "MEX": "Latin America",
    "RUS": "E. Europe", "BRA": "Latin America", "THA": "Asia", "IDN": "Asia",
    "CHN": "Asia", "IND": "Asia", "NGA": "Africa", "GHA": "Africa",
}


def takeoff_dates(threshold: float = 3000) -> pd.DataFrame:
    """First year each country's GDP per capita sustainably crossed `threshold`."""
    codes = list(TAKEOFF_SET)
    with connect() as con:
        df = con.execute(
            f"SELECT entity, min(year) FILTER (WHERE value >= {threshold}) AS takeoff "
            f"FROM obs WHERE series_id='maddison/gdppc' "
            f"AND entity IN ({','.join(['?'] * len(codes))}) GROUP BY entity",
            codes,
        ).df().dropna()
    df["region"] = df.entity.map(TAKEOFF_SET)
    df["name"] = df.entity.map({
        "NLD": "Netherlands", "GBR": "Britain", "USA": "United States", "FRA": "France",
        "DEU": "Germany", "ARG": "Argentina", "ITA": "Italy", "ESP": "Spain",
        "JPN": "Japan", "MEX": "Mexico", "RUS": "Russia", "BRA": "Brazil",
        "THA": "Thailand", "IDN": "Indonesia", "CHN": "China", "IND": "India",
        "NGA": "Nigeria", "GHA": "Ghana"})
    return df.sort_values("takeoff").reset_index(drop=True)


def fig_takeoff_dates() -> None:
    import matplotlib.pyplot as plt

    td = takeoff_dates()
    print("[ch01] takeoff span:", int(td.takeoff.min()), td.name.iloc[0],
          "->", int(td.takeoff.max()), td.name.iloc[-1])
    region_color = {"W. Europe": "#1f6feb", "Anglo-offshoots": "#0969da",
                    "Latin America": "#9a6700", "E. Europe": "#8250df",
                    "Asia": "#1a7f37", "Africa": "#d1242f"}
    fig, ax = new_fig(
        "When each nation boarded the train: the diffusion of modern growth",
        subtitle="First year GDP per capita crossed ~$3,000 (2011 PPP\\$), the rough escape from Malthusian subsistence "
        "(Maddison). Five centuries separate the first economy from the last.",
        ylabel=None,
    )
    for i, r in td.iterrows():
        c = region_color[r["region"]]
        ax.plot([r["takeoff"], r["takeoff"]], [i, i], marker="o", ms=9, color=c)
        ax.annotate(f"{r['name']} ({int(r['takeoff'])})", (r["takeoff"], i),
                    xytext=(10, 0), textcoords="offset points", va="center", fontsize=8.5, color="#24292f")
    ax.set_yticks([])
    ax.set_ylim(-1, len(td))
    ax.invert_yaxis()
    ax.set_xlim(1480, 2060)
    ax.set_xlabel("year of takeoff (GDP/capita first crossed ~$3,000)")
    for x, lbl in [(1760, "Industrial\nRevolution"), (2011, "")]:
        ax.axvline(x, color="#57606a", lw=0.7, ls=":")
    ax.text(1760, len(td) - 0.5, "Industrial Revolution", rotation=90, fontsize=8,
            color="#57606a", va="bottom", ha="right")
    handles = [plt.Line2D([0], [0], marker="o", ls="", color=c, label=reg)
               for reg, c in region_color.items()]
    ax.legend(handles=handles, fontsize=8, loc="lower left", ncol=2)
    source_note(ax, "Source: computed from Maddison Project 2023 GDP per capita (econlab warehouse)")
    save(fig, "01_takeoff_dates")


def main() -> None:
    fig_bloc_shares()
    fig_growth_eras()
    fig_convergence()
    fig_takeoff_dates()
    fig_decomposition()


if __name__ == "__main__":
    main()
