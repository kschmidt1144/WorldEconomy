"""Choropleth: farm real estate value per acre, by state (NASS 2025).

Pure matplotlib over public-domain Census/Natural-Earth-derived state
polygons — no GIS dependencies. Contiguous 48 (AK/HI noted in subtitle).
"""

from __future__ import annotations

import json

import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import LogNorm
from matplotlib.patches import Polygon as MplPolygon

from ..fetch import download
from ..model import connect
from ..viz import save

GEOJSON_URL = ("https://raw.githubusercontent.com/PublicaMundi/MappingAPI/"
               "master/data/geojson/us-states.json")
SKIP = {"Alaska", "Hawaii", "Puerto Rico"}


def state_values(year: int = 2025) -> dict[str, float]:
    """state NAME -> $/acre (joins warehouse entities for names)."""
    with connect() as con:
        df = con.execute(
            """
            SELECT e.name, o.value FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='nass/farm_realestate_per_acre'
              AND o.year = ? AND o.entity LIKE 'US-%'
            """, [year],
        ).df()
    return dict(zip(df.name, df.value))


def fig_land_value_map(year: int = 2025) -> None:
    import matplotlib.pyplot as plt

    geo = download("geo", GEOJSON_URL, "us-states.json")
    gj = json.load(open(geo))
    vals = state_values(year)
    with connect() as con:
        us_avg = con.execute(
            "SELECT value FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
            "AND entity='USA' AND year=?", [year],
        ).fetchone()[0]

    patches, colors = [], []
    for f in gj["features"]:
        name = f["properties"]["name"]
        if name in SKIP or name not in vals:
            continue
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            patches.append(MplPolygon(np.array(poly[0]), closed=True))
            colors.append(vals[name])

    fig, ax = plt.subplots(figsize=(12.5, 7.5))
    norm = LogNorm(vmin=600, vmax=20_000)
    pc = PatchCollection(patches, cmap="YlGn", norm=norm, edgecolor="white", lw=0.7)
    pc.set_array(np.array(colors))
    ax.add_collection(pc)
    ax.set_xlim(-125, -66)
    ax.set_ylim(24, 50)
    ax.set_aspect(1.25)
    ax.axis("off")

    ax.set_title(f"What an acre of American farmland costs, {year}",
                 loc="left", fontweight="bold", fontsize=14, pad=26)
    ax.text(0, 1.02,
            f"USDA NASS farm real estate (land + buildings), \\$/acre by state. US average: \\${us_avg:,.0f}; "
            f"top: Rhode Island \\${vals.get('Rhode Island', 0):,.0f}. AK/HI not surveyed. "
            "Farmland is ~39% of US land — urban acres (3%) trade orders of magnitude higher.",
            transform=ax.transAxes, fontsize=9, color="#57606a")

    # annotate the extremes (NJ label pushed offshore to clear the dark polygon)
    anns = [("Iowa", (-93.5, 42.1), "center"), ("California", (-120.4, 37.2), "center"),
            ("Wyoming", (-107.5, 43.0), "center"), ("New Mexico", (-106.1, 34.4), "center"),
            ("Texas", (-99.3, 31.4), "center")]
    for name, xy, ha in anns:
        if name in vals:
            ax.annotate(f"{name}\n\\${vals[name]:,.0f}", xy, fontsize=8, ha=ha, color="#1f2328")
    if "New Jersey" in vals:
        ax.annotate(f"New Jersey \\${vals['New Jersey']:,.0f}", (-74.6, 40.0),
                    xytext=(-70.5, 37.8), fontsize=8, ha="left", color="#1f2328",
                    arrowprops=dict(arrowstyle="-", color="#57606a", lw=0.7))

    cbar = fig.colorbar(pc, ax=ax, shrink=0.65, pad=0.01,
                        ticks=[600, 1000, 2000, 4000, 8000, 16000])
    cbar.ax.set_yticklabels(["$600", "$1k", "$2k", "$4k", "$8k", "$16k"])
    cbar.set_label("$ per acre (log scale)", fontsize=9)

    fig.text(0.01, 0.01,
             "Source: computed from USDA NASS Land Values 2025 Summary; boundaries: US Census/PublicaMundi (econlab warehouse)",
             fontsize=8, color="#57606a")
    save(fig, "09_land_value_map")


