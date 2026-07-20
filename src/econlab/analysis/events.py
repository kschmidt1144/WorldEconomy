"""Event-study apparatus — the market impact of historical events.

Generalizes the conference event-studies of Chapter 10 (Jackson Hole, the FOMC)
into a reusable engine: given any event date, measure how the S&P 500 responded —
the drawdown it caused, the volatility it unleashed, how long it took the market
to regain its pre-event high, and the return (up or down) over the following
year. Daily prices reach back to 1927; monthly Shiller data back to 1871 carries
the older events. Run over a curated cross-category catalog (the `events`
warehouse table — war, pandemic, disaster, crash, political, monetary), it turns
"what moves markets, up or down?" into a computation with a century-plus of data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect

WINDOW_3M = 95   # calendar days ~ one quarter
WINDOW_1M = 32
WINDOW_1Y = 365


def _prices() -> tuple[pd.Series, pd.Series]:
    with connect() as con:
        d = con.execute("SELECT date, value FROM obs WHERE series_id='markets/spx' AND date IS NOT NULL ORDER BY date").df()
        m = con.execute("SELECT date, value FROM obs WHERE series_id='shiller/sp_price' AND date IS NOT NULL ORDER BY date").df()
    daily = d.assign(date=pd.to_datetime(d["date"])).set_index("date")["value"]
    monthly = m.assign(date=pd.to_datetime(m["date"])).set_index("date")["value"]
    return daily, monthly


def _vol(daily: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Daily log returns and the 21-day rolling annualized realized volatility (%)."""
    r = np.log(daily / daily.shift(1))
    roll = r.rolling(21).std() * (252 ** 0.5) * 100
    return r, roll


def event_impact(date, daily=None, monthly=None, logret=None, rollvol=None) -> dict | None:
    """Full market response to one event: drawdown, 1m/3m/12m returns, the peak
    realized volatility vs its pre-event baseline, and days to regain the
    pre-event level. Uses daily prices when the event is in range, else monthly."""
    if daily is None:
        daily, monthly = _prices()
    if rollvol is None:
        logret, rollvol = _vol(daily)
    ev = pd.Timestamp(date)
    use_daily = ev >= daily.index[0]
    s = daily if use_daily else monthly
    prior = s.index[s.index < ev]   # base = last close BEFORE the event (captures event-day crashes)
    if len(prior) == 0:
        return None
    base_date = prior[-1]
    base = float(s.loc[base_date])
    if base <= 0:
        return None

    def win(days):
        return s[(s.index > base_date) & (s.index <= base_date + pd.Timedelta(days=days))]

    w3 = win(WINDOW_3M)
    if len(w3) < 2:
        return None
    w1, w12 = win(WINDOW_1M), win(WINDOW_1Y)

    # recovery to the pre-event level, but only after a genuine >=10% drawdown
    # (so a brief bounce mid-crash — e.g. the Sept-2008 short-ban rally — doesn't
    # count Lehman as an instant recovery)
    after = s[s.index > base_date]
    # the >=10% drawdown must strike within ~6 months to be the event's doing —
    # otherwise a much-later, unrelated bear (post-JFK 1966-74) gets mis-attributed
    deep = after[(after.index <= base_date + pd.Timedelta(days=185)) & (after < base * 0.90)]
    if len(deep) == 0:
        recovery_days = 0
    else:
        rec = after[(after.index > deep.index[0]) & (after >= base)]
        recovery_days = int((rec.index[0] - base_date).days) if len(rec) else None  # None = not regained in data

    vol_base = vol_peak = vol_ratio = None
    if use_daily:
        br = logret[(logret.index > base_date - pd.Timedelta(days=63)) & (logret.index <= base_date)]
        if len(br) > 10:
            vol_base = float(br.std() * (252 ** 0.5) * 100)
        rv = rollvol[(rollvol.index > base_date) & (rollvol.index <= base_date + pd.Timedelta(days=WINDOW_3M))]
        if len(rv):
            vol_peak = float(rv.max())
        if vol_base and vol_peak:
            vol_ratio = vol_peak / vol_base

    return {
        "base_date": base_date.date(), "base": base,
        "drawdown_3m": 100 * (float(w3.min()) - base) / base,
        "ret_1m": (100 * (float(w1.iloc[-1]) - base) / base) if len(w1) >= 2 else None,
        "ret_3m": 100 * (float(w3.iloc[-1]) - base) / base,
        "ret_12m": (100 * (float(w12.iloc[-1]) - base) / base) if len(w12) >= 2 else None,
        "recovery_days": recovery_days, "vol_base": vol_base, "vol_peak": vol_peak, "vol_ratio": vol_ratio,
        "resolution": "daily" if use_daily else "monthly",
    }


