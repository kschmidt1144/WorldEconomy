"""NASS annual survey — farm real estate $/acre by state, 1997 -> present.

The QuickStats 'economics' bulk (date-stamped filename, regenerated daily;
resolved from the datasets listing) filtered to the annual June-survey land
value at state + national level. Extends the 5-year `nass` summary window to
a ~30-year panel. Public domain.
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download, get_text

SOURCE = "agsurvey"
TITLE = "NASS annual survey: state farm real estate values"
LISTING = "https://www.nass.usda.gov/datasets/"
FILENAME = "economics.txt.gz"

ITEM = "AG LAND, INCL BUILDINGS - ASSET VALUE, MEASURED IN $ / ACRE"


def fetch(force: bool = False) -> None:
    dest = RAW / SOURCE / FILENAME
    if dest.exists() and not force:
        return
    html = get_text(LISTING)
    m = re.search(r"qs\.economics_\d+\.txt\.gz", html)
    if not m:
        raise RuntimeError("agsurvey: no qs.economics_* file in datasets listing")
    download(SOURCE, LISTING + m.group(0), FILENAME, force=True,
             headers={"User-Agent": "Mozilla/5.0"})


def parse() -> tuple[list[Series], pd.DataFrame]:
    path = str(RAW / SOURCE / FILENAME)
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT AGG_LEVEL_DESC AS lvl, STATE_ALPHA AS st, YEAR AS year, VALUE AS raw
        FROM read_csv('{path}', delim='\t', header=true, all_varchar=true)
        WHERE SHORT_DESC = '{ITEM}'
          AND AGG_LEVEL_DESC IN ('STATE', 'NATIONAL')
          AND DOMAIN_DESC = 'TOTAL'
          AND REFERENCE_PERIOD_DESC = 'YEAR'
        """
    ).df()
    con.close()
    if df.empty:
        raise ValueError("agsurvey: no rows matched — SHORT_DESC changed?")

    df["value"] = pd.to_numeric(df["raw"].str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=["value"])
    df["entity"] = df.apply(
        lambda r: "USA" if r["lvl"] == "NATIONAL" else f"US-{r['st']}", axis=1
    )
    df["year"] = df["year"].astype(int)

    obs = df[["entity", "year", "value"]].drop_duplicates(subset=["entity", "year"]).copy()
    obs["series_id"] = "agsurvey/farm_realestate_per_acre"
    obs["date"] = None

    series_list = [
        Series(
            series_id="agsurvey/farm_realestate_per_acre",
            source=SOURCE,
            name="Farm real estate value per acre (annual survey)",
            unit="US$ per acre (land + buildings)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "NASS June Area Survey via QuickStats economics bulk: average farm "
                "real estate value per acre, states (US-<postal>) + national (USA), "
                "1997->present. Cross-checks the `nass` summary series."
            ),
            license="Public domain (USDA)",
            url="https://quickstats.nass.usda.gov/",
        )
    ]
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
