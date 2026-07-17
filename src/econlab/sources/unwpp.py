"""UN World Population Prospects 2024 — demographic indicators, 1950 -> 2100.

Medium-variant annual panel (history through ~2023, projections after): total
population, fertility, life expectancy, median age, births/deaths, migration.
Countries via ISO3_code; the World aggregate is kept as WLD. Counts are
published in thousands -> normalized to persons. License: CC BY 3.0 IGO.
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "unwpp"
TITLE = "UN World Population Prospects 2024"
URL = (
    "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/"
    "CSV_FILES/WPP2024_Demographic_Indicators_Medium.csv.gz"
)
FILENAME = "WPP2024_Demographic_Indicators_Medium.csv.gz"

ID_COLS = {
    "SortOrder", "LocID", "Notes", "ISO3_code", "ISO2_code", "SDMX_code",
    "LocTypeID", "LocTypeName", "ParentID", "Location", "VarID", "Variant", "Time",
}

# thousands -> persons
THOUSANDS_PREFIXES = (
    "TPopulation", "PopDensity_SKIP",  # PopDensity is per km2, not thousands
)
THOUSANDS_COLS = {
    "TPopulation1Jan", "TPopulation1July", "TPopulationMale1July", "TPopulationFemale1July",
    "NatChange", "Births", "Births1519", "Deaths", "DeathsMale", "DeathsFemale",
    "NetMigrations", "InfantDeaths", "Under5Deaths", "LBsurvivingAge1",
}

CURATED_UNITS: dict[str, tuple[str, str]] = {
    "TPopulation1July": ("persons (mid-year)", "count"),
    "PopDensity": ("persons per km2", "ratio"),
    "MedianAgePop": ("years", "count"),
    "TFR": ("live births per woman", "ratio"),
    "LEx": ("life expectancy at birth, years", "count"),
    "IMR": ("infant deaths per 1,000 live births", "ratio"),
    "CBR": ("births per 1,000 population", "ratio"),
    "CDR": ("deaths per 1,000 population", "ratio"),
    "Births": ("persons", "count"),
    "Deaths": ("persons", "count"),
    "NetMigrations": ("persons", "count"),
    "PopGrowthRate": ("% per year", "percent"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force)


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = pd.read_csv(RAW / SOURCE / FILENAME, compression="gzip", low_memory=False)

    # countries + World only (skip the region/SDG soup for now)
    df["entity"] = df["ISO3_code"]
    df.loc[df["LocID"] == 900, "entity"] = "WLD"
    df = df.dropna(subset=["entity"])

    num_cols = [
        c for c in df.columns
        if c not in ID_COLS and c != "entity" and pd.api.types.is_numeric_dtype(df[c])
    ]

    series_list = []
    for c in num_cols:
        unit, unit_type = CURATED_UNITS.get(c, ("", "unknown"))
        if c in THOUSANDS_COLS and c not in CURATED_UNITS:
            unit, unit_type = ("persons", "count")
        series_list.append(
            Series(
                series_id=f"unwpp/{c}",
                source=SOURCE,
                name=f"WPP: {c}",
                unit=unit,
                unit_type=unit_type,
                frequency="A",
                description=(
                    f"UN WPP 2024 medium variant `{c}`. History through ~2023, "
                    f"projection to 2100 after."
                ),
                license="CC BY 3.0 IGO",
                url="https://population.un.org/wpp/",
            )
        )

    obs = df.melt(
        id_vars=["entity", "Time"], value_vars=num_cols, var_name="key", value_name="value"
    ).dropna(subset=["value"])
    mult = obs["key"].map(lambda k: 1e3 if k in THOUSANDS_COLS else 1.0)
    obs["value"] = obs["value"] * mult
    obs["series_id"] = "unwpp/" + obs["key"]
    obs = obs.rename(columns={"Time": "year"})
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
