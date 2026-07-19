"""Curated US & world land-ownership facts — small, fully cited, versioned.

Unlike bulk sources these few dozen numbers live in official PDFs (CRS,
USDA-AFIDA, national cadastres), so we curate them here with per-series
citations — the same policy as MapMaker's curated packs: few numbers, named
sources, no invention. The raw layer gets a JSON copy for provenance.
"""

from __future__ import annotations

import json

import pandas as pd

from ..catalog import Series
from ..fetch import save_bytes

SOURCE = "usland"
TITLE = "Curated land-ownership facts (CRS / USDA / national cadastres)"

# (series_key, entity, year, value, unit, unit_type, name, citation)
FACTS = [
    # --- US total: 2.27B acres. Federal estate by agency (million acres) ---
    ("federal_acres_blm", "USA", 2018, 244.4e6, "acres", "physical",
     "US federal land: Bureau of Land Management",
     "CRS R42346 'Federal Land Ownership: Overview and Data' (Feb 2020), FY2018 data"),
    ("federal_acres_usfs", "USA", 2018, 192.9e6, "acres", "physical",
     "US federal land: Forest Service", "CRS R42346 (Feb 2020)"),
    ("federal_acres_fws", "USA", 2018, 89.2e6, "acres", "physical",
     "US federal land: Fish & Wildlife Service", "CRS R42346 (Feb 2020)"),
    ("federal_acres_nps", "USA", 2018, 79.9e6, "acres", "physical",
     "US federal land: National Park Service", "CRS R42346 (Feb 2020)"),
    ("federal_acres_dod", "USA", 2018, 8.8e6, "acres", "physical",
     "US federal land: Department of Defense", "CRS R42346 (Feb 2020)"),
    ("federal_acres_total", "USA", 2018, 640e6, "acres", "physical",
     "US federal land: total (all agencies)",
     "CRS R42346 (Feb 2020): ~640M acres of 2.27B, ~28% of US land"),
    # --- ownership shares of total US land ---
    ("share_federal", "USA", 2018, 28.0, "% of US land", "percent",
     "US land share: federal", "CRS R42346 (Feb 2020)"),
    ("share_state_local", "USA", 2015, 8.6, "% of US land", "percent",
     "US land share: state & local government",
     "USDA ERS Major Land Uses / Wildlife Society summaries (~195M acres)"),
    ("share_tribal", "USA", 2020, 2.5, "% of US land", "percent",
     "US land share: tribal trust",
     "BIA: ~56M acres held in trust (Bureau of Indian Affairs)"),
    ("share_private", "USA", 2018, 60.9, "% of US land", "percent",
     "US land share: private (residual)",
     "Residual of CRS/USDA/BIA shares; ~1.38B acres"),
    # --- what private land IS (USDA ERS Major Land Uses, 2017) ---
    ("acres_cropland", "USA", 2017, 392e6, "acres", "physical",
     "US cropland (all ownership)", "USDA ERS Major Land Uses 2017"),
    ("acres_grassland_pasture", "USA", 2017, 654e6, "acres", "physical",
     "US grassland pasture & range", "USDA ERS Major Land Uses 2017"),
    ("acres_forest_use", "USA", 2017, 623e6, "acres", "physical",
     "US forest-use land", "USDA ERS Major Land Uses 2017"),
    ("acres_urban", "USA", 2017, 70e6, "acres", "physical",
     "US urban land", "USDA ERS Major Land Uses 2017 (~3% of US land)"),
    # --- foreign ownership of US agricultural land (USDA AFIDA 2023) ---
    ("foreign_ag_acres", "USA", 2023, 45.9e6, "acres", "physical",
     "US agricultural land held by foreign persons",
     "USDA AFIDA 2023 annual report: 45.9M acres ~= 3.6% of private ag land; largest: Canada (~1/3)"),
    ("foreign_ag_share", "USA", 2023, 3.6, "% of private ag land", "percent",
     "Foreign share of US private agricultural land", "USDA AFIDA 2023"),
    # --- national public-land shares, selected countries ---
    ("share_public", "CAN", 2020, 89.0, "% of land", "percent",
     "Canada: Crown land share (41% federal + 48% provincial)",
     "Natural Resources Canada"),
    ("share_public", "CHN", 2020, 100.0, "% of land", "percent",
     "China: all land state- (urban) or collective- (rural) owned; private parties hold use rights only",
     "PRC Constitution Art. 10; Land Administration Law"),
    ("share_public", "RUS", 2020, 92.2, "% of land", "percent",
     "Russia: state & municipal land share", "Rosreestr land fund reports"),
    ("share_public", "AUS", 2020, 71.0, "% of land", "percent",
     "Australia: Crown land incl. pastoral leasehold (freehold ~29%)",
     "Geoscience Australia / state land registries (leasehold counted as Crown)"),
]

# The Land Report 100: largest private US landowners (journalistic estimates)
LANDOWNERS = [
    (1, "Emmerson family (Sierra Pacific)", 2.41e6, "timber"),
    (2, "Reed family (Green Diamond)", 2.1e6, "timber"),
    (3, "Ted Turner", 2.0e6, "ranches"),
    (4, "Stan Kroenke", 1.7e6, "ranches"),
    (5, "Irving family", 1.25e6, "timber (Maine)"),
]


def fetch(force: bool = False) -> None:
    payload = {"facts": FACTS, "landowners": LANDOWNERS}
    save_bytes(SOURCE, "curated.json", json.dumps(payload, indent=1).encode(),
               "curated: see per-series citations")


def parse() -> tuple[list[Series], pd.DataFrame]:
    rows, series_list, seen = [], [], set()
    for key, entity, year, value, unit, ut, name, citation in FACTS:
        sid = f"usland/{key}"
        rows.append((sid, entity, year, None, float(value)))
        if sid not in seen:
            seen.add(sid)
            series_list.append(
                Series(
                    series_id=sid, source=SOURCE, name=name, unit=unit,
                    unit_type=ut, frequency="A",
                    description=f"Curated fact. Source: {citation}.",
                    license="Public documents; curated with citation",
                    url="https://crsreports.congress.gov/product/pdf/R/R42346",
                )
            )

    # top private landowners as obs too (entity = rank slug, kind 'other')
    for rank, name, acres, kind in LANDOWNERS:
        sid = "usland/top_private_owner_acres"
        rows.append((sid, f"LANDOWNER_{rank}", 2024, None, float(acres)))
    series_list.append(
        Series(
            series_id="usland/top_private_owner_acres", source=SOURCE,
            name="Largest private US landowners (acres)",
            unit="acres", unit_type="physical", frequency="A",
            description=("Land Report 100 (2024) estimates; entities LANDOWNER_1.. = "
                         + "; ".join(f"#{r} {n} ({k})" for r, n, _, k in LANDOWNERS)),
            license="Land Report estimates (journalistic) — flagged",
            url="https://landreport.com/",
        )
    )
    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
    return series_list, obs
