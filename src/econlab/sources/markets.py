"""Daily market closes — indices, FX, gold, oil, bitcoin — via yfinance.

Series ids are provider-agnostic (markets/spx, markets/gold…) so swapping the
provider never renames series. Stooq was the original plan but now sits behind
a JS browser-check wall; Yahoo via yfinance is the workhorse fallback.
Per-ticker failures are tolerated (warn + skip).
"""

from __future__ import annotations

import time

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import _record  # manifest bookkeeping for API-assembled raw files

SOURCE = "markets"
TITLE = "Daily market data (via Yahoo Finance)"

# slug -> (yahoo symbol, display name, unit, unit_type)
INSTRUMENTS: dict[str, tuple[str, str, str, str]] = {
    "spx": ("^GSPC", "S&P 500", "index points", "index"),
    "dji": ("^DJI", "Dow Jones Industrial Average", "index points", "index"),
    "nasdaq": ("^IXIC", "Nasdaq Composite", "index points", "index"),
    "dax": ("^GDAXI", "DAX (Germany)", "index points", "index"),
    "ftse": ("^FTSE", "FTSE 100 (UK)", "index points", "index"),
    "nikkei": ("^N225", "Nikkei 225 (Japan)", "index points", "index"),
    "hangseng": ("^HSI", "Hang Seng (Hong Kong)", "index points", "index"),
    "shanghai": ("000001.SS", "Shanghai Composite (China)", "index points", "index"),
    "eurusd": ("EURUSD=X", "EUR/USD", "USD per EUR", "ratio"),
    "usdjpy": ("JPY=X", "USD/JPY", "JPY per USD", "ratio"),
    "gold": ("GC=F", "Gold (front-month future)", "USD per troy oz", "nominal_usd"),
    "wti": ("CL=F", "WTI crude oil (front-month future)", "USD per barrel", "nominal_usd"),
    "btc": ("BTC-USD", "Bitcoin", "USD per BTC", "nominal_usd"),
    "ust10y": ("^TNX", "US 10-year Treasury yield", "% per year", "percent"),
}


def fetch(force: bool = False) -> None:
    import yfinance as yf

    for slug, (symbol, *_rest) in INSTRUMENTS.items():
        dest = RAW / SOURCE / f"{slug}.parquet"
        if dest.exists() and not force:
            continue
        try:
            hist = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False)
            if hist.empty:
                print(f"[markets] {slug} ({symbol}): empty history, skipping")
                continue
            out = hist[["Close"]].reset_index()
            out.columns = ["date", "close"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            out.to_parquet(dest, index=False)
            _record(SOURCE, f"{slug}.parquet", f"yfinance:{symbol}", "-", dest.stat().st_size)
            time.sleep(0.8)
        except Exception as e:
            print(f"[markets] {slug} ({symbol}): fetch failed ({e}), skipping")


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    series_list, frames, ents = [], [], []
    for slug, (symbol, name, unit, ut) in INSTRUMENTS.items():
        path = RAW / SOURCE / f"{slug}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        dates = pd.to_datetime(df["date"], utc=True)
        entity = slug.upper()
        series_list.append(
            Series(
                series_id=f"markets/{slug}",
                source=SOURCE,
                name=name,
                unit=unit,
                unit_type=ut,
                frequency="D",
                description=f"Daily close for {name} (Yahoo Finance symbol {symbol}).",
                license="Personal research use (Yahoo Finance data)",
                url=f"https://finance.yahoo.com/quote/{symbol}/",
            )
        )
        ents.append((entity, name, "instrument"))
        frames.append(
            pd.DataFrame(
                {
                    "series_id": f"markets/{slug}",
                    "entity": entity,
                    "year": dates.dt.year,
                    "date": dates.dt.date,
                    "value": pd.to_numeric(df["close"], errors="coerce"),
                }
            ).dropna(subset=["value"])
        )
    if not frames:
        raise RuntimeError("markets: no instruments fetched")
    obs = pd.concat(frames, ignore_index=True)
    ent_df = pd.DataFrame(ents, columns=["entity", "name", "kind"])
    return series_list, obs[["series_id", "entity", "year", "date", "value"]], ent_df
