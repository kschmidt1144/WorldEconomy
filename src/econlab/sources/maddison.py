"""Maddison Project Database 2023 — GDP per capita + population, 1 CE -> 2022.

The deep-history backbone: ~230 entities incl. historical states (Former USSR,
Czechoslovakia, Yugoslavia). gdppc in 2011 international (PPP) dollars; pop in
thousands (we store persons). License: CC BY 4.0 (Groningen Growth and
Development Centre).
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..fetch import download_first

SOURCE = "maddison"
TITLE = "Maddison Project Database 2023"

URLS = [
    # 2023 release now lives on DataverseNL (linked from the RUG release page)
    "https://dataverse.nl/api/access/datafile/421302",
    "https://www.rug.nl/ggdc/historicaldevelopment/maddison/data/mpd2023_web.xlsx",
]
FILENAME = "mpd2023_web.xlsx"


def fetch(force: bool = False) -> None:
    download_first(SOURCE, URLS, FILENAME, force=force)


def parse() -> tuple[list[Series], pd.DataFrame]:
    from ..config import RAW

    df = pd.read_excel(RAW / SOURCE / FILENAME, sheet_name="Full data")
    df = df.rename(columns=str.lower)
    required = {"countrycode", "year", "gdppc", "pop"}
    if not required.issubset(df.columns):
        raise ValueError(f"maddison: unexpected columns {list(df.columns)}")

    base = "https://www.rug.nl/ggdc/historicaldevelopment/maddison/"
    series_list = [
        Series(
            series_id="maddison/gdppc",
            source=SOURCE,
            name="Real GDP per capita",
            unit="2011 int'l $ (PPP) per person",
            unit_type="ppp_usd",
            frequency="A",
            per_capita=True,
            description="Maddison Project Database 2023. Benchmark years before 1820, mostly annual after.",
            license="CC BY 4.0",
            url=base,
        ),
        Series(
            series_id="maddison/pop",
            source=SOURCE,
            name="Population",
            unit="persons",
            unit_type="count",
            frequency="A",
            description="Maddison Project Database 2023 population (stored as persons; source file is thousands).",
            license="CC BY 4.0",
            url=base,
        ),
    ]

    gdppc = df[["countrycode", "year", "gdppc"]].dropna().rename(
        columns={"countrycode": "entity", "gdppc": "value"}
    )
    gdppc["series_id"] = "maddison/gdppc"

    pop = df[["countrycode", "year", "pop"]].dropna().rename(
        columns={"countrycode": "entity", "pop": "value"}
    )
    pop["value"] = pop["value"] * 1_000.0  # thousands -> persons
    pop["series_id"] = "maddison/pop"

    obs = pd.concat([gdppc, pop], ignore_index=True)
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
