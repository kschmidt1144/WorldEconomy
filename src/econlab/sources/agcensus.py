"""NASS Census of Agriculture 2022 — county-level land value per acre.

The 309MB QuickStats bulk dump (keyless), filtered by DuckDB straight from
the gzip to one item: average value of ag land & buildings, $/acre, per
county (~3,000 counties). Entities are US-<5-digit FIPS>. Public domain.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "agcensus"
TITLE = "NASS Census of Agriculture: county land values"
URL = "https://www.nass.usda.gov/datasets/qs.census2022.txt.gz"
FILENAME = "qs.census2022.txt.gz"

ITEM = "AG LAND, INCL BUILDINGS - ASSET VALUE, MEASURED IN $ / ACRE"


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, headers={"User-Agent": "Mozilla/5.0"})


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    path = str(RAW / SOURCE / FILENAME)
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT STATE_FIPS_CODE AS sf, COUNTY_CODE AS cf,
               COUNTY_NAME AS county, STATE_ALPHA AS st,
               YEAR AS year, VALUE AS raw
        FROM read_csv('{path}', delim='\t', header=true, all_varchar=true)
        WHERE SHORT_DESC = '{ITEM}'
          AND AGG_LEVEL_DESC = 'COUNTY'
          AND DOMAIN_DESC = 'TOTAL'
        """
    ).df()
    con.close()
    if df.empty:
        raise ValueError("agcensus: no county rows matched — SHORT_DESC changed?")

    df["value"] = pd.to_numeric(df["raw"].str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=["value", "sf", "cf"])
    df["entity"] = "US-" + df["sf"].str.zfill(2) + df["cf"].str.zfill(3)
    df["year"] = df["year"].astype(int)

    obs = df[["entity", "year", "value"]].copy()
    obs["series_id"] = "agcensus/agland_value_per_acre"
    obs["date"] = None
    obs = obs.drop_duplicates(subset=["entity", "year"])

    ents = df.drop_duplicates("entity")[["entity", "county", "st"]].copy()
    ents["name"] = ents["county"].str.title() + " County, " + ents["st"]
    ents["kind"] = "region"

    series_list = [
        Series(
            series_id="agcensus/agland_value_per_acre",
            source=SOURCE,
            name="Ag land & buildings, average value per acre (county)",
            unit="US$ per acre",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "Census of Agriculture 2022 (QuickStats bulk): estimated market value "
                "of agricultural land and buildings, $/acre, by county (entity = "
                "US-<5-digit FIPS>). Farm operations only; urban land not covered."
            ),
            license="Public domain (USDA NASS)",
            url="https://www.nass.usda.gov/AgCensus/",
        )
    ]
    return series_list, obs[["series_id", "entity", "year", "date", "value"]], ents[["entity", "name", "kind"]]
