"""US foreign aid — ForeignAssistance.gov (Foreign Military Financing).

The report's aid-reach map (Ch.2 F8) is built from WDI net ODA — *development*
aid only. It concedes it misses **military financing**: the weapons money that
is most of what Israel and Egypt actually receive. This connector supplies that
missing channel from the official ForeignAssistance.gov flat files.

We ingest the pre-aggregated `us_foreign_aid_funding.csv` (funding account ×
country × year; ~22MB), keep the **Foreign Military Financing Program** account,
and emit disbursements (the actuals) and obligations per recipient-year in base
USD. The full transaction-level file is 3.7GB and deliberately avoided. Public
domain (US Government).
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "faid"
TITLE = "US foreign aid (ForeignAssistance.gov) — military financing"
URL = "https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_funding.csv"
FILENAME = "us_foreign_aid_funding.csv"

FMF_ACCOUNT = "Foreign Military Financing Program"

# Country Code values in this file that are regional/global aggregates, not real
# recipients — kept out of the obs (the figure sums countries only). ForeignAssistance
# uses 3-letter *region* codes (EES = Europe & Eurasia, AFR = Africa, ...) that collide
# with the ISO3 pattern; list them explicitly. WBG (West Bank/Gaza) is a real recipient.
_AGG_CODES = {"", "WLD", "EES", "AFR", "EAP", "EUR", "MEA", "MENA", "SCA",
              "WHA", "OES", "GLO", "SSA", "NEA", "SAS", "ECA", "LAC"}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, timeout=600)


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = pd.read_csv(
        RAW / SOURCE / FILENAME,
        usecols=["Funding Account Name", "Country Code", "Country Name",
                 "Transaction Type Name", "Fiscal Year", "current_amount"],
        dtype=str,
    )
    df = df[df["Funding Account Name"] == FMF_ACCOUNT].copy()
    if df.empty:
        raise ValueError("faid: no Foreign Military Financing rows — file schema changed?")

    df["year"] = pd.to_numeric(df["Fiscal Year"], errors="coerce")
    df["value"] = pd.to_numeric(df["current_amount"], errors="coerce")
    df = df.dropna(subset=["year", "value"])
    df["year"] = df["year"].astype(int)
    df = df[(df["year"] >= 1999) & (df["year"] <= 2025)]
    # aggregate rows carry a non-ISO3 code; drop them from the country panel
    df = df[~df["Country Code"].isin(_AGG_CODES)]
    df = df[df["Country Code"].str.fullmatch(r"[A-Z]{3}", na=False)]

    txn = {"Disbursements": "fmf_disbursed", "Obligations": "fmf_obligated"}
    rows = []
    for tname, sid in txn.items():
        sub = (df[df["Transaction Type Name"] == tname]
               .groupby(["Country Code", "year"], as_index=False)["value"].sum())
        for cc, yr, val in sub.itertuples(index=False):
            if val != 0:
                rows.append((f"faid/{sid}", cc, int(yr), float(val)))

    if not rows:
        raise ValueError("faid: no FMF disbursement/obligation rows parsed")

    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "value"])

    series_list = [
        Series(
            series_id="faid/fmf_disbursed",
            source=SOURCE,
            name="Foreign Military Financing — disbursements (US grants for arms)",
            unit="US$ (base units)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "US Foreign Military Financing Program disbursements by recipient "
                "and fiscal year (ForeignAssistance.gov funding file). FMF is grant "
                "money that buys US weapons — the security channel the ODA aid map "
                "excludes. Israel and Egypt dominate by treaty (Camp David, 1979)."
            ),
            license="Public domain (US Government)",
            url="https://foreignassistance.gov",
        ),
        Series(
            series_id="faid/fmf_obligated",
            source=SOURCE,
            name="Foreign Military Financing — obligations",
            unit="US$ (base units)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "US Foreign Military Financing obligations by recipient and fiscal "
                "year; obligations lead disbursements (e.g. Ukraine/Taiwan booked "
                "before the money moves)."
            ),
            license="Public domain (US Government)",
            url="https://foreignassistance.gov",
        ),
    ]
    return series_list, obs[["series_id", "entity", "year", "value"]]
