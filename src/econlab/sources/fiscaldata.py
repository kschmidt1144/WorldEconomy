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
BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
API = BASE + "/v2/accounting/od/debt_outstanding"
AVG_API = BASE + "/v2/accounting/od/avg_interest_rates"
FILENAME = "debt_outstanding.json"
AVG_FILENAME = "avg_interest_rates.json"


def fetch(force: bool = False) -> None:
    dest = RAW / SOURCE / FILENAME
    if force or not dest.exists():
        records: list[dict] = []
        page = 1
        while True:
            payload = get_json(API, params={"page[size]": 500, "page[number]": page})
            records.extend(payload.get("data", []))
            if page >= payload.get("meta", {}).get("total-pages", 1):
                break
            page += 1
        save_bytes(SOURCE, FILENAME, json.dumps(records, indent=1).encode(), API)
    # the government's true funding cost: weighted-avg rate on all interest-bearing debt
    avg_dest = RAW / SOURCE / AVG_FILENAME
    if force or not avg_dest.exists():
        payload = get_json(AVG_API, params={
            "filter": "security_desc:eq:Total Interest-bearing Debt",
            "fields": "record_date,avg_interest_rate_amt", "page[size]": 1000, "sort": "record_date"})
        save_bytes(SOURCE, AVG_FILENAME, json.dumps(payload.get("data", []), indent=1).encode(), AVG_API)


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
    obs = obs[["series_id", "entity", "year", "date", "value"]]

    # effective average interest rate on total interest-bearing debt (annual mean)
    avg = pd.DataFrame(json.loads((RAW / SOURCE / AVG_FILENAME).read_text()))
    avg["rate"] = pd.to_numeric(avg["avg_interest_rate_amt"], errors="coerce")
    avg["year"] = pd.to_datetime(avg["record_date"]).dt.year
    annual = avg.dropna(subset=["rate"]).groupby("year")["rate"].mean().reset_index()
    avg_obs = pd.DataFrame({"series_id": "fiscaldata/avg_interest_rate", "entity": "USA",
                            "year": annual["year"].astype(int), "date": pd.NaT, "value": annual["rate"]})
    series_list.append(Series(
        series_id="fiscaldata/avg_interest_rate", source=SOURCE,
        name="US effective average interest rate on public debt", unit="%", unit_type="percent",
        frequency="A", description="Weighted-average interest rate on total interest-bearing federal "
        "debt (Treasury FiscalData; monthly → annual mean), 2001→present. The government's true funding cost.",
        license="Public domain (US government)",
        url="https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/"))
    return series_list, pd.concat([obs, avg_obs], ignore_index=True)
