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

# The Land Report 100 (2026 edition, landreport.com/land-report-100, fetched
# 2026-07-18): largest private US landowners. Journalistic estimates — flagged.
# Note the tie at 42 (list has two #42s and no #43).
LANDOWNERS = [
    (1, "Stan Kroenke", 2_700_000), (2, "Emmerson Family", 2_440_000),
    (3, "John Malone", 2_200_000), (4, "Ted Turner", 2_000_000),
    (5, "Reed Family", 1_615_000), (6, "Buck Family", 1_320_000),
    (7, "Irving Family", 1_267_000), (8, "King Ranch Heirs", 911_000),
    (9, "Pingree Heirs", 830_000), (10, "Cullen Heirs", 800_000),
    (11, "Briscoe Family", 738_000), (12, "Wilks Brothers", 652_000),
    (13, "Thomas Peterffy", 647_000), (14, "Stefan Soloviev", 629_000),
    (15, "Brad Kelley", 624_000), (16, "Lykes Heirs", 615_000),
    (17, "Ford Family", 600_000), (18, "Westervelt Heirs", 600_000),
    (19, "Stimson Family", 552_000), (20, "Martin Family", 550_000),
    (21, "Jeff Bezos", 462_000), (22, "Zane & Tanya Kiehne", 455_000),
    (23, "Shannon Kizer", 445_000), (24, "Simplot Family", 443_000),
    (25, "Fisher Family", 440_000), (26, "Kenedy Ranch", 425_000),
    (27, "O'Connor Heirs", 410_000), (28, "Skiles Family", 403_000),
    (29, "Holding Family", 395_000), (30, "Bass Family", 381_000),
    (31, "Robinson & Freed", 373_000), (32, "Collins Family", 370_000),
    (33, "Mike Smith", 351_000), (34, "Malone Mitchell 3rd", 349_000),
    (35, "Killam Family", 341_000), (36, "Barta Family", 340_000),
    (37, "Hughes Family", 319_000), (38, "Horton Family", 302_000),
    (39, "Cogdell Family", 284_000), (40, "Fasken Family", 284_000),
    (41, "Llano Partners", 284_000), (42, "Benjy Griffith III", 279_000),
    (42, "Kokernot Heirs", 278_000), (44, "Bill Gates", 275_000),
    (45, "Babbitt Heirs", 275_000), (46, "Jones Family", 275_000),
    (47, "Lee Family", 275_000), (48, "True Family", 272_000),
    (49, "Taylor Sheridan", 267_000), (50, "Galt Family", 262_000),
    (51, "Hadley Family", 260_000), (52, "Sanders Family", 256_000),
    (53, "Miller Family", 255_000), (54, "Kress Family", 250_000),
    (55, "Coffee Family", 248_840), (56, "Langdale Family", 248_000),
    (57, "Angell Family", 244_000), (58, "Riggs Family", 241_803),
    (59, "Hunt Family", 240_000), (60, "Hearst Family", 238_000),
    (61, "Brask Family", 230_000), (62, "Gene Taylor", 230_000),
    (63, "Fanjul Family", 229_592), (64, "Brophy Family", 228_000),
    (65, "Bidegain Family", 225_000), (66, "Catron Cibola Ranches", 225_000),
    (67, "Sugg Family", 225_000), (68, "Lyda Family", 223_000),
    (69, "Bobby Patton & Mark Walter", 223_000), (70, "Bacon Family", 221_805),
    (71, "Cassidy Heirs", 220_000), (72, "Scott Family", 220_000),
    (73, "Kennedy Family", 219_663), (74, "Gabrych Family", 218_000),
    (75, "Bridwell Heirs", 217_785), (76, "East Foundation", 217_000),
    (77, "Gage Heirs", 213_730), (78, "Russell Gordy", 212_000),
    (79, "Cunningham Sheep Co.", 211_563), (80, "Reese Family", 208_238),
    (81, "Boswell Family", 207_000), (82, "Roger Burch", 203_000),
    (83, "Cocanougher Family", 202_000),
    (84, "Holland M. Ware Charitable Foundation", 200_000),
    (85, "Anthony Family", 200_000), (86, "Philip Anschutz", 198_000),
    (87, "Tianqiao Chen", 198_000), (88, "Stewart & Lynda Resnick", 196_775),
    (89, "Nunley Family", 191_500), (90, "Taylor Family", 191_000),
    (91, "Offutt Family", 190_000), (92, "Scotch Families", 190_000),
    (93, "McLean Heirs", 186_000), (94, "Durrett Family", 182_000),
    (95, "Haynes Family", 180_000), (96, "Williams Family", 177_000),
    (97, "JA Ranch Heirs", 171_000), (98, "Singleton Family", 171_000),
    (99, "Broadbent Family", 170_000), (100, "Irwin Family", 170_000),
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

    # full Land Report 100 -> dedicated warehouse table (rank/name/acres)
    from ..config import TIDY

    lo = pd.DataFrame(LANDOWNERS, columns=["rank", "name", "acres"])
    lo["edition"] = 2026
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    lo.to_parquet(out / "landowners.parquet", index=False)

    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
    return series_list, obs
