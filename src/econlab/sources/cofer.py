"""IMF COFER — Currency Composition of Official Foreign Exchange Reserves.

The canonical record of which currencies the world's central banks hold their
reserves in — the hard numbers behind "dollar dominance". Reached via the IMF's
new SDMX 2.1 REST API (`api.imf.org`), the survivor of the 2025 API migration;
the old `dataservices.imf.org` SDMX-JSON endpoint is dead.

One GET returns the whole COFER dataset (~140 series as StructureSpecific XML);
we keep the AFXRA (allocated reserves by currency) SHRO_PT (share-of-allocated,
%) annual series per currency. USD/JPY/GBP/CHF reach back to 1995, EUR to 1999,
CNY to 2016 — entity is WLD (COFER country code G001, the world aggregate).
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "cofer"
TITLE = "IMF COFER (reserve currency composition)"
URL = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,COFER/"

# FXR_CURRENCY code -> (short code, display name)
CURRENCIES = {
    "CI_USD": ("USD", "US dollar"),
    "CI_EUR": ("EUR", "Euro"),
    "CI_JPY": ("JPY", "Japanese yen"),
    "CI_GBP": ("GBP", "Pound sterling"),
    "CI_CNY": ("CNY", "Chinese renminbi"),
    "CI_CHF": ("CHF", "Swiss franc"),
    "CI_CAD": ("CAD", "Canadian dollar"),
    "CI_AUD": ("AUD", "Australian dollar"),
    "CI_OTHC": ("OTH", "Other currencies"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, "cofer.xml", force=force,
             headers={"Accept": "application/vnd.sdmx.structurespecificdata+xml;version=2.1"})


def parse() -> tuple[list[Series], pd.DataFrame]:
    xml = (RAW / SOURCE / "cofer.xml").read_text()
    blocks = re.findall(r"<(?:\w+:)?Series ([^>]+)>(.*?)</(?:\w+:)?Series>", xml, re.S)

    series_list, rows = [], []
    for code, (short, disp) in CURRENCIES.items():
        sid = f"cofer/reserve_share.{short}"
        series_list.append(
            Series(
                series_id=sid, source=SOURCE,
                name=f"Reserve share: {disp}",
                unit="% of allocated FX reserves", unit_type="percent",
                frequency="A", per_capita=False,
                description=(
                    f"Share of world allocated official FX reserves held in {disp} "
                    f"(IMF COFER, AFXRA/SHRO_PT annual; COUNTRY=G001 world aggregate)."
                ),
                license="IMF COFER terms",
                url="https://data.imf.org/COFER",
            )
        )
        by_year: dict[int, float] = {}
        for attrs_s, body in blocks:
            a = dict(re.findall(r'(\w+)="([^"]*)"', attrs_s))
            if (a.get("INDICATOR") == "AFXRA" and a.get("FXR_CURRENCY") == code
                    and a.get("TYPE_OF_TRANSFORMATION") == "SHRO_PT"
                    and a.get("FREQUENCY") == "A"):
                for yr, val in re.findall(r'TIME_PERIOD="(\d{4})" OBS_VALUE="([^"]+)"', body):
                    by_year[int(yr)] = float(val)  # dedup vintages: last wins
        for yr, val in by_year.items():
            rows.append((sid, "WLD", yr, None, val))

    if not rows:
        raise RuntimeError("cofer: parsed 0 rows — SDMX schema may have changed")
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