COUNTIES_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
NON_CONUS_FIPS = {"02", "15", "72"}  # AK, HI, PR


def fig_county_land_value_map(year: int = 2022) -> None:
    import matplotlib.pyplot as plt

    geo = download("geo", COUNTIES_URL, "geojson-counties-fips.json")
    gj = json.load(open(geo))
    with connect() as con:
        df = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='agcensus/agland_value_per_acre' "
            "AND year=?", [year],
        ).df()
        top = con.execute(
            """
            SELECT e.name, o.value FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='agcensus/agland_value_per_acre' AND o.year=?
            ORDER BY o.value DESC LIMIT 1
            """, [year],
        ).fetchone()
    vals = {e[3:]: v for e, v in zip(df.entity, df.value)}  # strip 'US-' -> FIPS

    med = float(np.median(list(vals.values())))
    lo_q, hi_q = np.percentile(list(vals.values()), [1, 99])

    patches, colors = [], []
    for f in gj["features"]:
        fips = f["id"]
        if fips[:2] in NON_CONUS_FIPS or fips not in vals:
            continue
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            patches.append(MplPolygon(np.array(poly[0]), closed=True))
            colors.append(vals[fips])

    fig, ax = plt.subplots(figsize=(13, 7.8))
    norm = LogNorm(vmin=max(lo_q, 200), vmax=hi_q)
    pc = PatchCollection(patches, cmap="YlGn", norm=norm, edgecolor="none", lw=0)
    pc.set_array(np.array(colors))
    ax.add_collection(pc)
    ax.set_xlim(-125, -66)
    ax.set_ylim(24, 50)
    ax.set_aspect(1.25)
    ax.axis("off")

    ax.set_title(f"Every county's acre: US agricultural land value, {year}",
                 loc="left", fontweight="bold", fontsize=14, pad=26)
    ax.text(0, 1.02,
            f"Census of Agriculture: ag land & buildings, \\$/acre, {len(vals):,} counties. "
            f"Median county: \\${med:,.0f}. Top: {top[0]} \\${top[1]:,.0f}. "
            "Farms only — urban cores are blank or fringe-priced.",
            transform=ax.transAxes, fontsize=9, color="#57606a")

    cbar = fig.colorbar(pc, ax=ax, shrink=0.65, pad=0.01,
                        ticks=[500, 1000, 2000, 4000, 8000, 16000, 32000])
    cbar.ax.set_yticklabels(["$500", "$1k", "$2k", "$4k", "$8k", "$16k", "$32k"])
    cbar.set_label("$ per acre (log scale, 1st-99th pctile)", fontsize=9)

    fig.text(0.01, 0.01,
             "Source: computed from USDA NASS Census of Agriculture 2022 bulk (QuickStats); "
             "boundaries: US Census/plotly (econlab warehouse)",
             fontsize=8, color="#57606a")
    save(fig, "09_county_land_value_map")


def _cpi_annual() -> "pd.Series":
    """Long CPI: Shiller 1871-> (annual means) — deflates the 175-yr land panel."""
    import pandas as pd  # noqa: F401

    with connect() as con:
        return con.execute(
            "SELECT year, avg(value) v FROM obs WHERE series_id='shiller/cpi' "
            "GROUP BY 1 ORDER BY 1"
        ).df().set_index("year")["v"]


