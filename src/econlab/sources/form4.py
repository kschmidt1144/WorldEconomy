"""SEC Form 3/4/5 insider filings — the director-interlock network.

Every corporate director files Form 4 when they transact in their company's
stock (and at least annually via equity grants). SEC's quarterly bulk data sets
pair each filing's REPORTINGOWNER (person CIK + relationship) with its
SUBMISSION (issuer + ticker). Filtering to *directors* and deduping to distinct
(person, company) pairs yields the board-seat graph — and the people who sit on
several boards at once are the interlocks Chapter 10 asks about (Mizruchi's
"thinning" thesis, now computable). A person's CIK is stable across issuers, so
it is the join key. Public domain (SEC).
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "form4"
TITLE = "SEC Form 4 insider filings — board-interlock network"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com"}
BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets"


def _recent_quarters(n: int = 5) -> list[str]:
    """The n most recent calendar quarters, newest first (e.g. '2026q1')."""
    y, q = dt.date.today().year, (dt.date.today().month - 1) // 3 + 1
    out = []
    for _ in range(n + 1):  # +1 slack; current quarter's file may not be published yet
        out.append(f"{y}q{q}")
        q -= 1
        if q == 0:
            q, y = 4, y - 1
    return out


def fetch(force: bool = False) -> None:
    got = 0
    for tag in _recent_quarters():
        try:
            download(SOURCE, f"{BASE}/{tag}_form345.zip", f"{tag}.zip", force=force, headers=UA)
            got += 1
        except Exception:
            continue  # not yet published
        if got >= 5:
            break


def _seats_from_zip(path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        sub = pd.read_csv(z.open("SUBMISSION.tsv"), sep="\t", dtype=str,
                          usecols=["ACCESSION_NUMBER", "ISSUERCIK", "ISSUERNAME", "ISSUERTRADINGSYMBOL"])
        own = pd.read_csv(z.open("REPORTINGOWNER.tsv"), sep="\t", dtype=str,
                          usecols=["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP"])
    own = own[own["RPTOWNER_RELATIONSHIP"].str.contains("Director", case=False, na=False)]
    m = own.merge(sub, on="ACCESSION_NUMBER", how="inner")
    m = m[m["ISSUERTRADINGSYMBOL"].notna() & (m["ISSUERTRADINGSYMBOL"].str.strip() != "")]
    return m[["RPTOWNERCIK", "RPTOWNERNAME", "ISSUERCIK", "ISSUERNAME", "ISSUERTRADINGSYMBOL"]]


def parse() -> tuple[list[Series], pd.DataFrame]:
    frames = [_seats_from_zip(p) for p in sorted((RAW / SOURCE).glob("*.zip"))]
    seats = pd.concat(frames, ignore_index=True)
    # one row per (director, company): the board seat
    seats = seats.rename(columns={
        "RPTOWNERCIK": "person_cik", "RPTOWNERNAME": "person", "ISSUERCIK": "issuer_cik",
        "ISSUERNAME": "issuer", "ISSUERTRADINGSYMBOL": "ticker"})
    seats["ticker"] = "$" + seats["ticker"].str.upper().str.strip()
    seats = (seats.sort_values("issuer")
             .drop_duplicates(subset=["person_cik", "issuer_cik"]))

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    seats.to_parquet(out / "board_seats.parquet", index=False)

    n_dir = seats["person_cik"].nunique()
    n_seats = len(seats)
    per = seats.groupby("person_cik").size()
    n_interlock = int((per >= 2).sum())
    print(f"[form4] {n_seats:,} director seats, {n_dir:,} directors, "
          f"{n_interlock:,} on 2+ boards; busiest sits on {per.max()}")

    year = dt.date.today().year
    obs = pd.concat([
        pd.DataFrame({"series_id": "form4/directors", "entity": "USA", "year": year, "value": [float(n_dir)]}),
        pd.DataFrame({"series_id": "form4/director_seats", "entity": "USA", "year": year, "value": [float(n_seats)]}),
    ], ignore_index=True)
    series_list = [
        Series(series_id="form4/directors", source=SOURCE, name="US public-company directors (Form 4, trailing ~year)",
               unit="people", unit_type="count", frequency="A",
               description="Distinct persons filing as a Director on Form 3/4/5 over the recent quarters.",
               license="Public domain (SEC)", url=BASE),
        Series(series_id="form4/director_seats", source=SOURCE, name="Director board-seats (person×company)",
               unit="seats", unit_type="count", frequency="A",
               description="Distinct (director, company) pairs — the board-seat graph behind the interlock network.",
               license="Public domain (SEC)", url=BASE),
    ]
    return series_list, obs
