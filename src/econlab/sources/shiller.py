"""Robert Shiller's long-run US dataset — monthly since 1871.

S&P composite price/dividends/earnings, CPI, 10-yr Treasury yield, CAPE.
Hosting has moved over the years (Yale -> shillerdata.com), so we resolve the
current ie_data.xls link with fallbacks. License: freely provided for research.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download, download_first, get_text
from ..model import month_end

SOURCE = "shiller"
TITLE = "Shiller US stock market & CPI data (1871->)"
FILENAME = "ie_data.xls"

DIRECT_URLS = [
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
    "https://www.econ.yale.edu/~shiller/data/ie_data.xls",
]
LANDING = "https://shillerdata.com/"


def fetch(force: bool = False) -> None:
    # shillerdata.com carries the actively-updated file; the Yale mirror froze in 2023
    try:
        html = get_text(LANDING)
        m = re.search(r'href="((?:https:)?//[^"]*ie_data\.xls[^"]*)"', html)
        if m:
            url = m.group(1).replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url
            download(SOURCE, url, FILENAME, force=force)
            return
    except Exception:
        pass
    download_first(SOURCE, DIRECT_URLS, FILENAME, force=force)


def _find_cape_col(raw: pd.DataFrame, data_start: int) -> int | None:
    for r in range(max(0, data_start - 10), data_start):
        for c in range(raw.shape[1]):
            cell = str(raw.iat[r, c])
            if "CAPE" in cell or "P/E10" in cell:
                return c
    return None


def parse() -> tuple[list[Series], pd.DataFrame]:
    raw = pd.read_excel(RAW / SOURCE / FILENAME, sheet_name="Data", header=None)

    # data starts at the first row whose col0 parses as a fractional-year ~1871.01
    data_start = None
    for i in range(min(30, len(raw))):
        try:
            v = float(raw.iat[i, 0])
        except (TypeError, ValueError):
            continue
        if 1800 < v < 1900:
            data_start = i
            break
    if data_start is None:
        raise ValueError("shiller: could not locate data start row")

    cape_col = _find_cape_col(raw, data_start)

    rows = []
    for i in range(data_start, len(raw)):
        try:
            frac = float(raw.iat[i, 0])
        except (TypeError, ValueError):
            break  # footer notes
        if not (1800 < frac < 2200):
            break
        year = int(frac)
        month = round((frac - year) * 100)
        if not 1 <= month <= 12:
            continue
        d = month_end(year, month)

        def num(col: int | None):
            if col is None:
                return None
            try:
                v = float(raw.iat[i, col])
                return v if v == v else None  # NaN check
            except (TypeError, ValueError):
                return None

        rows.append(
            {
                "year": year,
                "date": d,
                "sp_price": num(1),
                "sp_div": num(2),
                "sp_earn": num(3),
                "cpi": num(4),
                "gs10": num(6),
                "cape": num(cape_col),
            }
        )
    wide = pd.DataFrame(rows)
    if wide.empty or wide["cpi"].isna().all():
        raise ValueError("shiller: parse produced no CPI data — layout changed?")

    meta = {
        "sp_price": ("S&P Composite price index", "index points (nominal)", "index"),
        "sp_div": ("S&P Composite dividends per share (annualized)", "nominal US$", "nominal_usd"),
        "sp_earn": ("S&P Composite earnings per share (annualized)", "nominal US$", "nominal_usd"),
        "cpi": ("US Consumer Price Index", "index (1982-84=100)", "index"),
        "gs10": ("US 10-year Treasury constant-maturity yield", "% per year", "percent"),
        "cape": ("Cyclically adjusted P/E ratio (CAPE)", "ratio", "ratio"),
    }
    series_list = [
        Series(
            series_id=f"shiller/{k}",
            source=SOURCE,
            name=name,
            unit=unit,
            unit_type=ut,
            frequency="M",
            description=f"{name}, monthly since 1871. From Robert Shiller's ie_data.xls.",
            license="Free for research use (Shiller)",
            url="https://shillerdata.com/",
        )
        for k, (name, unit, ut) in meta.items()
    ]

    obs = wide.melt(
        id_vars=["year", "date"], value_vars=list(meta), var_name="key", value_name="value"
    ).dropna(subset=["value"])
    obs["series_id"] = "shiller/" + obs["key"]
    obs["entity"] = "USA"
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
