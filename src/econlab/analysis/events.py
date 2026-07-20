"""Event-study apparatus — the market impact of historical events.

Generalizes the conference event-studies of Chapter 10 (Jackson Hole, the FOMC)
into a reusable engine: given any event date, measure how the S&P 500 responded
in the weeks after — the drawdown it caused and the return over the next quarter.
Daily prices reach back to 1927; monthly Shiller data back to 1871 carries the
older events. Run over a curated cross-category catalog (the `events` warehouse
table — war, pandemic, disaster, crash, political, monetary), it turns "what kind
of event actually moves markets?" into a computation with real data going back a
century.
"""

from __future__ import annotations

import pandas as pd

from ..model import connect

WINDOW_3M = 95   # calendar days ~ one quarter
WINDOW_1M = 32


def _prices() -> tuple[pd.Series, pd.Series]:
    with connect() as con:
        d = con.execute("SELECT date, value FROM obs WHERE series_id='markets/spx' AND date IS NOT NULL ORDER BY date").df()
        m = con.execute("SELECT date, value FROM obs WHERE series_id='shiller/sp_price' AND date IS NOT NULL ORDER BY date").df()
    daily = d.assign(date=pd.to_datetime(d["date"])).set_index("date")["value"]
    monthly = m.assign(date=pd.to_datetime(m["date"])).set_index("date")["value"]
    return daily, monthly


def event_impact(date, daily: pd.Series | None = None, monthly: pd.Series | None = None) -> dict | None:
    """S&P response to one event: base level, 3-month max drawdown, 1- and 3-month
    returns. Uses daily prices when the event is in their range, else monthly."""
    if daily is None:
        daily, monthly = _prices()
    ev = pd.Timestamp(date)
    use_daily = ev >= daily.index[0]
    s = daily if use_daily else monthly
    # base = the last close STRICTLY BEFORE the event, so an event-day crash
    # (e.g. Black Monday) is captured in the window, not hidden in the base
    prior = s.index[s.index < ev]
    if len(prior) == 0:
        return None
    base_date = prior[-1]
    base = float(s.loc[base_date])
    if base <= 0:
        return None

    def window(days):
        return s[(s.index > base_date) & (s.index <= base_date + pd.Timedelta(days=days))]

    w3 = window(WINDOW_3M)
    if len(w3) < 2:
        return None
    trough = float(w3.min())
    w1 = window(WINDOW_1M)
    return {
        "base_date": base_date.date(), "base": base,
        "drawdown_3m": 100 * (trough - base) / base,
        "ret_1m": (100 * (float(w1.iloc[-1]) - base) / base) if len(w1) >= 2 else None,
        "ret_3m": 100 * (float(w3.iloc[-1]) - base) / base,
        "resolution": "daily" if use_daily else "monthly",
    }


def event_catalog() -> pd.DataFrame:
    """The curated cross-category event catalog (from the `events` warehouse table)."""
    with connect() as con:
        return con.execute("SELECT date, name, category, note FROM events ORDER BY date").df()


def run_events(events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute the market impact of every catalogued event."""
    if events is None:
        events = event_catalog()
    daily, monthly = _prices()
    rows = []
    for e in events.itertuples():
        imp = event_impact(e.date, daily, monthly)
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