def event_catalog() -> pd.DataFrame:
    """The curated cross-category event catalog (from the `events` warehouse table)."""
    with connect() as con:
        return con.execute("SELECT date, name, category, note FROM events ORDER BY date").df()


def run_events(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute the full market impact of every catalogued event."""
    if events is None:
        events = event_catalog()
    daily, monthly = _prices()
    logret, rollvol = _vol(daily)
    rows = []
    for e in events.itertuples():
        imp = event_impact(e.date, daily, monthly, logret, rollvol)
        if imp is None:
            continue
        rows.append({"date": pd.Timestamp(e.date).date(), "name": e.name, "category": e.category,
                     "note": getattr(e, "note", ""), **imp})
    return pd.DataFrame(rows)


def impact_by_category(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Median and worst S&P impact by event category — the 'what moves markets' answer."""
    if df is None:
        df = run_events()
    return (df.groupby("category").agg(
        n=("drawdown_3m", "size"), median_dd=("drawdown_3m", "median"),
        worst_dd=("drawdown_3m", "min"), median_ret3=("ret_3m", "median"))
        .reset_index().sort_values("median_dd"))


# ---------- multi-asset: do gold, bonds and oil respond oppositely to stocks? ----------

# label -> (series_id, kind). Daily prices for all four reach back to 2000
# (gold/oil futures) or 1962 (the 10y yield), so the multi-asset study is a
# 21st-century instrument. Bonds are the 10y note: a falling yield is a rising
# price, so we convert the yield move to an approximate total return.
_ASSETS = {
    "Stocks": ("markets/spx", "price"),
    "Bonds": ("fred/DGS10", "yield"),
    "Gold": ("markets/gold", "price"),
    "Oil": ("markets/wti", "price"),
}
_BOND_DURATION = 8.0  # ~modified duration of the 10y note; bond return ≈ -D·Δyield(pp)

# the major cross-regime shocks of the era where all four assets trade daily —
# spanning demand/financial panics (oil collapses) and supply/geopolitical
# shocks (oil spikes), the split that decides whether Treasuries hedge at all.
MULTI_ASSET_EVENTS = [
    ("2000-03-10", "Dot-com peak"),
    ("2001-09-11", "9/11 attacks"),
    ("2003-03-20", "Iraq war begins"),
    ("2007-07-15", "Subprime / quant quake"),
    ("2008-09-15", "Lehman / GFC"),
    ("2010-05-06", "Euro crisis / flash crash"),
    ("2011-02-21", "Libya / Arab Spring"),
    ("2011-08-05", "US debt downgrade"),
    ("2015-08-24", "China devaluation"),
    ("2018-12-01", "2018 Q4 selloff"),
    ("2019-09-16", "Abqaiq oil-field attack"),
    ("2020-02-24", "COVID crash"),
    ("2022-02-24", "Russia invades Ukraine"),
    ("2023-03-10", "SVB / bank runs"),
]


def _asset_series() -> dict[str, pd.Series]:
    """Daily series for each tradable asset (stocks, the 10y yield, gold, oil)."""
    out = {}
    with connect() as con:
        for label, (sid, _) in _ASSETS.items():
            d = con.execute(
                "SELECT date, value FROM obs WHERE series_id=? AND date IS NOT NULL ORDER BY date", [sid]
            ).df()
            out[label] = d.assign(date=pd.to_datetime(d["date"])).set_index("date")["value"]
    return out


def _asset_response(s: pd.Series, date, kind: str, window: int = WINDOW_1M) -> float | None:
    """One asset's response over `window` days from the last close before the event.
    Prices -> % return; the 10y yield -> approximate bond total return (-D·Δyield)."""
    ev = pd.Timestamp(date)
    prior = s.index[s.index < ev]
    if len(prior) == 0:
        return None
    b = float(s.loc[prior[-1]])
    w = s[(s.index > prior[-1]) & (s.index <= prior[-1] + pd.Timedelta(days=window))]
    if len(w) < 2 or b == 0:
        return None
    last = float(w.iloc[-1])
    if kind == "yield":
        return -_BOND_DURATION * (last - b)   # Δyield already in percentage points
    return 100 * (last - b) / b


def multi_asset_impact(date, assets: dict | None = None) -> dict:
    """1-month response of every asset to one event (%; bonds as a price proxy)."""
    if assets is None:
        assets = _asset_series()
    return {label: _asset_response(assets[label], date, kind) for label, (sid, kind) in _ASSETS.items()}


def run_multi_asset(events=MULTI_ASSET_EVENTS) -> pd.DataFrame:
    """Every shock's cross-asset response, classified demand vs supply by oil's sign."""
    assets = _asset_series()
    rows = []
    for dt, nm in events:
        imp = multi_asset_impact(dt, assets)
        if any(v is None for v in imp.values()):
            continue
        imp["regime"] = "Supply (oil ↑)" if imp["Oil"] > 0 else "Demand (oil ↓)"
        rows.append({"date": dt, "name": nm, **imp})
    return pd.DataFrame(rows)


# ---------- widening the event study: global equity contagion & the FX leg ----------

CONTAGION_INDICES = {
    "markets/spx": "S&P 500 (US)", "markets/dji": "Dow (US)", "markets/nasdaq": "Nasdaq (US)",
    "markets/ftse": "FTSE (UK)", "markets/dax": "DAX (Germany)", "markets/nikkei": "Nikkei (Japan)",
    "markets/hangseng": "Hang Seng (HK)", "markets/shanghai": "Shanghai (China)",
}

# sid -> (label, sign) — sign flips so a POSITIVE response = the currency strengthened
# (USD/JPY up = yen weaker, so yen = -USDJPY; EUR/USD up = euro stronger).
HAVEN_FX = {
    "fred/DTWEXBGS": ("US dollar (index)", +1),
    "markets/usdjpy": ("Japanese yen", -1),
    "markets/eurusd": ("euro", +1),
}


def _daily(sid: str) -> pd.Series:
    with connect() as con:
        d = con.execute(
            "SELECT date, value FROM obs WHERE series_id=? AND date IS NOT NULL ORDER BY date", [sid]).df()
    return d.assign(date=pd.to_datetime(d["date"])).set_index("date")["value"]


def _event_drawdown(s: pd.Series, date, window: int = WINDOW_1M) -> float | None:
    """Trough return over `window` days from the last close before the event."""
    ev = pd.Timestamp(date)
    prior = s.index[s.index < ev]
    if len(prior) == 0:
        return None
    b = float(s.loc[prior[-1]])
    w = s[(s.index > prior[-1]) & (s.index <= prior[-1] + pd.Timedelta(days=window))]
    if len(w) < 2 or b <= 0:
        return None
    return 100 * (float(w.min()) - b) / b


def run_global_contagion(events=MULTI_ASSET_EVENTS):
    """Each global index's 1-month drawdown per shock + its correlation with the S&P."""
    series = {sid: _daily(sid) for sid in CONTAGION_INDICES}
    rows = []
    for dt, nm in events:
        row = {"date": dt, "name": nm}
        for sid in CONTAGION_INDICES:
            row[sid] = _event_drawdown(series[sid], dt)
        rows.append(row)
    df = pd.DataFrame(rows)
    corr = {sid: float(df["markets/spx"].corr(df[sid])) for sid in CONTAGION_INDICES if sid != "markets/spx"}
    means = {sid: float(df[sid].mean()) for sid in CONTAGION_INDICES}
    return df, corr, means


def run_currency_havens(events=MULTI_ASSET_EVENTS) -> pd.DataFrame:
    """1-month FX response per shock (oriented so + = the currency strengthened), by regime."""
    fx = {sid: _daily(sid) for sid in HAVEN_FX}
    regime = {r.date: r.regime for r in run_multi_asset(events).itertuples()}
    rows = []
    for dt, nm in events:
        row = {"date": dt, "name": nm, "regime": regime.get(dt)}
        for sid, (lab, sgn) in HAVEN_FX.items():
            r = _asset_response(fx[sid], dt, "price")
            row[sid] = sgn * r if r is not None else None
        rows.append(row)
    return pd.DataFrame(rows)
