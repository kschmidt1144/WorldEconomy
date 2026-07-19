"""World Bank Commodity Markets "Pink Sheet" — monthly commodity prices since 1960.

The canonical long history of nominal commodity prices (energy, metals,
agriculture) in USD, free and keyless. One xlsx; we keep a marquee basket
across the three groups and store each as a monthly series (entity=WLD).
Real (CPI-deflated) supercycles are computed downstream in ch08.
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download
from ..model import month_end

SOURCE = "pinksheet"
TITLE = "World Bank Pink Sheet (commodity prices)"
URL = ("https://thedocs.worldbank.org/en/doc/"
       "18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx")

# exact column header (stripped) -> (slug, unit, group)
COMMODITIES = {
    "Crude oil, average": ("oil", "$/bbl", "energy"),
    "Coal, Australian": ("coal", "$/mt", "energy"),
    "Natural gas, US": ("natgas_us", "$/mmbtu", "energy"),
    "Gold": ("gold", "$/troy oz", "metals"),
    "Silver": ("silver", "$/troy oz", "metals"),
    "Copper": ("copper", "$/mt", "metals"),
    "Aluminum": ("aluminum", "$/mt", "metals"),
    "Iron ore, cfr spot": ("iron_ore", "$/dmtu", "metals"),
    "Nickel": ("nickel", "$/mt", "metals"),
    "Wheat, US HRW": ("wheat", "$/mt", "agriculture"),
    "Maize": ("maize", "$/mt", "agriculture"),
    "Rice, Thai 5%": ("rice", "$/mt", "agriculture"),
    "Sugar, world": ("sugar", "$/kg", "agriculture"),
    "Coffee, Arabica": ("coffee", "$/kg", "agriculture"),
    "Cotton, A Index": ("cotton", "$/kg", "agriculture"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, "pinksheet.xlsx", force=force)


def parse() -> tuple[list[Series], pd.DataFrame]:
    path = RAW / SOURCE / "pinksheet.xlsx"
    raw = pd.read_excel(path, "Monthly Prices", header=None, engine="openpyxl")
    names = {str(n).strip(): i for i, n in enumerate(raw.iloc[4].tolist()) if str(n) != "nan"}

    series_list, frames = [], []
    for header, (slug, unit, group) in COMMODITIES.items():
        if header not in names:
            continue
        col = names[header]
        sid = f"pinksheet/{slug}"
        series_list.append(
            Series(
                series_id=sid, source=SOURCE, name=f"{header} (nominal price)",
                unit=unit, unit_type="nominal_usd", frequency="M", per_capita=False,
                description=f"World Bank Pink Sheet monthly nominal price: {header} ({group}).",
                license="World Bank (CC BY 4.0)", url="https://www.worldbank.org/commodities",
            )
        )
        rows = []
        for period, val in zip(raw.iloc[6:, 0], raw.iloc[6:, col]):
            ps = str(period)
            if "M" not in ps:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue  # "…" missing markers
            y, m = ps.split("M")
            d = month_end(int(y), int(m))
            rows.append((sid, "WLD", int(y), d, v))
        frames.append(pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]))

    if not frames:
        raise RuntimeError("pinksheet: no commodity columns matched — sheet layout may have changed")
    return series_list, pd.concat(frames, ignore_index=True)