def fig_county_change_map(y0: int = 2012, y1: int = 2022) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    geo = download("geo", COUNTIES_URL, "geojson-counties-fips.json")
    gj = json.load(open(geo))
    with connect() as con:
        df = con.execute(
            """
            SELECT a.entity, a.value AS v1, b.value AS v0
            FROM obs a JOIN obs b USING (entity)
            WHERE a.series_id='agcensus/agland_value_per_acre' AND a.year=?
              AND b.series_id='agcensus/agland_value_per_acre' AND b.year=?
            """, [y1, y0],
        ).df()
    cpi = _cpi_annual()
    infl = cpi[y1] / cpi[y0]
    df["real_chg"] = 100 * ((df.v1 / df.v0) / infl - 1)
    vals = {e[3:]: c for e, c in zip(df.entity, df.real_chg)}

    patches, colors = [], []
    for f in gj["features"]:
        fips = f["id"]
        if fips[:2] in NON_CONUS_FIPS or fips not in vals:
            continue
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            patches.append(MplPolygon(np.array(poly[0]), closed=True))
            colors.append(vals[fips])

    lo, hi = np.percentile(list(vals.values()), [2, 98])
    fig, ax = plt.subplots(figsize=(13, 7.8))
    norm = TwoSlopeNorm(vmin=min(lo, -1), vcenter=0, vmax=max(hi, 1))
    pc = PatchCollection(patches, cmap="RdYlGn", norm=norm, edgecolor="none")
    pc.set_array(np.array(colors))
    ax.add_collection(pc)
    ax.set_xlim(-125, -66)
    ax.set_ylim(24, 50)
    ax.set_aspect(1.25)
    ax.axis("off")

    med = float(np.median(list(vals.values())))
    ax.set_title(f"Where the acre gained and lost: real change, {y0} → {y1}",
                 loc="left", fontweight="bold", fontsize=14, pad=26)
    ax.text(0, 1.02,
            f"Census of Agriculture, CPI-deflated change in ag land \\$/acre ({len(vals):,} counties; "
            f"inflation over the decade: {100*(infl-1):.0f}%). Median county: {med:+.0f}% real. "
            "Green = beat inflation; red = lost real value.",
            transform=ax.transAxes, fontsize=9, color="#57606a")
    cbar = fig.colorbar(pc, ax=ax, shrink=0.65, pad=0.01)
    cbar.set_label("real % change (2nd–98th pctile clamp)", fontsize=9)
    fig.text(0.01, 0.01,
             "Source: computed from USDA NASS Census of Agriculture bulks + CPI (econlab warehouse)",
             fontsize=8, color="#57606a")
    save(fig, "09_county_change_map")


def fig_land_value_history() -> None:
    import matplotlib.pyplot as plt

    from ..viz import PALETTE

    with connect() as con:
        df = con.execute(
            "SELECT entity, year, value FROM obs WHERE "
            "series_id='agsurvey/farm_realestate_per_acre' "
            "AND entity IN ('USA','US-IA','US-CA','US-TX','US-NJ') ORDER BY year"
        ).df()
    cpi = _cpi_annual()
    df = df[df.year >= int(cpi.index.min())]  # real series begins with CPI (1871)
    base = cpi[df.year.max()]
    df["real"] = df.value * df.year.map(lambda y: base / cpi[y])
    wide = df.pivot(index="year", columns="entity", values="real")

    fig, ax = plt.subplots(figsize=(11.5, 6))
    names = {"USA": "US average", "US-IA": "Iowa", "US-CA": "California",
             "US-TX": "Texas", "US-NJ": "New Jersey"}
    for i, (ent, label) in enumerate(names.items()):
        lw = 2.6 if ent == "USA" else 1.6
        ax.plot(wide.index, wide[ent], lw=lw, color=PALETTE[i], label=label)
    for x, label in [(1920, "1920 peak →\n1930s bust"), (1981, "1981 peak →\n'80s farm crisis"),
                     (2013, "corn boom\npeak")]:
        ax.axvline(x, color="#57606a", lw=0.7, ls=":")
        ax.text(x + 1, ax.get_ylim()[1] * 0.02 + 14000, label, fontsize=7.5, color="#57606a")
    ax.set_yscale("log")
    ax.set_title("The acre through 150 years: real farm real estate values",
                 loc="left", fontweight="bold", fontsize=13, pad=24)
    ax.text(0, 1.015,
            f"NASS survey (QuickStats historical), \\$/acre in {df.year.max()} dollars "
            f"(Shiller-CPI deflated), 1871->{df.year.max()}. Log scale.",
            transform=ax.transAxes, fontsize=9, color="#57606a")
    ax.set_ylabel(f"real \\$ per acre ({df.year.max()}\\$, log scale)")
    ax.legend(fontsize=9, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.25)
    fig.text(0.01, -0.01,
             "Source: computed from NASS QuickStats economics bulk + CPI (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_land_value_history")


if __name__ == "__main__":
    fig_land_value_map()
    fig_county_land_value_map()
    fig_county_change_map()
    fig_land_value_history()
