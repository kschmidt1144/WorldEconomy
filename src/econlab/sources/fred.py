"""FRED — curated headline US/global financial & macro series.

Needs a free API key: https://fred.stlouisfed.org/docs/api/api_key.html
Read from env FRED_API_KEY or the file .secrets/fred.key (gitignored).
Series metadata (title, units, frequency) is pulled from the API itself.
License: FRED terms; underlying series carry their own licenses.
"""

from __future__ import annotations

import json
import os
import time

import pandas as pd

from ..catalog import Series
from ..config import RAW, ROOT
from ..fetch import get_json, save_bytes

SOURCE = "fred"
TITLE = "FRED (St. Louis Fed)"
API = "https://api.stlouisfed.org/fred"

SERIES_IDS = [
    # activity & labor
    "GDPC1", "GDP", "INDPRO", "PAYEMS", "UNRATE", "CIVPART", "EMRATIO", "AHETPI",
    "RSAFS", "HOUST", "PCE", "PSAVERT",
    # prices
    "CPIAUCSL", "PCEPILFE", "T5YIE", "T10YIE",
    # rates & curve
    "FEDFUNDS", "DGS2", "DGS10", "DGS30", "T10Y2Y", "DFII10", "MORTGAGE30US", "SOFR",
    # money & Fed
    "M2SL", "WALCL", "RRPONTSYD",
    # credit & risk
    "BAMLH0A0HYM2", "BAMLC0A0CM", "NFCI", "DRTSCILM", "TOTALSL",
    # fiscal & external
    "GFDEGDQ188S", "FYFSD", "BOPGSTB", "DTWEXBGS",
    # corporate
    "CP", "VIXCLS",
]

UNIT_TYPE_HINTS = [
    ("percent", "percent"),
    ("index", "index"),
    ("billions of dollars", "nominal_usd"),
    ("millions of dollars", "nominal_usd"),
    ("billions of chained", "real_usd"),
    ("thousands of persons", "count"),
    ("thousands of units", "count"),
    ("number", "count"),
    ("dollars", "nominal_usd"),
    ("ratio", "ratio"),
]

SCALE_HINTS = [("billions", 1e9), ("millions", 1e6), ("thousands", 1e3)]


NAME_ALIASES = {"fred_api_key", "fred_api", "fred_key", "fred"}


def _api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        keyfile = ROOT / ".secrets" / "fred.key"
        if keyfile.exists():
            key = keyfile.read_text().strip()
    if not key:
        envfile = ROOT / ".env"  # accepts `FRED_API_KEY=…`, `fred_api = …`, etc.
        if envfile.exists():
            for line in envfile.read_text().splitlines():
                name, sep, val = line.partition("=")
                if sep and name.strip().lower() in NAME_ALIASES:
                    key = val.strip().strip("'\"")
                    break
    if not key:
        raise RuntimeError(
            "FRED API key not found. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html then put it in "
            ".env (FRED_API_KEY=...), .secrets/fred.key, or export FRED_API_KEY"
        )
    return key


def fetch(force: bool = False) -> None:
    key = _api_key()
    for sid in SERIES_IDS:
        dest = RAW / SOURCE / f"{sid}.json"
        if dest.exists() and not force:
            continue
        meta = get_json(f"{API}/series", params={"series_id": sid, "api_key": key, "file_type": "json"})
        obs = get_json(
            f"{API}/series/observations",
            params={"series_id": sid, "api_key": key, "file_type": "json", "limit": 100000},
        )
        payload = {"meta": meta["seriess"][0], "observations": obs["observations"]}
        # never persist the key
        save_bytes(SOURCE, f"{sid}.json", json.dumps(payload).encode(), f"{API}/series/observations?series_id={sid}")
        time.sleep(0.25)


def _classify(units: str) -> tuple[str, float]:
    u = units.lower()
    ut = "unknown"
    for hint, t in UNIT_TYPE_HINTS:
        if hint in u:
            ut = t
            break
    mult = 1.0
    if ut in ("nominal_usd", "real_usd", "count"):
        for hint, m in SCALE_HINTS:
            if hint in u:
                mult = m
                break
    return ut, mult


def parse() -> tuple[list[Series], pd.DataFrame]:
    series_list = []
    frames = []
    for sid in SERIES_IDS:
        path = RAW / SOURCE / f"{sid}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        meta = payload["meta"]
        units = meta.get("units", "")
        ut, mult = _classify(units)
        freq = {"D": "D", "W": "W", "M": "M", "Q": "Q", "A": "A"}.get(
            meta.get("frequency_short", "M"), "M"
        )
        norm_note = " (scale normalized)" if mult != 1.0 else ""
        series_list.append(
            Series(
                series_id=f"fred/{sid}",
                source=SOURCE,
                name=meta.get("title", sid),
                unit=units + norm_note,
                unit_type=ut,
                frequency=freq,
                description=(meta.get("notes") or "")[:2000],
                license="FRED terms of use",
                url=f"https://fred.stlouisfed.org/series/{sid}",
            )
        )
        rows = [
            (f"fred/{sid}", "USA", int(o["date"][:4]), pd.Timestamp(o["date"]).date(),
             float(o["value"]) * mult)
            for o in payload["observations"]
            if o["value"] not in (".", "", None)
        ]
        frames.append(pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]))

    if not frames:
        raise RuntimeError("fred: nothing fetched (missing key?)")
    return series_list, pd.concat(frames, ignore_index=True)
