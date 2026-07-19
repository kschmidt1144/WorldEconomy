"""USDA NASS Land Values Summary — farm real estate $/acre by state.

The only official annual per-acre land-value series (surveyed each June,
published August). Parses the fixed-width state table from the release .txt;
entities are US states as US-<postal>. Public domain.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "nass"
TITLE = "USDA NASS farm real estate value per acre"
URL = ("https://esmis.nal.usda.gov/sites/default/release-files/"
       "pn89d6567/2n49w148w/1g05hb655/land0825.txt")
FILENAME = "land0825.txt"
YEARS = [2021, 2022, 2023, 2024, 2025]  # columns of the 2025 summary table

STATES = {  # AK/HI are excluded from the NASS farm-real-estate survey
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "United States": "",  # national average -> entity USA
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, headers={"User-Agent": "Mozilla/5.0"})


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    text = (RAW / SOURCE / FILENAME).read_text(encoding="latin-1")

    # rows look like: "  Iowa .......:  7,420  8,880  9,250  9,420  9,790  3.9"
    # BUT long rows wrap to a continuation line, so slice each row's span from
    # its header to the next header and collect numbers across newlines.
    # The farm-real-estate table comes first; keep the FIRST hit per state
    # (cropland/pasture tables repeat the same row format later).
    # names may carry footnote markers ("Arizona 1/ ...:"); AK/HI are excluded
    # from the survey entirely ("2/ Excludes Alaska and Hawaii")
    starts = list(re.finditer(r"^\s{0,4}([A-Za-z ]+?)(?:\s+\d/)?\s*\.+\s*:", text, re.M))
    seen: dict[str, list[float]] = {}
    for i, m in enumerate(starts):
        name = m.group(1).strip()
        if name not in STATES or name in seen:
            continue
        span_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        tokens = re.findall(r"[\d,]+(?:\.\d+)?", text[m.end():span_end])
        ints = [t for t in tokens if "." not in t]  # drop the percent-change column
        if len(ints) >= 5:
            seen[name] = [float(t.replace(",", "")) for t in ints[:5]]

    if "Iowa" not in seen or "United States" not in seen:
        raise ValueError(f"nass: state table parse failed (got {len(seen)} rows)")

    rows, ents = [], []
    for name, vals in seen.items():
        post = STATES[name]
        entity = "USA" if not post else f"US-{post}"
        if post:
            ents.append((entity, name, "region"))
        for year, v in zip(YEARS, vals):
            rows.append(("nass/farm_realestate_per_acre", entity, year, None, v))

    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
    series_list = [
        Series(
            series_id="nass/farm_realestate_per_acre",
            source=SOURCE,
            name="Farm real estate value per acre",
            unit="US$ per acre (land + buildings)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "USDA NASS Land Values Summary (Aug 2025): average farm real estate "
                "value per acre, by state (US-<postal>) and national (USA), 2021-2025. "
                "Farmland only (~39% of US land); urban land is worth orders of "
                "magnitude more per acre and has no comparable official series."
            ),
            license="Public domain (USDA)",
            url="https://www.nass.usda.gov/Publications/Todays_Reports/reports/land0825.pdf",
        )
    ]
    ent_df = pd.DataFrame(ents, columns=["entity", "name", "kind"])
    return series_list, obs, ent_df
