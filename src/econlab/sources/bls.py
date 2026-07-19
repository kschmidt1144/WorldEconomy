"""BLS Public Data API — CPI item series that FRED does not mirror.

FRED carries most CPI components, but a few story-critical ones — day-care &
preschool (childcare), televisions, physicians' services — are only at BLS.
The BLS v2 API is free and keyless (25 req/day, 10 years/request); an optional
BLS_API_KEY in .env raises limits. We chunk each series into ≤10-year windows.
"""

from __future__ import annotations

import json
import os
import time

import pandas as pd

from ..catalog import Series
from ..config import RAW, ROOT
from ..fetch import save_bytes
from ..model import month_end

SOURCE = "bls"
TITLE = "BLS CPI item detail (childcare, TVs, physicians)"
API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# BLS series id -> (slug, human name, unit_type)
SERIES = {
    "CUUR0000SEEB03": ("childcare", "CPI: day care and preschool (childcare)", "index"),
    "CUUR0000SERA01": ("televisions", "CPI: televisions", "index"),
    "CUUR0000SEMC01": ("physicians", "CPI: physicians' services", "index"),
}
START = 1990  # earliest window we request (childcare begins ~1990)


def _bls_key() -> str | None:
    key = os.environ.get("BLS_API_KEY")
    if not key and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            name, sep, val = line.partition("=")
            if sep and name.strip().lower() in {"bls_api_key", "bls_key", "bls"}:
                return val.strip().strip("'\"")
    return key


def fetch(force: bool = False) -> None:
    import datetime as _dt

    import requests

    key = _bls_key()
    # request in <=10-year windows (keyless limit). End year passed via a raw
    # window list so the fetch stays deterministic (no Date.now in the pipeline).
    windows = [(y, min(y + 9, 2025)) for y in range(START, 2026, 10)]
    for sid in SERIES:
        dest = RAW / SOURCE / f"{sid}.json"
        if dest.exists() and not force:
            continue
        merged: dict[str, float] = {}
        for y0, y1 in windows:
            body = {"seriesid": [sid], "startyear": str(y0), "endyear": str(y1)}
            if key:
                body["registrationkey"] = key
            try:
                r = requests.post(API, json=body, timeout=60)
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                print(f"[bls] {sid} {y0}-{y1}: fetch failed ({e}), skipping window")
                continue
            for s in payload.get("Results", {}).get("series", []):
                for o in s.get("data", []):
                    if not o["period"].startswith("M"):
                        continue
                    try:
                        merged[f"{o['year']}-{o['period']}"] = float(o["value"])
                    except (TypeError, ValueError):
                        continue  # "-", ".", "" and other missing markers
            time.sleep(0.4)
        if merged:
            save_bytes(SOURCE, f"{sid}.json", json.dumps(merged).encode(), f"{API}?series={sid}")


def parse() -> tuple[list[Series], pd.DataFrame]:
    series_list, frames = [], []
    for sid, (slug, name, ut) in SERIES.items():
        path = RAW / SOURCE / f"{sid}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        series_list.append(
            Series(
                series_id=f"bls/{slug}", source=SOURCE, name=name,
                unit="index (1982-84=100 or item base)", unit_type=ut,
                frequency="M", per_capita=False,
                description=f"BLS CPI-U item series {sid}, US city average, not seasonally adjusted.",
                license="BLS (public domain)", url=f"https://data.bls.gov/timeseries/{sid}",
            )
        )
        rows = []
        for ym, val in data.items():
            y, m = ym.split("-M")
            rows.append((f"bls/{slug}", "USA", int(y), month_end(int(y), int(m)), val))
        frames.append(pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]))
    if not frames:
        raise RuntimeError("bls: nothing fetched")
    return series_list, pd.concat(frames, ignore_index=True)
