"""Forbes real-time billionaires list — a snapshot of extreme private wealth.

Unofficial JSON endpoint (the one behind forbes.com's own list page), fetched
with a browser UA. The full person table lands in warehouse table
`billionaires`; obs carries global aggregates only. Flagged unofficial:
levels are Forbes estimates; treat ranks and orders of magnitude as the data.
"""

from __future__ import annotations

import datetime as _dt
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "billionaires"
TITLE = "Forbes real-time billionaires (snapshot)"
URL = (
    "https://www.forbes.com/forbesapi/person/rtb/0/position/true.json"
    "?fields=rank,personName,finalWorth,countryOfCitizenship,source,industries"
)
FILENAME = "forbes_rtb.json"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, headers={"User-Agent": BROWSER_UA})


def parse() -> tuple[list[Series], pd.DataFrame]:
    payload = json.loads((RAW / SOURCE / FILENAME).read_text())
    people = payload.get("personList", {}).get("personsLists", [])
    if not people:
        raise RuntimeError("billionaires: unexpected Forbes payload shape")

    df = pd.DataFrame(
        {
            "rank": [p.get("rank") for p in people],
            "name": [p.get("personName") for p in people],
            "worth_usd": [
                (p.get("finalWorth") or 0) * 1e6 for p in people  # finalWorth is $M
            ],
            "country": [p.get("countryOfCitizenship") for p in people],
            "source": [p.get("source") for p in people],
        }
    ).dropna(subset=["name"])
    df = df[df["worth_usd"] > 0].sort_values("rank")
    snap_date = _dt.date.today()
    df["snapshot_date"] = snap_date

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out / "people.parquet")

    year = snap_date.year
    aggs = {
        "billionaires/count": float(len(df)),
        "billionaires/total_worth": float(df["worth_usd"].sum()),
        "billionaires/top10_worth": float(df.nsmallest(10, "rank")["worth_usd"].sum()),
        "billionaires/top100_worth": float(df.nsmallest(100, "rank")["worth_usd"].sum()),
    }
    series_list = [
        Series(
            series_id=sid,
            source=SOURCE,
            name={
                "billionaires/count": "Number of billionaires (Forbes list)",
                "billionaires/total_worth": "Combined billionaire wealth",
                "billionaires/top10_worth": "Combined wealth, top 10 individuals",
                "billionaires/top100_worth": "Combined wealth, top 100 individuals",
            }[sid],
            unit="persons" if sid.endswith("count") else "US$",
            unit_type="count" if sid.endswith("count") else "nominal_usd",
            frequency="A",
            description=(
                "Snapshot aggregate from the Forbes real-time billionaires list "
                f"({snap_date}). Unofficial estimates; full table in warehouse "
                "table `billionaires`."
            ),
            license="Forbes estimates (unofficial endpoint) — research use, flagged",
            url="https://www.forbes.com/real-time-billionaires/",
        )
        for sid in aggs
    ]
    obs = pd.DataFrame(
        [(sid, "WLD", year, snap_date, v) for sid, v in aggs.items()],
        columns=["series_id", "entity", "year", "date", "value"],
    )
    return series_list, obs
