"""Energy — country-year panel via OWID's maintained mirror (GitHub, CC BY).

Consolidates Energy Institute Statistical Review + Ember electricity data:
~130 variables (production, consumption, mix, per-capita) 1900->latest.
The EI direct download sits behind a bot wall; OWID republishes it with a
codebook (units + descriptions) that we ingest as catalog metadata.
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "energy"
TITLE = "Energy (OWID mirror of EI Statistical Review + Ember)"
DATA_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"
CODEBOOK_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-codebook.csv"

ID_COLS = {"country", "year", "iso_code", "population", "gdp"}


def fetch(force: bool = False) -> None:
    download(SOURCE, DATA_URL, "owid-energy-data.csv", force=force)
    download(SOURCE, CODEBOOK_URL, "owid-energy-codebook.csv", force=force)


def _unit_type(unit: str, col: str) -> str:
    u = (unit or "").lower()
    if "%" in u:
        return "percent"
    if any(k in u for k in ("terawatt", "kilowatt", "exajoule", "megawatt", "tonne", "cubic", "barrel", "gigawatt")):
        return "physical"
    if "people" in u or "persons" in u:
        return "count"
    if "international-$" in u or "dollar" in u:
        return "ppp_usd" if "2011" in u or "international" in u else "nominal_usd"
    return "unknown"


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = pd.read_csv(RAW / SOURCE / "owid-energy-data.csv")
    codebook = pd.read_csv(RAW / SOURCE / "owid-energy-codebook.csv")
    meta = {
        r["column"]: (str(r.get("description") or ""), str(r.get("unit") or ""))
        for _, r in codebook.iterrows()
    }

    df["entity"] = df["iso_code"]
    df.loc[df["country"] == "World", "entity"] = "WLD"
    df = df.dropna(subset=["entity"])
    df = df[df["entity"].astype(str).str.len() == 3]  # drops OWID_ synthetic regions

    value_cols = [
        c for c in df.columns
        if c not in ID_COLS and c != "entity" and pd.api.types.is_numeric_dtype(df[c])
    ]

    series_list = []
    for c in value_cols:
        desc, unit = meta.get(c, ("", ""))
        series_list.append(
            Series(
                series_id=f"energy/{c}",
                source=SOURCE,
                name=f"Energy: {c.replace('_', ' ')}",
                unit=unit,
                unit_type=_unit_type(unit, c),
                frequency="A",
                per_capita="per_capita" in c,
                description=desc[:2000],
                license="CC BY (OWID; underlying: Energy Institute, Ember)",
                url="https://github.com/owid/energy-data",
            )
        )

    obs = df.melt(
        id_vars=["entity", "year"], value_vars=value_cols, var_name="key", value_name="value"
    ).dropna(subset=["value"])
    obs["series_id"] = "energy/" + obs["key"]
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
