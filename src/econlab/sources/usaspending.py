"""U.S. Department of Defense prime-contract awards, by recipient — the money the
defense revolving door competes for.

USASpending.gov is the government's own free, keyless record of federal spending.
We query annual DoD prime-contract obligations by recipient, then roll the many
subsidiary line-items up to their parent (Sikorsky -> Lockheed, Electric Boat ->
General Dynamics, Raytheon -> RTX, …) to get true contractor totals. The result
quantifies how concentrated the "prize" is — the contracts that make a retired
general a valuable board member.
"""

from __future__ import annotations

import json

import pandas as pd
import requests

from ..catalog import Series
from ..config import RAW, TIDY

SOURCE = "usaspending"
TITLE = "DoD prime-contract awards by contractor (USASpending)"
API = "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com",
      "Content-Type": "application/json"}
YEARS = list(range(2019, 2025))

# subsidiary/division name -> parent; and whether the parent is a weapons prime.
# Checked most-specific-first so "SIKORSKY" resolves before a bare "LOCKHEED".
PRIME_MAP = [
    ("SIKORSKY", "Lockheed Martin", True), ("LOCKHEED", "Lockheed Martin", True),
    ("RAYTHEON", "RTX", True), ("PRATT", "RTX", True), ("COLLINS AEROSPACE", "RTX", True),
    ("RTX", "RTX", True),
    ("BOEING", "Boeing", True),
    ("ELECTRIC BOAT", "General Dynamics", True), ("BATH IRON WORKS", "General Dynamics", True),
    ("GULFSTREAM", "General Dynamics", True), ("GENERAL DYNAMICS", "General Dynamics", True),
    ("NORTHROP GRUMMAN", "Northrop Grumman", True),
    ("HUNTINGTON INGALLS", "Huntington Ingalls", True),
    ("L3HARRIS", "L3Harris", True), ("L-3", "L3Harris", True), ("HARRIS CORP", "L3Harris", True),
    ("BAE ", "BAE Systems", True), ("BAE,", "BAE Systems", True),
    ("GENERAL ATOMICS", "General Atomics", True), ("OSHKOSH", "Oshkosh", True),
    ("LEIDOS", "Leidos", True), ("BOOZ ALLEN", "Booz Allen", True), ("SAIC", "SAIC", True),
    ("HUMANA", "Humana (TRICARE)", False), ("HEALTH NET", "Health Net (TRICARE)", False),
    ("AMERISOURCE", "AmerisourceBergen (pharma)", False), ("MCKESSON", "McKesson (pharma)", False),
]


def _parent(name: str) -> tuple[str, bool]:
    up = name.upper()
    for needle, parent, prime in PRIME_MAP:
        if needle in up:
            return parent, prime
    return name.title(), False


def _payload(fy: int) -> dict:
    return {
        "filters": {
            "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}],
            "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
            "award_type_codes": ["A", "B", "C", "D"],
        },
        "category": "recipient", "limit": 100,
    }


def fetch(force: bool = False) -> None:
    out = RAW / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    for fy in YEARS:
        dest = out / f"dod_{fy}.json"
        if dest.exists() and not force:
            continue
        r = requests.post(API, headers=UA, data=json.dumps(_payload(fy)), timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)


def parse() -> tuple[list[Series], pd.DataFrame]:
    rows = []
    for fy in YEARS:
        p = RAW / SOURCE / f"dod_{fy}.json"
        if not p.exists():
            continue
        agg: dict[str, list] = {}
        for rec in json.loads(p.read_text()).get("results", []):
            parent, prime = _parent(rec.get("name") or "")
            amt = float(rec.get("amount") or 0)
            if parent not in agg:
                agg[parent] = [0.0, prime]
            agg[parent][0] += amt
        for parent, (amt, prime) in agg.items():
            rows.append({"year": fy, "parent": parent, "amount": amt, "prime": prime})

    df = pd.DataFrame(rows)
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "dod_contractors.parquet", index=False)

    primes = df[df["prime"]]
    top5 = (primes.groupby("year")["amount"].apply(lambda s: s.nlargest(5).sum())).reset_index()
    lmt = df[df["parent"] == "Lockheed Martin"].groupby("year")["amount"].sum().reset_index()
    latest = df[df["year"] == df["year"].max()].sort_values("amount", ascending=False)
    print(f"[usaspending] FY{int(df['year'].max())} top DoD contractor: {latest.iloc[0]['parent']} "
          f"${latest.iloc[0]['amount']/1e9:.0f}B; top-5 weapons primes "
          f"${top5[top5.year==top5.year.max()]['amount'].iloc[0]/1e9:.0f}B combined")

    obs = pd.concat([
        pd.DataFrame({"series_id": "usaspending/dod_top5_primes", "entity": "USA",
                      "year": top5["year"], "value": top5["amount"]}),
        pd.DataFrame({"series_id": "usaspending/dod_lockheed", "entity": "USA",
                      "year": lmt["year"], "value": lmt["amount"]}),
    ], ignore_index=True)

    series_list = [
        Series(series_id="usaspending/dod_top5_primes", source=SOURCE,
               name="DoD contract $ to the top-5 weapons primes (per year)", unit="USD",
               unit_type="nominal_usd", frequency="A",
               description="Combined DoD prime-contract obligations to the 5 largest weapons primes, "
                           "subsidiaries rolled to parent.", license="US government (public domain)",
               url="usaspending.gov"),
        Series(series_id="usaspending/dod_lockheed", source=SOURCE,
               name="DoD contract $ to Lockheed Martin (per year)", unit="USD",
               unit_type="nominal_usd", frequency="A",
               description="DoD prime-contract obligations to Lockheed Martin (incl. Sikorsky).",
               license="US government (public domain)", url="usaspending.gov"),
    ]
    return series_list, obs
