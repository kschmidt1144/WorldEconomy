"""US Treasury FiscalData — Historical Debt Outstanding, 1790 -> present.

Total gross federal debt at fiscal-year end, annually, from a keyless JSON
API. Public domain. Used to extend long-run debt series to the present.
"""

from __future__ import annotations

import json

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import get_json, save_bytes

SOURCE = "fiscaldata"
TITLE = "Treasury FiscalData historical debt outstanding"
API = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v2/accounting/od/debt_outstanding"
)
FILENAME = "debt_outstanding.json"


def fetch(force: bool = False) -> None:
    dest = RAW / SOURCE / FILENAME
    if dest.exists() and not force:
        return
    records: list[dict] = []
    page = 1
    while True:
        payload = get_json(API, params={"page[size]": 500, "page[number]": page})
        records.extend(payload.get("data", []))
        total_pages = payload.get("meta", {}).get("total-pages", 1)
        if page >= total_pages:
            break
        page += 1
    save_bytes(SOURCE, FILENAME, json.dumps(records, indent=1).encode(), API)


def parse() -> tuple[list[Series], pd.DataFrame]:
    records = json.loads((RAW / SOURCE / FILENAME).read_text())
    df = pd.DataFrame(records)
    df["value"] = pd.to_numeric(df["debt_outstanding_amt"], errors="coerce")
    df["date"] = pd.to_datetime(df["record_date"]).dt.date
    # fiscal year is the meaningful annual key (FY ends Sep 30; Jun 30 pre-1977)
    df["year"] = pd.to_numeric(df["record_fiscal_year"], errors="coerce")
    df = df.dropna(subset=["value", "year"])

    series_list = [
        Series(
            series_id="fiscaldata/debt_outstanding",
            source=SOURCE,
            name="US gross federal debt outstanding (fiscal-year end)",
            unit="nominal US$",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "Total gross federal debt outstanding at fiscal-year end, 1790->present. "
                "Fiscal year ends Sep 30 (Jun 30 before 1977)."
            ),
            license="Public domain (US government)",
            url="https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/",
        )
    ]
    obs = df[["year", "date", "value"]].copy()
    obs["series_id"] = "fiscaldata/debt_outstanding"
    obs["entity"] = "USA"
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
