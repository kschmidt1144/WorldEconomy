"""Series catalog: every series in the warehouse has a registered identity.

unit_type is load-bearing: transforms refuse to mix incompatible unit types
(nominal vs real vs PPP confusion is the #1 failure mode in this domain).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

UNIT_TYPES = {
    "nominal_usd",  # current US$
    "real_usd",     # constant US$ (base year in `unit` text)
    "ppp_usd",      # international/PPP $ (base year in `unit` text)
    "lcu",          # local currency units
    "index",        # index numbers (base in `unit` text)
    "percent",      # rates, shares expressed 0-100
    "ratio",        # dimensionless ratios (e.g. CAPE, debt/gdp expressed 0-1)
    "count",        # people, firms, units
    "physical",     # physical quantities (EJ, TWh, tonnes, barrels/day…)
    "unknown",      # not yet classified (bulk sources); transforms warn
}

FREQUENCIES = {"A", "Q", "M", "W", "D"}


@dataclass
class Series:
    series_id: str   # namespaced: "maddison/gdppc", "wdi/NY.GDP.MKTP.CD"
    source: str
    name: str
    unit: str        # human text: "2011 int'l $ per person"
    unit_type: str
    frequency: str
    per_capita: bool = False
    description: str = ""
    license: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        if self.unit_type not in UNIT_TYPES:
            raise ValueError(f"{self.series_id}: bad unit_type {self.unit_type!r}")
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"{self.series_id}: bad frequency {self.frequency!r}")
        if "/" not in self.series_id:
            raise ValueError(f"series_id must be namespaced: {self.series_id!r}")


def catalog_df(series_list: list[Series]) -> pd.DataFrame:
    df = pd.DataFrame([asdict(s) for s in series_list])
    if df["series_id"].duplicated().any():
        dupes = df.loc[df["series_id"].duplicated(), "series_id"].tolist()
        raise ValueError(f"duplicate series_ids: {dupes[:5]}")
    return df
