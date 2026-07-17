"""IMF DataMapper API — Global Debt Database (keyless JSON).

Public/private debt ratios back to 1950 for 190+ countries. The DataMapper
API is the simple survivor of IMF's 2025 API migration: one GET per indicator.
"""

from __future__ import annotations

import json

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import get_json, save_bytes

SOURCE = "imf"
TITLE = "IMF DataMapper (WEO + Global Debt Database)"
API = "https://www.imf.org/external/datamapper/api/v1/"

# indicator -> (name, unit, unit_type, multiplier, per_capita)
# The WEO bulk .ashx files sit behind Akamai bot protection; DataMapper carries
# the same WEO headline indicators (incl. projections to ~2031) keylessly.
INDICATORS: dict[str, tuple[str, str, str, float, bool]] = {
    # Global Debt Database
    "GG_DEBT_GDP": ("General government debt", "% of GDP", "percent", 1.0, False),
    "CG_DEBT_GDP": ("Central government debt", "% of GDP", "percent", 1.0, False),
    "PVD_LS": ("Private debt (loans and debt securities)", "% of GDP", "percent", 1.0, False),
    "HH_LS": ("Household debt (loans and debt securities)", "% of GDP", "percent", 1.0, False),
    "NFC_LS": ("Nonfinancial corporate debt", "% of GDP", "percent", 1.0, False),
    # WEO headline set (history + IMF projections)
    "NGDP_RPCH": ("Real GDP growth", "% per year", "percent", 1.0, False),
    "NGDPD": ("GDP, current prices", "US$ (normalized from billions)", "nominal_usd", 1e9, False),
    "NGDPDPC": ("GDP per capita, current prices", "US$ per person", "nominal_usd", 1.0, True),
    "PPPGDP": ("GDP, PPP", "int'l $ (normalized from billions)", "ppp_usd", 1e9, False),
    "PPPPC": ("GDP per capita, PPP", "int'l $ per person", "ppp_usd", 1.0, True),
    "PCPIPCH": ("Inflation, average consumer prices", "% per year", "percent", 1.0, False),
    "LUR": ("Unemployment rate", "% of labor force", "percent", 1.0, False),
    "LP": ("Population", "persons (normalized from millions)", "count", 1e6, False),
    "GGXWDG_NGDP": ("General government gross debt (WEO)", "% of GDP", "percent", 1.0, False),
    "GGXCNL_NGDP": ("General government net lending/borrowing", "% of GDP", "percent", 1.0, False),
    "BCA_NGDPD": ("Current account balance", "% of GDP", "percent", 1.0, False),
}


def fetch(force: bool = False) -> None:
    for ind in INDICATORS:
        dest = RAW / SOURCE / f"{ind}.json"
        if dest.exists() and not force:
            continue
        payload = get_json(API + ind)
        if "values" not in payload:
            raise RuntimeError(f"imf: unexpected DataMapper response for {ind}")
        save_bytes(SOURCE, f"{ind}.json", json.dumps(payload).encode(), API + ind)


def parse() -> tuple[list[Series], pd.DataFrame]:
    series_list = []
    frames = []
    for ind, (name, unit, unit_type, mult, per_capita) in INDICATORS.items():
        series_list.append(
            Series(
                series_id=f"imf/{ind}",
                source=SOURCE,
                name=name,
                unit=unit,
                unit_type=unit_type,
                frequency="A",
                per_capita=per_capita,
                description=(
                    f"IMF DataMapper indicator {ind}: {name}. WEO-derived series include "
                    f"IMF projections (through ~2031)."
                ),
                license="IMF DataMapper terms",
                url=f"https://www.imf.org/external/datamapper/{ind}",
            )
        )
        payload = json.loads((RAW / SOURCE / f"{ind}.json").read_text())
        values = payload["values"].get(ind, {})
        rows = [
            (f"imf/{ind}", entity, int(year), None, float(v) * mult)
            for entity, years in values.items()
            for year, v in years.items()
            if v is not None and len(entity) == 3  # countries; skip region groups
        ]
        frames.append(pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]))
    return series_list, pd.concat(frames, ignore_index=True)
