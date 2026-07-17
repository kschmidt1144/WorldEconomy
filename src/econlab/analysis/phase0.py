"""Phase 0 figures — first light. Every number computed from the warehouse.

Run: `econ figures` (or `uv run python -m econlab.analysis.phase0`).
"""

from __future__ import annotations

import pandas as pd

from ..model import connect
from ..viz import new_fig, save, source_note


def fig_world_gdp() -> None:
    """World GDP, 1 CE -> 2022: bottom-up sum, validated against Maddison's own aggregate."""
    from .maddison_world import deep_benchmarks, maddison_world_reference, world_gdp_annual

    line = world_gdp_annual(start=1950)  # near-complete country coverage from 1950
    early = deep_benchmarks()
    ref = maddison_world_reference()

    fig, ax = new_fig(
        "World GDP, year 1 to 2022",
        subtitle=(
            "Blue line: our sum over ~170 economies from 1950 (USSR/Yugoslav/Czechoslovak overlaps resolved). "
            "x: Maddison's own world aggregate 1820->. Pre-1820 dots: covered economies only - a lower bound."
        ),
        ylabel="trillion 2011 int'l $ (log scale)",
    )
    ax.plot(early.year, early.gdp / 1e12, "o--", ms=5, lw=1, alpha=0.8,
            label="benchmark years (partial coverage)")
    ax.plot(ref.year, ref.gdp / 1e12, "x", ms=6, color="#1a7f37", alpha=0.9,
            label="Maddison world aggregate")
    ax.plot(line.year, line.gdp / 1e12, lw=2, label="bottom-up sum (econlab, 1950->)")
    for _, r in early.iterrows():
        ax.annotate(f"{int(r.n_economies)} econ.", (r.year, r.gdp / 1e12),
                    textcoords="offset points", xytext=(0, 8), fontsize=7.5, color="#57606a")
    ax.set_yscale("log")
    ax.set_xlim(-60, 2060)
    ax.legend(loc="center left", fontsize=9)
    source_note(ax, "Source: computed from Maddison Project Database 2023 (econlab warehouse)")
    save(fig, "00_world_gdp_long_run")


def fig_divergence() -> None:
    """The Great Divergence and the late-20th-century (re)convergence."""
    countries = {"GBR": "Britain", "USA": "United States", "JPN": "Japan",
                 "CHN": "China", "IND": "India"}
    with connect() as con:
        df = con.execute(
            """
            SELECT entity, year, value
            FROM obs
            WHERE series_id = 'maddison/gdppc'
              AND entity IN ('GBR','USA','JPN','CHN','IND')
              AND year >= 1500
            ORDER BY year
            """
        ).df()

    fig, ax = new_fig(
        "The Great Divergence - and the catch-up",
        subtitle="GDP per capita, 1500-2022. China ~= Britain in 1500; 30x apart by 1950; converging since 1980.",
        ylabel="2011 int'l $ per person (log scale)",
    )
    for code, label in countries.items():
        sub = df[df.entity == code]
        ax.plot(sub.year, sub.value, marker="o", ms=2.5, lw=1.6, label=label)
    ax.set_yscale("log")
    ax.legend(loc="upper left")
    source_note(ax, "Source: computed from Maddison Project Database 2023 (econlab warehouse)")
    save(fig, "00_great_divergence")


def fig_us_inflation() -> None:
    """US CPI inflation, monthly year-over-year, 1872 -> present."""
    with connect() as con:
        df = con.execute(
            "SELECT date, value FROM obs WHERE series_id='shiller/cpi' ORDER BY date"
        ).df()
    df["date"] = pd.to_datetime(df["date"])
    df["yoy"] = (df["value"] / df["value"].shift(12) - 1) * 100
    df = df.dropna(subset=["yoy"])

    fig, ax = new_fig(
        "US inflation, 1872 to today",
        subtitle="CPI, % change vs a year earlier, monthly. Wars and the 1970s stand out; deflation vanishes after WWII.",
        ylabel="% per year",
    )
    ax.plot(df.date, df.yoy, lw=0.9)
    ax.axhline(0, color="#57606a", lw=0.8)
    source_note(ax, "Source: computed from Robert Shiller's ie_data.xls (econlab warehouse)")
    save(fig, "00_us_inflation")


def fig_us_debt_gdp() -> None:
    """US public debt / GDP: JST 1870-2020, extended to 2024 with FiscalData / WDI."""
    with connect() as con:
        jst = con.execute(
            "SELECT year, value * 100 AS pct FROM obs "
            "WHERE series_id='jst/debtgdp' AND entity='USA' ORDER BY year"
        ).df()
        ext = con.execute(
            """
            SELECT d.year, d.value / g.value * 100 AS pct
            FROM obs d
            JOIN obs g ON g.entity = 'USA' AND g.year = d.year
                       AND g.series_id = 'wdi/NY.GDP.MKTP.CD'
            WHERE d.series_id = 'fiscaldata/debt_outstanding' AND d.entity = 'USA'
              AND d.year >= 1960
            ORDER BY d.year
            """
        ).df()

    fig, ax = new_fig(
        "US public debt / GDP, 1870 to 2024",
        subtitle="Solid: JST (federal debt). Dashed: gross federal debt (Treasury) / GDP (World Bank) - a slightly wider concept.",
        ylabel="% of GDP",
    )
    ax.plot(jst.year, jst.pct, lw=2, label="JST macrohistory (1870-2020)")
    ax.plot(ext.year, ext.pct, "--", lw=1.6, label="Treasury debt / WDI GDP (1960-2024)")
    ax.legend(loc="upper left")
    source_note(
        ax,
        "Source: computed from JST Macrohistory R6, Treasury FiscalData, World Bank WDI (econlab warehouse)",
    )
    save(fig, "00_us_debt_gdp")


def main() -> None:
    fig_world_gdp()
    fig_divergence()
    fig_us_inflation()
    fig_us_debt_gdp()


if __name__ == "__main__":
    main()
