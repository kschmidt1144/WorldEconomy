"""Bank of England 'A millennium of macroeconomic data' — UK headline series.

Nominal/real GDP, CPI, population, Bank Rate, consol yields — some from
1209. The denominator for any 'how big was X in year Y' question about
Britain, which for the 19th century means about the world's financial
center. License: BoE research dataset, free with attribution.
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "boe"
TITLE = "Bank of England millennium of UK macro data"
URL = ("https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
       "research-datasets/a-millennium-of-macroeconomic-data-for-the-uk.xlsx")
FILENAME = "millennium.xlsx"
SHEET = "A1. Headline series"

# keyword (matched against A1's Description row) -> (slug, name, unit_type, multiplier)
WANTED = [
    ("real uk gdp at market prices", "rgdp", "UK real GDP", "lcu", 1e6),
    ("consumer price index", "cpi", "UK consumer price index", "index", 1.0),
    ("population (gb+ni", "pop", "UK population", "count", 1e3),
    ("bank rate", "bank_rate", "Bank of England policy rate", "percent", 1.0),
    ("consol", "consol_yield", "British consol/long bond yield", "percent", 1.0),
]


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, headers={"User-Agent": "Mozilla/5.0"})


def _row_strs(raw: pd.DataFrame, idx: int) -> list[str]:
    # pandas 3 keeps NaN as float through astype(str) — coerce by hand
    return [x.lower() if isinstance(x, str) else "" for x in raw.iloc[idx]]


def parse() -> tuple[list[Series], pd.DataFrame]:
    raw = pd.read_excel(RAW / SOURCE / FILENAME, sheet_name=SHEET, header=None)
    desc = _row_strs(raw, 3)
    units = [str(x)[:120] for x in raw.iloc[5]]

    picked: dict[str, tuple[int, str, str, str, float]] = {}
    for kw, slug, name, ut, mult in WANTED:
        for col in range(1, raw.shape[1]):
            if kw in desc[col] and slug not in picked:
                picked[slug] = (col, name, units[col], ut, mult)
                break
    if "cpi" not in picked:
        raise ValueError(f"boe: headline columns not found; got {list(picked)}")

    years = pd.to_numeric(raw.iloc[7:, 0], errors="coerce")
    frames, series_list = [], []
    for slug, (col, name, unit, ut, mult) in picked.items():
        vals = pd.to_numeric(raw.iloc[7:, col], errors="coerce") * mult
        sub = pd.DataFrame({"year": years, "value": vals}).dropna()
        sub["series_id"] = f"boe/{slug}"
        frames.append(sub)
        series_list.append(
            Series(
                series_id=f"boe/{slug}",
                source=SOURCE,
                name=name,
                unit=(unit[:80] + (" (scale normalized)" if mult != 1 else "")),
                unit_type=ut,
                frequency="A",
                description=(
                    f"BoE 'A millennium of macroeconomic data' (v3.1), headline sheet: "
                    f"{name}. Column units as published: {unit[:120]}."
                ),
                license="BoE research dataset (free with attribution)",
                url="https://www.bankofengland.co.uk/statistics/research-datasets",
            )
        )

    # nominal UK GDP (market prices, geographically consistent) lives on A9 —
    # the A1 headline nominal column is England-only
    a9 = pd.read_excel(RAW / SOURCE / FILENAME, sheet_name="A9. Nominal GDP (A)", header=None)
    sub_hdr = _row_strs(a9, 4)
    ngdp_col = next(c for c in range(1, 8) if "market prices" in sub_hdr[c])
    y9 = pd.to_numeric(a9.iloc[5:, 0], errors="coerce")
    v9 = pd.to_numeric(a9.iloc[5:, ngdp_col], errors="coerce") * 1e6  # £mn -> £
    ng = pd.DataFrame({"year": y9, "value": v9}).dropna()
    ng["series_id"] = "boe/ngdp"
    frames.append(ng)
    series_list.append(
        Series(
            series_id="boe/ngdp", source=SOURCE,
            name="UK nominal GDP (market prices)",
            unit="£ (normalized from £mn)", unit_type="lcu", frequency="A",
            description=("BoE millennium dataset sheet A9: nominal UK GDP, headline "
                         "market-price measure, geographically consistent, 1688->."),
            license="BoE research dataset (free with attribution)",
            url="https://www.bankofengland.co.uk/statistics/research-datasets",
        )
    )

    obs = pd.concat(frames, ignore_index=True)
    obs["entity"] = "GBR"
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
