"""World aggregation over the Maddison panel — done carefully.

Two traps this module exists to handle:

1. MPD2023 carries historical composites (Former USSR, Czechoslovakia,
   Yugoslavia) IN PARALLEL with their successor states over overlapping years
   (we verified: 1950 USSR pop == sum of 15 FSU states to 6 decimal places).
   A naive sum double-counts them. We partition at a per-composite *handoff
   year* — the first year all present successors have both gdppc and pop —
   using the composite before it and successors after.

2. Country coverage is ragged; a naive annual sum sawtooths as economies
   enter/exit. We interpolate each economy within its own observed span
   (log-linear gdppc, linear pop) before summing, and never extrapolate.

Cross-check: the MPD2023 'Regional data' sheet ships Maddison's own world
GDP pc and world population (1820->2022) — maddison_world_reference() reads it
so figures can overlay our bottom-up sum against their aggregate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import RAW
from ..model import connect

SUCCESSORS = {
    "SUN": ["ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LTU", "LVA",
            "MDA", "RUS", "TJK", "TKM", "UZB", "UKR"],
    "CSK": ["CZE", "SVK"],
    "YUG": ["BIH", "HRV", "MKD", "MNE", "SRB", "SVN", "XKX"],
}

DEEP_BENCHMARK_YEARS = [1, 1000, 1500, 1600, 1700]


def load_panel() -> pd.DataFrame:
    """entity, year, gdppc, pop — inner join of the two Maddison series."""
    with connect() as con:
        return con.execute(
            """
            SELECT g.entity, g.year, g.value AS gdppc, p.value AS pop
            FROM obs g
            JOIN obs p ON g.entity = p.entity AND g.year = p.year
                       AND p.series_id = 'maddison/pop'
            WHERE g.series_id = 'maddison/gdppc'
            ORDER BY g.entity, g.year
            """
        ).df()


def successor_partition(panel: pd.DataFrame) -> pd.DataFrame:
    """Resolve composite/successor overlap so every territory is counted once."""
    out = panel
    entities = set(panel["entity"])
    for comp, succs in SUCCESSORS.items():
        present = [s for s in succs if s in entities]
        if comp not in entities or not present:
            continue
        firsts = panel[panel["entity"].isin(present)].groupby("entity")["year"].min()
        handoff = int(firsts.max())  # all successors online from here
        out = out[
            ~(
                ((out["entity"] == comp) & (out["year"] >= handoff))
                | (out["entity"].isin(present) & (out["year"] < handoff))
            )
        ]
    return out


def world_gdp_annual(start: int = 1820, end: int = 2022) -> pd.DataFrame:
    """Bottom-up world GDP: interpolate each economy within its span, then sum.

    Returns year, gdp (2011 int'l $), n_economies contributing.
    """
    panel = successor_partition(load_panel())
    years = np.arange(start, end + 1)
    gdp = np.zeros(len(years))
    n = np.zeros(len(years), dtype=int)

    for _, sub in panel.groupby("entity"):
        sub = sub[(sub["year"] >= start - 50)]  # tolerate spans starting a bit before
        if sub.empty:
            continue
        x = sub["year"].to_numpy(dtype=float)
        lo, hi = max(x.min(), start), min(x.max(), end)
        if lo > hi:
            continue
        mask = (years >= lo) & (years <= hi)
        xs = years[mask].astype(float)
        gdppc = np.exp(np.interp(xs, x, np.log(sub["gdppc"].to_numpy())))
        pop = np.interp(xs, x, sub["pop"].to_numpy())
        gdp[mask] += gdppc * pop
        n[mask] += 1

    return pd.DataFrame({"year": years, "gdp": gdp, "n_economies": n})


def deep_benchmarks() -> pd.DataFrame:
    """Pre-1820 'world' points: sum over covered economies only (a lower bound).

    Returns year, gdp, n_economies for the canonical benchmark years.
    """
    panel = successor_partition(load_panel())
    rows = []
    for y in DEEP_BENCHMARK_YEARS:
        sub = panel[panel["year"] == y]
        if len(sub):
            rows.append({"year": y, "gdp": float((sub.gdppc * sub["pop"]).sum()),
                         "n_economies": len(sub)})
    return pd.DataFrame(rows)


def maddison_world_reference() -> pd.DataFrame:
    """Maddison's own world aggregate from the 'Regional data' sheet (1820->2022).

    Returns year, gdppc, pop, gdp. Population sheet unit is thousands.
    """
    raw = pd.read_excel(
        RAW / "maddison" / "mpd2023_web.xlsx", sheet_name="Regional data", header=None
    )
    df = pd.DataFrame(
        {
            "year": pd.to_numeric(raw.iloc[2:, 0], errors="coerce"),
            "gdppc": pd.to_numeric(raw.iloc[2:, 9], errors="coerce"),
            "pop": pd.to_numeric(raw.iloc[2:, 19], errors="coerce") * 1_000.0,
        }
    ).dropna()
    df["year"] = df["year"].astype(int)
    df["gdp"] = df["gdppc"] * df["pop"]
    return df.reset_index(drop=True)
