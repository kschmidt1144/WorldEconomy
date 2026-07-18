"""Federal Reserve Distributional Financial Accounts — US wealth distribution.

Household net worth (levels + shares) by wealth percentile group, quarterly
since 1989. Public domain (US government work).
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download
from ..model import month_end

SOURCE = "dfa"
TITLE = "Fed Distributional Financial Accounts"
ZIP_URL = "https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip"
ZIP_NAME = "dfa.zip"
# prefix -> (zip-member regex, unit, unit_type, kind text)
FILES = {
    "nw": (r"networth-levels\.csv$", "US$ (normalized from millions)", "nominal_usd", "net worth level"),
    "nwshare": (r"networth-shares\.csv$", "% of household total", "percent", "share of net worth"),
    # asset composition by wealth group (equities, real estate, pensions…)
    "nwd": (r"networth-levels-detail\.csv$", "US$ (normalized from millions)", "nominal_usd", "component level"),
    # balance-sheet components by INCOME percentile (mortgages, consumer credit…)
    "inc": (r"income-levels-detail\.csv$", "US$ (normalized from millions)", "nominal_usd", "component level by income group"),
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def fetch(force: bool = False) -> None:
    download(SOURCE, ZIP_URL, ZIP_NAME, force=force)


def _read_zip_csv(member_pattern: str) -> pd.DataFrame:
    with zipfile.ZipFile(RAW / SOURCE / ZIP_NAME) as z:
        csvs = [
            m for m in z.namelist()
            if m.lower().endswith(".csv") and re.search(member_pattern, m.lower())
        ]
        if not csvs:
            raise ValueError(
                f"dfa: no csv matching {member_pattern!r} in {ZIP_NAME}; members: {z.namelist()[:20]}"
            )
        with z.open(sorted(csvs, key=len)[0]) as f:
            return pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"))


def parse() -> tuple[list[Series], pd.DataFrame]:
    series_list: list[Series] = []
    frames = []

    for prefix, (member_pattern, unit, unit_type, kindtext) in FILES.items():
        df = _read_zip_csv(member_pattern)
        date_col = df.columns[0]  # "Date"
        cat_col = "Category"
        if cat_col not in df.columns:
            raise ValueError(f"dfa: no Category column in {zname}: {list(df.columns)[:6]}")

        value_cols = [c for c in df.columns if c not in (date_col, cat_col)]
        m = df[date_col].astype(str).str.extract(r"(\d{4}):?Q(\d)")
        df["year"] = m[0].astype(int)
        df["date"] = [month_end(y, q * 3) for y, q in zip(df["year"], m[1].astype(int))]

        long = df.melt(
            id_vars=["year", "date", cat_col],
            value_vars=value_cols,
            var_name="component",
            value_name="value",
        ).dropna(subset=["value"])
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long = long.dropna(subset=["value"])
        if unit_type == "nominal_usd":  # source publishes $ millions -> base units
            is_count = long["component"].map(_slug) == "household_count"  # already a raw count
            long.loc[~is_count, "value"] = long.loc[~is_count, "value"] * 1e6
        long["series_id"] = (
            f"dfa/{prefix}." + long["component"].map(_slug) + "." + long[cat_col].map(_slug)
        )

        for (comp, cat), _ in long.groupby(["component", cat_col]):
            comp_is_count = _slug(comp) == "household_count"
            series_list.append(
                Series(
                    series_id=f"dfa/{prefix}.{_slug(comp)}.{_slug(cat)}",
                    source=SOURCE,
                    name=f"US household {comp} ({kindtext}), {cat}",
                    unit="households" if comp_is_count else unit,
                    unit_type="count" if comp_is_count else unit_type,
                    frequency="Q",
                    description=(
                        f"Distributional Financial Accounts: {comp} for wealth group {cat}. "
                        f"Quarterly since 1989."
                    ),
                    license="Public domain (US government)",
                    url="https://www.federalreserve.gov/releases/z1/dataviz/dfa/",
                )
            )
        frames.append(long[["series_id", "year", "date", "value"]])

    obs = pd.concat(frames, ignore_index=True)
    obs["entity"] = "USA"
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
