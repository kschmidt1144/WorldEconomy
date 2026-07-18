"""SEC EDGAR companyfacts — fundamentals for every US-listed filer.

The ~1.3GB bulk zip holds one XBRL-facts JSON per company. We keep only
*frame-tagged* entries (CY2023, CY2023Q1, CY2023Q1I) — the SEC's own
deduplicated calendar assignments — for a curated set of us-gaap/dei tags,
split into annual and quarterly series per company. Entity = "$" + primary
ticker ("$AAPL") — the $ prefix keeps tickers out of the ISO3 country
namespace (ticker SUN is Sunoco; entity SUN is the former USSR).
Public domain.
"""

from __future__ import annotations

import json
import re
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "edgar"
TITLE = "SEC EDGAR company fundamentals (XBRL frames)"
ZIP_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# us-gaap tag -> series key (first match wins where several tags map to one key)
GAAP_TAGS: dict[str, str] = {
    "Revenues": "revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenues",
    "NetIncomeLoss": "net_income",
    "OperatingIncomeLoss": "operating_income",
    "Assets": "assets",
    "Liabilities": "liabilities",
    "StockholdersEquity": "equity",
    "CashAndCashEquivalentsAtCarryingValue": "cash",
    "LongTermDebt": "debt_lt",
    "LongTermDebtNoncurrent": "debt_lt",  # fallback tag, per-frame priority
}

KEY_NAMES = {
    "revenues": "Revenues",
    "net_income": "Net income",
    "operating_income": "Operating income",
    "assets": "Total assets",
    "liabilities": "Total liabilities",
    "equity": "Stockholders' equity",
    "cash": "Cash & equivalents",
    "debt_lt": "Long-term debt",
    "shares": "Common shares outstanding",
}

FRAME_RE = re.compile(r"^CY(\d{4})(?:Q([1-4]))?I?$")


def fetch(force: bool = False) -> None:
    download(SOURCE, ZIP_URL, "companyfacts.zip", force=force)
    download(SOURCE, TICKERS_URL, "company_tickers.json", force=force)


def _ticker_map() -> dict[int, tuple[str, str]]:
    """cik -> (ticker, title); first listing wins (primary class)."""
    data = json.loads((RAW / SOURCE / "company_tickers.json").read_text())
    out: dict[int, tuple[str, str]] = {}
    for row in data.values():
        cik = int(row["cik_str"])
        if cik not in out:
            out[cik] = (str(row["ticker"]).upper(), row.get("title", ""))
    return out


def _collect(
    facts: dict, tag_block: dict, unit_key: str, rows: list, entity: str, key: str, prio: int = 0
) -> None:
    for unit, entries in tag_block.get("units", {}).items():
        if unit != unit_key:
            continue
        for e in entries:
            frame = e.get("frame")
            if not frame:
                continue
            m = FRAME_RE.match(frame)
            if not m:
                continue
            year, quarter = int(m.group(1)), m.group(2)
            val = e.get("val")
            if val is None:
                continue
            end = e.get("end")
            rows.append((entity, key, year, quarter, end, float(val), prio))


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    tickers = _ticker_map()
    rows: list[tuple] = []
    ents: dict[str, str] = {}

    with zipfile.ZipFile(RAW / SOURCE / "companyfacts.zip") as z:
        members = [m for m in z.namelist() if m.startswith("CIK") and m.endswith(".json")]
        for i, member in enumerate(members):
            if i % 4000 == 0:
                print(f"[edgar] {i}/{len(members)} companies…")
            try:
                cik = int(member[3:13])
            except ValueError:
                continue
            tk = tickers.get(cik)
            if tk is None:
                continue  # funds/trusts without a listed ticker — skip for now
            ticker, title = tk
            entity = f"${ticker}"  # $-prefix: keep tickers out of the ISO3 namespace
            try:
                with z.open(member) as f:
                    doc = json.load(f)
            except Exception:
                continue
            facts = doc.get("facts", {})
            gaap = facts.get("us-gaap", {})

            # collect ALL revenue tags; dedupe later per frame with tag priority
            # (a company can report old years under Revenues and new years under
            # the ASC-606 tag — Apple does — so the choice is per-frame)
            for prio, (tag, key) in enumerate(GAAP_TAGS.items()):
                if tag in gaap:
                    _collect(facts, gaap[tag], "USD", rows, entity, key, prio)
            dei = facts.get("dei", {})
            if "EntityCommonStockSharesOutstanding" in dei:
                _collect(
                    facts, dei["EntityCommonStockSharesOutstanding"], "shares", rows, entity, "shares"
                )
            if rows and (entity not in ents):
                ents[entity] = title

    import datetime as _dt

    df = (
        pd.DataFrame(rows, columns=["entity", "key", "cy", "quarter", "end", "value", "prio"])
        .sort_values("prio", kind="stable")
        .drop_duplicates(subset=["entity", "key", "cy", "quarter"], keep="first")
    )
    df = df[df["cy"] <= _dt.date.today().year + 1]  # drop filer-error future fiscal years

    annual = df[df["quarter"].isna()].copy()
    quarterly = df[df["quarter"].notna()].copy()
    annual["series_id"] = "edgar/" + annual["key"]
    quarterly["series_id"] = "edgar/" + quarterly["key"] + "_q"

    out_frames = []
    for sub in (annual, quarterly):
        o = pd.DataFrame(
            {
                "series_id": sub["series_id"],
                "entity": sub["entity"],
                "year": sub["cy"].astype(int),
                "date": pd.to_datetime(sub["end"], errors="coerce").dt.date,
                "value": sub["value"],
            }
        )
        out_frames.append(o)
    obs = pd.concat(out_frames, ignore_index=True)

    series_list = []
    for key, name in KEY_NAMES.items():
        unit, ut = ("shares", "count") if key == "shares" else ("US$", "nominal_usd")
        for suffix, freq, label in (("", "A", "annual"), ("_q", "Q", "quarterly")):
            sid = f"edgar/{key}{suffix}"
            if sid not in set(obs["series_id"]):
                continue
            series_list.append(
                Series(
                    series_id=sid,
                    source=SOURCE,
                    name=f"{name} ({label}, per company)",
                    unit=unit,
                    unit_type=ut,
                    frequency=freq,
                    description=(
                        f"{name} per company from SEC XBRL frame-tagged facts "
                        f"({label} calendar frames). Entity = primary ticker."
                    ),
                    license="Public domain (SEC)",
                    url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
                )
            )

    ent_df = pd.DataFrame(
        [(e, n, "company") for e, n in ents.items()], columns=["entity", "name", "kind"]
    )
    return series_list, obs, ent_df
