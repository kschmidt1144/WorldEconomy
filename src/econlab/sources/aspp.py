"""State & local public-pension assets — Census Annual Survey of Public Pensions.

The report's chapters on capture (Ch.10/12) describe how officials steer public
money, but the *state-and-local* money surface was told in anecdotes. This is the
biggest single pot on it, computed: the total cash + investments of every state
and local government pension system, by state. Keyless Census bulk file; item code
RZ01 (total cash & investment holdings), weighted to the universe. Public domain.
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "aspp"
TITLE = "Census Annual Survey of Public Pensions (assets)"
YEAR = 2025
URL = (f"https://www2.census.gov/programs-surveys/aspp/datasets/{YEAR}/"
       f"aspp-historical-datasets/ASPP_Unit_File_{YEAR}.csv")
FILENAME = f"ASPP_Unit_File_{YEAR}.csv"

RZ01 = "RZ01"  # total cash and investment holdings (item code)


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, timeout=180)


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = pd.read_csv(
        RAW / SOURCE / FILENAME,
        usecols=["SAMPLE_YEAR", "STATE", "ITEM_CODE", "ITEM_VALUE", "FINAL_WEIGHT"],
        dtype={"STATE": str, "ITEM_CODE": str},
    )
    df = df[df["ITEM_CODE"] == RZ01].copy()
    if df.empty:
        raise ValueError("aspp: no RZ01 (total cash & investments) rows — schema changed?")
    df["ITEM_VALUE"] = pd.to_numeric(df["ITEM_VALUE"], errors="coerce")
    df["FINAL_WEIGHT"] = pd.to_numeric(df["FINAL_WEIGHT"], errors="coerce").fillna(1.0)
    df = df.dropna(subset=["ITEM_VALUE", "STATE"])
    # ITEM_VALUE for RZ01 holdings is already in dollars (state sums reproduce the
    # published $6.49T national total); FINAL_WEIGHT expands the sample to the universe
    df["usd"] = df["ITEM_VALUE"] * df["FINAL_WEIGHT"]

    by_state = df.groupby("STATE", as_index=False)["usd"].sum()
    by_state = by_state[by_state["STATE"].str.fullmatch(r"[A-Z]{2}", na=False)]

    rows = [("aspp/pension_assets", f"US-{s}", YEAR, float(v))
            for s, v in by_state.itertuples(index=False)]
    rows.append(("aspp/pension_assets", "USA", YEAR, float(by_state["usd"].sum())))
    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "value"])

    series_list = [
        Series(
            series_id="aspp/pension_assets",
            source=SOURCE,
            name="State & local public-pension assets (cash + investments)",
            unit="US$ (base units)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "Census Annual Survey of Public Pensions, item RZ01 (total cash & "
                "investment holdings), weighted to the universe and summed by state; "
                "USA = national total (~$6.5T, 2025). The pool of capital whose "
                "investment mandates state & local boards control."
            ),
            license="Public domain (US Census Bureau)",
            url="https://www.census.gov/programs-surveys/aspp.html",
        )
    ]
    return series_list, obs
