"""World Bank — World Development Indicators, full bulk archive.

~1,400 annual indicators x ~265 entities, 1960->present. Keyless bulk zip.
We keep EVERYTHING (the point of this project is breadth) and unpivot the
wide CSV with DuckDB rather than pandas — ~11M observations.
License: CC BY-4.0.
"""

from __future__ import annotations

import zipfile

import duckdb
import pandas as pd
import pyarrow as pa

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "wdi"
TITLE = "World Bank World Development Indicators"
URL = "https://databank.worldbank.org/data/download/WDI_CSV.zip"

# main data file was renamed WDIData.csv -> WDICSV.csv in recent archives
DATA_NAMES = ("WDICSV.csv", "WDIData.csv")
WANTED = DATA_NAMES + ("WDISeries.csv", "WDICountry.csv")


def _extracted() -> dict[str, str]:
    """name(lower) -> path for already-extracted files we care about."""
    out = {}
    for p in (RAW / SOURCE).glob("*.csv"):
        out[p.name.lower()] = str(p)
    return out


def fetch(force: bool = False) -> None:
    zpath = download(SOURCE, URL, "WDI_CSV.zip", force=force)
    have = _extracted()
    need = [n for n in WANTED if n.lower() not in have]
    if force or any(n.lower() not in have for n in ("WDISeries.csv", "WDICountry.csv")) or not any(
        n.lower() in have for n in DATA_NAMES
    ):
        with zipfile.ZipFile(zpath) as z:
            members = {m.filename.lower(): m.filename for m in z.infolist()}
            for want in WANTED:
                if want.lower() in members:
                    z.extract(members[want.lower()], RAW / SOURCE)
    del need


def _data_path() -> str:
    have = _extracted()
    for n in DATA_NAMES:
        if n.lower() in have:
            return have[n.lower()]
    raise FileNotFoundError("WDI data csv not found; run fetch first")


def _unit_type(code: str, name: str) -> str:
    c = code.upper()
    n = name.lower()
    if ".ZG" in c or c.endswith(".ZS") or "(% " in n or "(%)" in n or n.endswith("(%") or "(% of" in n:
        return "percent"
    if ".PP.CD" in c or ".PP.KD" in c or "ppp" in n:
        return "ppp_usd"
    if c.endswith(".CD"):
        return "nominal_usd"
    if c.endswith(".KD"):
        return "real_usd"
    if c.endswith(".CN") or c.endswith(".KN"):
        return "lcu"
    if c.endswith(".IN") and ("number" in n or "population" in n):
        return "count"
    if n.startswith("population") and "%" not in n:
        return "count"
    return "unknown"


def parse() -> tuple[list[Series], pa.Table]:
    data_csv = _data_path()
    con = duckdb.connect()

    # -- observations: unpivot year columns (all_varchar guards messy cells)
    obs = con.execute(
        f"""
        WITH wide AS (
            SELECT * FROM read_csv('{data_csv}', header=true, all_varchar=true)
        ),
        long AS (
            UNPIVOT wide
            ON COLUMNS(* EXCLUDE ("Country Name", "Country Code", "Indicator Name", "Indicator Code"))
            INTO NAME year VALUE raw_value
        )
        SELECT
            'wdi/' || "Indicator Code" AS series_id,
            "Country Code"             AS entity,
            CAST(year AS INTEGER)      AS year,
            CAST(NULL AS DATE)         AS date,
            TRY_CAST(raw_value AS DOUBLE) AS value
        FROM long
        WHERE TRY_CAST(raw_value AS DOUBLE) IS NOT NULL
          AND TRY_CAST(year AS INTEGER) IS NOT NULL
        """
    ).fetch_arrow_table()

    # -- catalog: from the data file's own distinct indicators (guarantees parity),
    #    enriched from WDISeries.csv where available
    indicators = con.execute(
        f"""
        SELECT DISTINCT "Indicator Code" AS code, "Indicator Name" AS name
        FROM read_csv('{data_csv}', header=true, all_varchar=true)
        """
    ).df()
    con.close()

    meta: dict[str, dict] = {}
    series_csv = _extracted().get("wdiseries.csv")
    if series_csv:
        sdf = pd.read_csv(series_csv, dtype=str).fillna("")
        code_col = "Series Code" if "Series Code" in sdf.columns else "﻿Series Code"
        for _, r in sdf.iterrows():
            meta[r[code_col]] = {
                "description": r.get("Long definition", "") or r.get("Short definition", ""),
                "unit": r.get("Unit of measure", ""),
                "license": r.get("License Type", "") or "CC BY-4.0",
            }

    series_list = []
    for _, r in indicators.iterrows():
        code, name = r["code"], r["name"]
        m = meta.get(code, {})
        series_list.append(
            Series(
                series_id=f"wdi/{code}",
                source=SOURCE,
                name=name,
                unit=m.get("unit", ""),
                unit_type=_unit_type(code, name),
                frequency="A",
                per_capita=".PC" in code.upper() or "per capita" in name.lower(),
                description=(m.get("description", "") or "")[:2000],
                license=m.get("license", "CC BY-4.0"),
                url="https://datatopics.worldbank.org/world-development-indicators/",
            )
        )
    return series_list, obs
