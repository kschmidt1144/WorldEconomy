"""NY Fed US-dollar liquidity swap operations — who drew, and how much.

FRED's SWPT gives the *aggregate* dollars the Fed had lent to foreign central
banks. The New York Fed's markets API gives the operation-level detail — which
central bank, how much, at what rate, for how long — for the daily-operations
era (2019→, which captures the whole March-2020 COVID dollar crunch). We store
the operations and compute, in the analysis layer, each central bank's *peak
dollars outstanding*: the size of the line each ally actually pulled on when the
world ran out of dollars. Public domain (Federal Reserve Bank of New York).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "nyfedswaps"
TITLE = "NY Fed USD liquidity swap operations (per central bank)"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com"}
API = "https://markets.newyorkfed.org/api/fxs/all/search.json"


def fetch(force: bool = False) -> None:
    url = f"{API}?startDate=2019-01-01&endDate={dt.date.today().isoformat()}"
    download(SOURCE, url, "operations.json", force=force, headers=UA)


def parse() -> tuple[list[Series], pd.DataFrame]:
    ops = json.loads((RAW / SOURCE / "operations.json").read_text())["fxSwaps"]["operations"]
    df = pd.DataFrame(ops)
    df = df[df["operationType"].str.contains("Liquidity Swap", na=False)].copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    for c in ("tradeDate", "settlementDate", "maturityDate"):
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    swaps = df[["counterparty", "currency", "tradeDate", "settlementDate", "maturityDate",
                "termInDays", "amount", "interestRate"]].dropna(subset=["amount", "settlementDate", "maturityDate"])

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    swaps.to_parquet(out / "swap_ops.parquet", index=False)
    print(f"[nyfedswaps] {len(swaps):,} swap operations, {swaps['counterparty'].nunique()} central banks, "
          f"{swaps['settlementDate'].min()}–{swaps['maturityDate'].max()}")

    # obs: total notional lent per year (context; the real analysis is peak-outstanding per CB)
    swaps["year"] = pd.to_datetime(swaps["settlementDate"]).dt.year
    by_year = swaps.groupby("year")["amount"].sum().reset_index()
    obs = pd.DataFrame({"series_id": "nyfedswaps/notional_lent", "entity": "USA",
                        "year": by_year["year"], "value": by_year["amount"].astype(float)})
    series_list = [Series(
        series_id="nyfedswaps/notional_lent", source=SOURCE,
        name="USD liquidity-swap notional lent to foreign central banks (per year)",
        unit="US$", unit_type="nominal_usd", frequency="A",
        description="Sum of USD liquidity-swap operation amounts (rolls counted), NY Fed markets API. "
        "Per-central-bank peak-outstanding is computed in analysis from the swap_ops table.",
        license="Public domain (FRBNY)", url="https://markets.newyorkfed.org/static/docs/markets-api.html")]
    return series_list, obs
