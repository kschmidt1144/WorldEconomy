"""FAO Forest Resources Assessment 2020 — who owns the world's forests.

The only truly global land-ownership ledger: forest area by ownership class
(public / private / of-which-individuals / of-which-business / of-which-
indigenous-and-community / unknown) per country, 1990-2015, plus forest and
land area. Bulk CSV via the FRA platform API (the countryIso=WO download in
fact contains every country). Areas published in 1000 ha -> normalized to
hectares. License: CC BY-NC-SA (FAO) — research use.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "fra"
TITLE = "FAO FRA 2020 forest ownership"
URL = ("https://fra-data.fao.org/api/file/bulk-download"
       "?assessmentName=fra&cycleName=2020&countryIso=WO")
ZIP_NAME = "fra_bulk.zip"

COLUMNS = {
    "1a_landArea": ("Land area", "physical"),
    "1a_forestArea": ("Forest area", "physical"),
    "4a_pub_own": ("Forest: public ownership", "physical"),
    "4a_priv_own": ("Forest: private ownership", "physical"),
    "4a_individ": ("Forest: owned by individuals", "physical"),
    "4a_bus_inst_fo": ("Forest: owned by business entities", "physical"),
    "4a_indigenous_fo": ("Forest: owned by Indigenous & community groups", "physical"),
    "4a_fo_unknown": ("Forest: ownership unknown", "physical"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, ZIP_NAME, force=force, headers={"User-Agent": "Mozilla/5.0"})


def parse() -> tuple[list[Series], pd.DataFrame]:
    with zipfile.ZipFile(RAW / SOURCE / ZIP_NAME) as z:
        main = next(m for m in z.namelist() if m.startswith("FRA_Years") and m.endswith(".csv"))
        with z.open(main) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"))

    df = df.dropna(subset=["iso3", "year"])
    df = df[df["iso3"].astype(str).str.len() == 3]

    frames = []
    for col, (name, _ut) in COLUMNS.items():
        if col not in df.columns:
            continue
        sub = df[["iso3", "year", col]].copy()
        sub["value"] = pd.to_numeric(sub[col], errors="coerce") * 1_000  # 1000 ha -> ha
        sub = sub.dropna(subset=["value"])
        sub["series_id"] = f"fra/{col}"
        frames.append(sub.rename(columns={"iso3": "entity"})[["series_id", "entity", "year", "value"]])

    obs = pd.concat(frames, ignore_index=True)
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None

    series_list = [
        Series(
            series_id=f"fra/{col}",
            source=SOURCE,
            name=name,
            unit="hectares (normalized from 1000 ha)",
            unit_type="physical",
            frequency="A",
            description=(
                f"FAO FRA 2020: {name.lower()}, per country, reported for 1990/2000/"
                f"2010/2015 (+2020 area). Private ownership subdivides into individuals, "
                f"business entities, and Indigenous & community groups."
            ),
            license="FAO FRA terms (research use, attribution)",
            url="https://fra-data.fao.org/",
        )
        for col, (name, _ut) in COLUMNS.items()
    ]
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
