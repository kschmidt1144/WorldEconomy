"""Census CPS H-3 — mean household income by quintile + top 5%, 1967->.

The income denominator for distributional ratios (debt/income,
interest/income by bracket). Current-dollar block only; CPS money income
undercounts capital income at the top — noted wherever ratios use it.
Public domain.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "census"
TITLE = "Census H-3 mean household income by quintile"
URL = (
    "https://www2.census.gov/programs-surveys/cps/tables/time-series/"
    "historical-income-households/h03ar.xlsx"
)
FILENAME = "h03ar.xlsx"

GROUPS = {
    1: ("q1", "lowest fifth"), 2: ("q2", "second fifth"), 3: ("q3", "middle fifth"),
    4: ("q4", "fourth fifth"), 5: ("q5", "highest fifth"), 6: ("top5", "top 5 percent"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, headers={"User-Agent": "Mozilla/5.0"})


def parse() -> tuple[list[Series], pd.DataFrame]:
    raw = pd.read_excel(RAW / SOURCE / FILENAME, header=None)

    # current-dollar block: rows after the 'Current Dollars' marker whose first
    # cell starts with a 4-digit year (footnote suffixes like '2013 (39)' occur)
    start = next(
        i for i in range(len(raw))
        if str(raw.iat[i, 0]).strip().lower() == "current dollars"
    )
    rows = []
    for i in range(start + 1, len(raw)):
        cell = str(raw.iat[i, 0]).strip()
        m = re.match(r"^(19|20)\d\d", cell)
        if not m:
            if rows and ("dollar" in cell.lower() or cell.lower().startswith("year")):
                break  # reached the inflation-adjusted block
            continue
        year = int(cell[:4])
        vals = [pd.to_numeric(raw.iat[i, c], errors="coerce") for c in range(1, 7)]
        if any(pd.isna(v) for v in vals):
            continue
        rows.append((year, vals))

    if len(rows) < 40:
        raise ValueError(f"census: only {len(rows)} year rows parsed — layout changed?")

    obs_rows = []
    for year, vals in rows:
        for col, v in zip(range(1, 7), vals):
            slug, _ = GROUPS[col]
            obs_rows.append((f"census/mean_hh_income.{slug}", "USA", year, None, float(v)))
    # duplicate-year survey revisions ('2013 (39)' vs '2013 (38)'): keep first (newest basis)
    obs = pd.DataFrame(
        obs_rows, columns=["series_id", "entity", "year", "date", "value"]
    ).drop_duplicates(subset=["series_id", "year"], keep="first")

    series_list = [
        Series(
            series_id=f"census/mean_hh_income.{slug}",
            source=SOURCE,
            name=f"Mean household income, {label}",
            unit="current US$ per household per year",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                f"CPS ASEC mean household money income, {label}, 1967->. Money income "
                "excludes capital gains and undercounts top capital income."
            ),
            license="Public domain (US Census Bureau)",
            url="https://www.census.gov/data/tables/time-series/demo/income-poverty/historical-income-households.html",
        )
        for slug, label in GROUPS.values()
    ]
    return series_list, obs
