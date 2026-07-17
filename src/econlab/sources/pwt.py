"""Penn World Table 11.0 — productivity, capital, labor share, 1950 -> 2023.

Every numeric variable ingested; names from the Legend sheet; magnitudes
normalized to base units (PWT publishes millions). PPP base year is 2021$.
License: CC BY 4.0 (Groningen).
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download_first

SOURCE = "pwt"
TITLE = "Penn World Table 11.0"
FILENAME = "pwt110.xlsx"

URLS = [
    "https://dataverse.nl/api/access/datafile/554105",  # PWT 11.0 Excel (Oct 2025)
]

ID_COLS = {"countrycode", "country", "currency_unit", "year"}

# variables published in millions -> normalize to base units
MILLIONS = {
    "rgdpe", "rgdpo", "cgdpe", "cgdpo", "rgdpna", "rconna", "rdana",
    "rnna", "rkna", "ccon", "cda", "cn", "ck", "pop", "emp",
}

CURATED_UNITS: dict[str, tuple[str, str]] = {
    "rgdpna": ("2021 US$ (PPP), base units", "ppp_usd"),
    "rgdpe": ("2021 US$ (PPP), base units", "ppp_usd"),
    "rgdpo": ("2021 US$ (PPP), base units", "ppp_usd"),
    "pop": ("persons", "count"),
    "emp": ("persons engaged", "count"),
    "avh": ("hours per worker per year", "count"),
    "hc": ("human capital index", "index"),
    "labsh": ("labor share of income (fraction)", "ratio"),
    "rtfpna": ("TFP index (2021=1)", "index"),
    "irr": ("real internal rate of return (fraction)", "ratio"),
    "delta": ("depreciation rate (fraction)", "ratio"),
}


def fetch(force: bool = False) -> None:
    download_first(SOURCE, URLS, FILENAME, force=force)


def parse() -> tuple[list[Series], pd.DataFrame]:
    path = RAW / SOURCE / FILENAME
    df = pd.read_excel(path, sheet_name="Data")
    legend = pd.read_excel(path, sheet_name="Legend", header=None)
    labels = {
        str(r[0]).strip(): str(r[1]).strip()
        for _, r in legend.iterrows()
        if pd.notna(r[0]) and pd.notna(r[1])
    }

    num_cols = [
        c for c in df.columns
        if c not in ID_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]

    series_list = []
    for c in num_cols:
        unit, unit_type = CURATED_UNITS.get(
            c, ("millions (PWT native)" if c in MILLIONS else "", "unknown")
        )
        if c in MILLIONS and c in CURATED_UNITS:
            unit = CURATED_UNITS[c][0]
        series_list.append(
            Series(
                series_id=f"pwt/{c}",
                source=SOURCE,
                name=labels.get(c, c),
                unit=unit,
                unit_type=unit_type,
                frequency="A",
                description=f"PWT 11.0 variable `{c}`: {labels.get(c, '')}".strip()[:2000],
                license="CC BY 4.0",
                url="https://www.rug.nl/ggdc/productivity/pwt/",
            )
        )

    obs = df.melt(
        id_vars=["countrycode", "year"], value_vars=num_cols, var_name="key", value_name="value"
    ).dropna(subset=["value"])
    mult = obs["key"].map(lambda k: 1e6 if k in MILLIONS else 1.0)
    obs["value"] = obs["value"] * mult
    obs["series_id"] = "pwt/" + obs["key"]
    obs = obs.rename(columns={"countrycode": "entity"})
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
