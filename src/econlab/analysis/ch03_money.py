"""Chapter 3 — Money & markets: returns, valuations, credit cycles.

Reproductions from primary data: the 'Rate of Return on Everything' pooled
means (JST), CAPE vs subsequent decade (Shiller), the Schularick-Taylor
credit-boom -> crisis result (with a hand-rolled IRLS logit), and revenue
concentration on a fixed top-500 universe (EDGAR coverage grows over time,
so naive all-filer shares are a composition artifact).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import new_fig, save, source_note

ASSET_CLASSES = {
    "jst/eq_tr": "Equities",
    "jst/housing_tr": "Housing",
    "jst/bond_tr": "Gov. bonds",
    "jst/bill_rate": "Bills",
}


# ---------- data ----------

def real_returns_panel() -> pd.DataFrame:
    """Annual real returns per country-year for the four JST asset classes."""
    with connect() as con:
        r = con.execute(
            "SELECT entity, year, series_id, value FROM obs WHERE series_id IN "
            "('jst/eq_tr','jst/housing_tr','jst/bond_tr','jst/bill_rate','jst/cpi')"
        ).df()
    p = r.pivot_table(index=["entity", "year"], columns="series_id", values="value").reset_index()
    p = p.sort_values(["entity", "year"])
    p["infl"] = p.groupby("entity")["jst/cpi"].pct_change()
    for col in ASSET_CLASSES:
        p[f"real_{col}"] = (1 + p[col]) / (1 + p["infl"]) - 1
    return p


def pooled_real_returns() -> pd.DataFrame:
    """Pooled and per-country mean real returns, 1870-2020 (trimmed of data errors)."""
    p = real_returns_panel()
    rows, dots = [], []
    for col, label in ASSET_CLASSES.items():
        real = p[f"real_{col}"].replace([np.inf, -np.inf], np.nan)
        ok = real[(real > -0.9) & (real < 3)]
        rows.append({"asset": label, "mean": 100 * ok.mean(), "n": int(ok.notna().sum())})
        per = (
            p.assign(r=real)[(real > -0.9) & (real < 3)]
            .groupby("entity")["r"].mean().mul(100)
        )
        dots.extend({"asset": label, "entity": e, "mean": v} for e, v in per.items())
    return pd.DataFrame(rows).set_index("asset"), pd.DataFrame(dots)


def cape_forward() -> tuple[pd.DataFrame, float, float, float]:
    """CAPE vs subsequent 10-yr real total return; returns (df, slope, intercept, current_cape)."""
    with connect() as con:
        sh = con.execute(
            "SELECT date, series_id, value FROM obs WHERE series_id IN "
            "('shiller/cape','shiller/sp_price','shiller/sp_div','shiller/cpi') ORDER BY date"
        ).df().pivot(index="date", columns="series_id", values="value")
    sh.index = pd.to_datetime(sh.index)
    sh = sh.resample("ME").last()
    real_p = sh["shiller/sp_price"] / sh["shiller/cpi"]
    real_d = sh["shiller/sp_div"] / sh["shiller/cpi"]
    tr = (real_p + real_d / 12).div(real_p.shift(1)).cumprod()
    fwd = (tr.shift(-120) / tr) ** (12 / 120) - 1
    df = pd.DataFrame({"cape": sh["shiller/cape"], "fwd": 100 * fwd}).dropna()
    slope, intercept = np.polyfit(df.cape, df.fwd, 1)
    current = float(sh["shiller/cape"].dropna().iloc[-1])
    return df, float(slope), float(intercept), current


def credit_crisis_stats() -> dict:
    """5-yr real credit growth ahead of crises vs normal times + IRLS logit beta."""
    with connect() as con:
        c = con.execute(
            "SELECT entity, year, series_id, value FROM obs WHERE series_id IN "
            "('jst/tloans','jst/cpi','jst/crisisJST')"
        ).df()
    cp = c.pivot_table(index=["entity", "year"], columns="series_id", values="value").reset_index()
    cp = cp.sort_values(["entity", "year"])
    cp["real_loans"] = cp["jst/tloans"] / cp["jst/cpi"]
    cp["g5"] = cp.groupby("entity")["real_loans"].transform(
        lambda s: 100 * ((s / s.shift(5)) ** (1 / 5) - 1)
    )
    cp["crisis_next"] = cp.groupby("entity")["jst/crisisJST"].transform(
        lambda s: s.shift(-1).rolling(2, min_periods=1).max()
    )
    sub = cp.dropna(subset=["g5", "crisis_next"])

    X = sub.g5.values / 100
    Y = (sub.crisis_next.values > 0).astype(float)
    Xm = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(2)
    for _ in range(30):  # IRLS Newton steps
        mu = 1 / (1 + np.exp(-(Xm @ b)))
        W = mu * (1 - mu) + 1e-9
        b = b + np.linalg.solve((Xm * W[:, None]).T @ Xm, Xm.T @ (Y - mu))

    return {
        "pre_crisis": sub[sub.crisis_next == 1].g5,
        "normal": sub[sub.crisis_next == 0].g5,
        "logit_beta": float(b[1]),
        "base_rate": float(Y.mean()),
    }


def revenue_concentration(universe: int = 500) -> pd.DataFrame:
    """Top-10/top-50 share of the top-`universe` filers' revenues per year.

    Fixed-N universe: EDGAR frame coverage triples over 2010-2024, so shares
    of ALL filers' totals are a composition artifact, not concentration.
    """
    with connect() as con:
        rev = con.execute(
            "SELECT year, entity, value FROM obs WHERE series_id='edgar/revenues' "
            "AND year BETWEEN 2010 AND 2025"
        ).df()
    rows = []
    for y, s in rev.groupby("year"):
        top = s.nlargest(universe, "value")["value"]
        if len(top) < universe:
            continue
        tot = top.sum()
        rows.append(
            {"year": y, "top10": 100 * top.head(10).sum() / tot,
             "top50": 100 * top.head(50).sum() / tot}
        )
    return pd.DataFrame(rows).set_index("year")


def crash_catalog(threshold: float = 0.20) -> pd.DataFrame:
    """Every real-price drawdown of the S&P ≥ `threshold` since 1871 (Shiller).

    Peak → trough → recovery episodes on the CPI-deflated S&P Composite price
    (real capital value; dividends excluded, as is standard for drawdowns).
    """
    with connect() as con:
        sh = con.execute(
            "SELECT date, series_id, value FROM obs WHERE series_id IN "
            "('shiller/sp_price','shiller/cpi') ORDER BY date"
        ).df().pivot(index="date", columns="series_id", values="value")
    sh.index = pd.to_datetime(sh.index)
    rp = (sh["shiller/sp_price"] / sh["shiller/cpi"]).dropna()

    episodes, peak_v, peak_d, trough_v, trough_d = [], rp.iloc[0], rp.index[0], rp.iloc[0], rp.index[0]
    for d, v in rp.items():
        if v >= peak_v:  # new high → close any open episode
            depth = trough_v / peak_v - 1
            if depth <= -threshold:
                episodes.append({"peak": peak_d, "trough": trough_d, "recovery": d,
                                 "depth_pct": 100 * depth,
                                 "fall_yrs": (trough_d - peak_d).days / 365.25,
                                 "recover_yrs": (d - trough_d).days / 365.25})
            peak_v, peak_d, trough_v, trough_d = v, d, v, d
        elif v < trough_v:
            trough_v, trough_d = v, d
    # an unrecovered drawdown still open at the end
    depth = trough_v / peak_v - 1
    if depth <= -threshold:
        episodes.append({"peak": peak_d, "trough": trough_d, "recovery": pd.NaT,
                         "depth_pct": 100 * depth, "fall_yrs": (trough_d - peak_d).days / 365.25,
                         "recover_yrs": np.nan})
    return pd.DataFrame(episodes).sort_values("depth_pct").reset_index(drop=True)


def long_rates() -> pd.DataFrame:
    """Long-term interest rate since 1703: BoE consols (UK) + Shiller/FRED 10y (US)."""
    with connect() as con:
        boe = con.execute(
            "SELECT year, value FROM obs WHERE series_id='boe/consol_yield' ORDER BY year"
        ).df().set_index("year")["value"]
        us = con.execute(
            "SELECT year, avg(value) v FROM obs WHERE series_id='shiller/gs10' GROUP BY 1 ORDER BY 1"
        ).df().set_index("year")["v"]
        us_now = con.execute(
            "SELECT year, avg(value) v FROM obs WHERE series_id='fred/DGS10' GROUP BY 1 ORDER BY 1"
        ).df().set_index("year")["v"]
    us_full = us.combine_first(us_now)
    return pd.DataFrame({"UK consol": boe, "US 10-year": us_full})


def yield_curve() -> tuple[pd.DataFrame, list]:
    """Monthly 10y-2y spread + the recessions that followed each inversion."""
    with connect() as con:
        sp = con.execute(
            "SELECT date, value FROM obs WHERE series_id='fred/T10Y2Y' ORDER BY date"
        ).df()
    sp["date"] = pd.to_datetime(sp["date"])
    monthly = sp.set_index("date")["value"].resample("ME").mean()
    # NBER US recessions since the spread series begins (curated reference dates)
    recessions = [("1980-01", "1980-07"), ("1981-07", "1982-11"), ("1990-07", "1991-03"),
                  ("2001-03", "2001-11"), ("2007-12", "2009-06"), ("2020-02", "2020-04")]
    return monthly.to_frame("spread"), recessions


# ---------- figures ----------

def fig_return_on_everything() -> None:
    pooled, dots = pooled_real_returns()
    fig, ax = new_fig(
        "The rate of return on everything, 1870-2020",
        subtitle="Mean annual real return, pooled over 16-18 economies (bars) with per-country means (dots). Equities ~= housing ~7%; safe assets far below.",
        ylabel="% per year, real",
    )
    x = np.arange(len(pooled))
    ax.bar(x, pooled["mean"], color="#1f6feb", width=0.55)
    for i, asset in enumerate(pooled.index):
        sub = dots[dots.asset == asset]
        ax.scatter(np.full(len(sub), i) + np.random.default_rng(7).uniform(-0.12, 0.12, len(sub)),
                   sub["mean"], s=14, color="#d1242f", alpha=0.6, zorder=3)
    for i, v in enumerate(pooled["mean"]):
        ax.text(i, v + 0.25, f"{v:.1f}", ha="center", fontweight="bold")
    ax.set_xticks(x, pooled.index)
    source_note(ax, "Source: computed from JST Macrohistory total returns vs CPI (econlab warehouse)")
    save(fig, "03_return_on_everything")


def fig_cape_forward() -> None:
    df, slope, intercept, current = cape_forward()
    implied = intercept + slope * current
    fig, ax = new_fig(
        "Valuations predict the decade, not the year",
        subtitle=f"Each dot a month, 1881-2016: CAPE vs the NEXT 10 years' real return. Today's CAPE {current:.1f} (99th percentile) implies ~{implied:.1f}%/yr.",
        ylabel="next 10y S&P real total return, %/yr",
    )
    ax.scatter(df.cape, df.fwd, s=6, alpha=0.35, color="#1f6feb")
    xs = np.linspace(df.cape.min(), max(df.cape.max(), current + 2), 100)
    ax.plot(xs, intercept + slope * xs, color="#d1242f", lw=2,
            label=f"fit: {intercept:.1f} {slope:+.2f}×CAPE")
    ax.axvline(current, color="#9a6700", lw=1.5, ls="--")
    ax.annotate(f"July 2026\nCAPE {current:.1f}", (current, 12), fontsize=9,
                color="#9a6700", ha="right")
    ax.legend()
    source_note(ax, "Source: computed from Shiller monthly data (econlab warehouse)")
    save(fig, "03_cape_forward")


def fig_credit_crises() -> None:
    s = credit_crisis_stats()
    fig, ax = new_fig(
        "Credit booms precede financial crises",
        subtitle=(
            f"5-yr real credit growth, 18 economies 1870-2020. Before crises: "
            f"{s['pre_crisis'].mean():.1f}%/yr vs {s['normal'].mean():.1f}% in normal times "
            f"(logit β = {s['logit_beta']:.1f}). The Schularick-Taylor result, reproduced."
        ),
        ylabel="density",
    )
    bins = np.linspace(-10, 25, 43)
    ax.hist(s["normal"], bins=bins, density=True, alpha=0.55, label="all other years",
            color="#1f6feb")
    ax.hist(s["pre_crisis"], bins=bins, density=True, alpha=0.55,
            label="1-2 years before a crisis", color="#d1242f")
    ax.axvline(s["normal"].mean(), color="#1f6feb", lw=2)
    ax.axvline(s["pre_crisis"].mean(), color="#d1242f", lw=2)
    ax.set_xlabel("5-yr annualized real loan growth, %")
    ax.legend()
    source_note(ax, "Source: computed from JST Macrohistory loans, CPI, crisis flags (econlab warehouse)")
    save(fig, "03_credit_crises")


def fig_concentration() -> None:
    conc = revenue_concentration()
    fig, ax = new_fig(
        "How top-heavy is corporate America?",
        subtitle="Share of top-500 US filers' revenues earned by the top 10 and top 50 (fixed universe; all-filer shares would be a coverage artifact).",
        ylabel="% of top-500 revenues",
    )
    ax.plot(conc.index, conc.top10, lw=2, marker="o", ms=4, label="top 10 share")
    ax.plot(conc.index, conc.top50, lw=2, marker="o", ms=4, label="top 50 share")
    ax.legend()
    print("[ch03] concentration:", conc.round(1).to_dict("index"))
    source_note(ax, "Source: computed from SEC EDGAR XBRL frames (econlab warehouse)")
    save(fig, "03_concentration")


def fig_crash_catalog() -> None:
    cat = crash_catalog().copy()
    cat["underwater"] = cat["fall_yrs"] + cat["recover_yrs"]
    print("[ch03] crashes >=20%:", len(cat), "| worst:",
          round(cat.iloc[0]["depth_pct"]), "at", str(cat.iloc[0]["peak"])[:7])
    fig, ax = new_fig(
        "Every S&P crash since 1871: how deep, how long underwater",
        subtitle="Real-price drawdowns ≥20% (CPI-deflated, Shiller). Vertical = depth; horizontal = years from the "
        "old peak back to it. The worst crashes cost a quarter-century of real gains.",
        ylabel="drawdown depth, %",
    )
    ax.scatter(cat["underwater"], cat["depth_pct"], s=90, alpha=0.7,
               color="#d1242f", edgecolor="#6e1119", zorder=3)
    labels = {"1929": "1929 crash", "1906": "1906–20", "1968": "Great Inflation\n1968–82",
              "2000": "dot-com +\nGFC 2000–14", "1876": "1876", "2021": "2022"}
    for _, r in cat.iterrows():
        key = str(r["peak"])[:4]
        if key in labels:
            dx = 0.6 if r["underwater"] < 25 else -0.6
            ha = "left" if dx > 0 else "right"
            ax.annotate(labels[key], (r["underwater"], r["depth_pct"]),
                        xytext=(r["underwater"] + dx, r["depth_pct"] + 2.5),
                        fontsize=8.5, ha=ha, color="#24292f")
    ax.set_xlabel("years underwater (peak → trough → back to peak, in real terms)")
    ax.set_xlim(0, cat["underwater"].max() * 1.15)
    source_note(ax, "Source: computed from Shiller S&P Composite / CPI (econlab warehouse)")
    save(fig, "03_crash_catalog")


def fig_long_rates() -> None:
    lr = long_rates()
    fig, ax = new_fig(
        "Three centuries of falling interest rates",
        subtitle="Long-term government bond yield: British consols from 1703, US 10-year from 1871. "
        "The 1974–1981 spike is the great exception — a two-generation aberration in a 300-year decline.",
        ylabel="long-term yield, % per year",
    )
    ax.plot(lr.index, lr["UK consol"], lw=1.6, color="#8250df", label="UK consol (1703–)")
    ax.plot(lr.index, lr["US 10-year"], lw=1.6, color="#1f6feb", label="US 10-year (1871–)")
    ax.axhline(0, color="#57606a", lw=0.8, ls=":")
    ax.annotate("Volcker peak 1981:\nUS 10y ≈ 15%", (1981, 14), fontsize=8.5, color="#d1242f", ha="center")
    ax.set_xlim(1700, 2030)
    ax.legend()
    source_note(ax, "Source: computed from Bank of England Millennium dataset + Shiller + FRED (econlab warehouse)")
    save(fig, "03_long_rates")


def fig_yield_curve() -> None:
    sp, recessions = yield_curve()
    fig, ax = new_fig(
        "The yield curve is the best recession alarm we have",
        subtitle="10-year minus 2-year Treasury yield (monthly). Every US recession since 1976 (shaded) was "
        "preceded by an inversion (spread below zero) 6–18 months earlier.",
        ylabel="10y − 2y spread, %",
    )
    ax.plot(sp.index, sp["spread"], lw=1.3, color="#1f6feb")
    ax.axhline(0, color="#d1242f", lw=1.2)
    ax.fill_between(sp.index, sp["spread"], 0, where=sp["spread"] < 0, color="#d1242f", alpha=0.4)
    for start, end in recessions:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color="#57606a", alpha=0.22)
    ax.set_ylim(-3, 4)
    source_note(ax, "Source: computed from FRED T10Y2Y; NBER recession reference dates (econlab warehouse)")
    save(fig, "03_yield_curve")


_EVENT_COL = {"crash": "#b42318", "pandemic": "#8250df", "war": "#1a1a1a",
              "political": "#b45309", "monetary": "#0d6e78", "disaster": "#8593a0"}
_EVENT_LABEL = {"crash": "financial crash", "pandemic": "pandemic", "war": "war / attack",
                "political": "political", "monetary": "monetary / policy", "disaster": "natural disaster"}


def fig_market_shocks() -> None:
    """A century of shocks: which kinds of event actually move markets?"""
    import matplotlib.pyplot as plt

    from .events import impact_by_category, run_events

    df = run_events()
    cat = impact_by_category(df)
    order = list(cat["category"])  # ascending by median drawdown (worst first)
    print("[ch03] event-study by category (median 3m drawdown): "
          + ", ".join(f"{r.category} {r.median_dd:.0f}%" for r in cat.itertuples()))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 6), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.suptitle("Markets fear financial contagion far more than bombs, viruses, or ballots",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    # Panel A: every event as a dot, grouped by category, medians marked
    ypos = {c: i for i, c in enumerate(order)}
    for c in order:
        sub = df[df["category"] == c]
        jitter = np.linspace(-0.22, 0.22, len(sub))
        ax1.scatter(sub["drawdown_3m"], [ypos[c]] * len(sub) + jitter, s=26,
                    color=_EVENT_COL[c], alpha=0.75, edgecolor="white", lw=0.4)
        med = cat.loc[cat["category"] == c, "median_dd"].iloc[0]
        ax1.plot([med, med], [ypos[c] - 0.32, ypos[c] + 0.32], color=_EVENT_COL[c], lw=2.4)
    ax1.set_yticks(range(len(order)), [f"{_EVENT_LABEL[c]}\n(median {cat.loc[cat.category==c,'median_dd'].iloc[0]:.0f}%)" for c in order], fontsize=8.5)
    ax1.axvline(0, color="#57606a", lw=0.8)
    ax1.set_xlabel("S&P 500 drawdown over the 3 months after the event, %")
    ax1.set_title("Each dot an event (n=93, 1906–2024); thick line = category median", fontsize=9.3, loc="left")
    ax1.set_xlim(-42, 6)

    # Panel B: the biggest single shocks, ranked
    top = df.nsmallest(12, "drawdown_3m").iloc[::-1]
    ax2.barh(range(len(top)), top["drawdown_3m"], color=[_EVENT_COL[c] for c in top["category"]])
    ax2.set_yticks(range(len(top)), [f"{n[:26]} ({str(d)[:4]})" for n, d in zip(top["name"], top["date"])], fontsize=7.6)
    for i, dd in enumerate(top["drawdown_3m"]):
        ax2.text(dd - 0.6, i, f"{dd:.0f}%", va="center", ha="right", fontsize=7.6)
    ax2.set_title("The 12 deepest shocks of the past century", fontsize=9.3, loc="left")
    ax2.set_xlabel("3-month drawdown, %")
    ax2.set_xlim(-46, 0)
    for c in order:
        ax2.scatter([], [], color=_EVENT_COL[c], marker="s", label=_EVENT_LABEL[c])
    ax2.legend(fontsize=7, loc="lower left", ncol=1)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.2, axis="x")
    fig.text(0.01, -0.01, "Source: event-study engine (analysis/events.py) over a curated 93-event catalog × S&P 500 daily (1927→) / "
             "monthly Shiller (1871→). Impact = drawdown from the pre-event close over the next quarter (econlab).", fontsize=7.2, color="#57606a")
    fig.tight_layout()
    save(fig, "03_market_shocks")


def fig_shock_aftermath() -> None:
    """Depth vs duration (recovery to new highs) and the volatility each shock unleashed."""
    import matplotlib.pyplot as plt

    from .events import run_events

    df = run_events()
    rec = df[df["recovery_days"].notna() & (df["recovery_days"] > 20)].copy()  # events that caused a real bear
    rec["rec_y"] = rec["recovery_days"] / 365
    vol = df[df["vol_peak"].notna()].groupby("category")["vol_peak"].median().sort_values()
    print(f"[ch03] aftermath: {len(rec)} event-driven bears; longest {rec['rec_y'].max():.0f}y; "
          f"crash peak-vol median {vol.get('crash', float('nan')):.0f}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.6), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.suptitle("Depth is set by the shock; how long the pain lasts is set by policy",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    for cat in _EVENT_COL:
        sub = rec[rec["category"] == cat]
        ax1.scatter(sub["drawdown_3m"], sub["rec_y"], s=40, color=_EVENT_COL[cat],
                    alpha=0.8, edgecolor="white", lw=0.5, label=_EVENT_LABEL[cat])
    ax1.set_yscale("log")
    ax1.set_yticks([0.1, 0.25, 0.5, 1, 2, 5, 10, 25], ["1mo", "3mo", "6mo", "1yr", "2yr", "5yr", "10yr", "25yr"], fontsize=8)
    ax1.set_xlabel("3-month drawdown, %")
    ax1.set_ylabel("time to regain the pre-event high")
    ax1.set_title("Same depth, wildly different duration", fontsize=9.3, loc="left")
    lab = {"COVID-19 — US market-crash onset": "COVID (0.5yr)", "Black Tuesday (1929 Crash)": "1929 (23yr)",
           "Lehman Brothers Bankruptcy": "Lehman (2.3yr)", "Dot-Com Peak": "dot-com (7yr)"}
    for r in rec.itertuples():
        if r.name in lab:
            ax1.annotate(lab[r.name], (r.drawdown_3m, r.rec_y), fontsize=8, fontweight="bold",
                         xytext=(6, 0), textcoords="offset points", va="center")
    ax1.legend(fontsize=7, loc="upper left", ncol=2)

    ax2.barh(range(len(vol)), vol.values, color=[_EVENT_COL[c] for c in vol.index])
    ax2.set_yticks(range(len(vol)), [_EVENT_LABEL[c] for c in vol.index], fontsize=8.5)
    for i, v in enumerate(vol.values):
        ax2.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=8)
    ax2.set_title("Peak volatility unleashed (median, ann. %)", fontsize=9.3, loc="left")
    ax2.set_xlabel("peak 21-day realized volatility, %")
    ax2.set_xlim(0, vol.max() * 1.18)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.2)
    fig.text(0.01, -0.02, "Source: event-study engine over the 93-event catalog × S&P 500 (econlab). Recovery = days to regain the "
             "pre-event level after a ≥10% drawdown; volatility = 21-day realized, annualized (daily era, 1927→).", fontsize=7.2, color="#57606a")
    fig.tight_layout()
    save(fig, "03_shock_aftermath")


def fig_market_upside() -> None:
    """What drives the UP moves: policy pivots and rebounds — the Fed calls the bottom."""
    import matplotlib.pyplot as plt

    from .events import impact_by_category, run_events

    df = run_events()
    top = df.nlargest(12, "ret_3m").iloc[::-1]
    cat = impact_by_category(df).sort_values("median_ret3")
    print("[ch03] biggest up-move: " + f"{top.iloc[-1]['name']} +{top.iloc[-1]['ret_3m']:.0f}%; "
          + "median 3m return by cat: " + ", ".join(f"{r.category} {r.median_ret3:+.0f}%" for r in cat.itertuples()))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.6), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.suptitle("What drives the up-moves: policy pivots and rebounds — the Fed calls the bottom",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    ax1.barh(range(len(top)), top["ret_3m"], color=[_EVENT_COL[c] for c in top["category"]])
    ax1.set_yticks(range(len(top)), [f"{n[:30]} ({str(d)[:4]})" for n, d in zip(top["name"], top["date"])], fontsize=7.6)
    for i, v in enumerate(top["ret_3m"]):
        ax1.text(v + 0.6, i, f"+{v:.0f}%", va="center", fontsize=7.8)
    ax1.set_title("The 12 biggest 3-month rallies", fontsize=9.3, loc="left")
    ax1.set_xlabel("3-month S&P return, %")
    ax1.set_xlim(0, top["ret_3m"].max() * 1.14)
    for c in _EVENT_COL:
        ax1.scatter([], [], color=_EVENT_COL[c], marker="s", label=_EVENT_LABEL[c])
    ax1.legend(fontsize=6.8, loc="lower right", ncol=1)

    colors = ["#157a52" if v > 0 else "#b42318" for v in cat["median_ret3"]]
    ax2.barh(range(len(cat)), cat["median_ret3"], color=colors)
    ax2.set_yticks(range(len(cat)), [_EVENT_LABEL[c] for c in cat["category"]], fontsize=8.5)
    for i, v in enumerate(cat["median_ret3"]):
        ax2.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:+.1f}%", va="center",
                 ha="left" if v >= 0 else "right", fontsize=8)
    ax2.axvline(0, color="#57606a", lw=0.8)
    ax2.set_title("Median 3-month return, by event type", fontsize=9.3, loc="left")
    ax2.set_xlabel("median S&P return 3 months after, %")
    ax2.set_xlim(-4, 7)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.2, axis="x")
    fig.text(0.01, -0.02, "Source: event-study engine over the 93-event catalog × S&P 500 (econlab). Positive catalysts include Fed "
             "pivots (QE, rate cuts, 'whatever it takes'), the 1933 & 2009 & 2020 bottoms, and vaccine/relief rallies.", fontsize=7.2, color="#57606a")
    fig.tight_layout()
    save(fig, "03_market_upside")


def fig_safe_havens() -> None:
    """Apply the engine to OTHER assets: when stocks crash, do gold, bonds and oil
    respond oppositely? And what splits the shocks that Treasuries can hedge from
    the ones they can't?"""
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    from .events import run_multi_asset

    df = run_multi_asset().sort_values("Stocks")   # worst equity shock at the top
    cols = ["Stocks", "Bonds", "Gold", "Oil"]
    M = df[cols].to_numpy(dtype=float)

    reg = df.groupby("regime")[cols].mean()
    for r in ("Demand (oil ↓)", "Supply (oil ↑)"):
        if r not in reg.index:
            reg.loc[r] = np.nan
    reg = reg.loc[["Demand (oil ↓)", "Supply (oil ↑)"]]
    print("[ch03] safe-haven regimes | "
          + " | ".join(f"{r}: bonds {reg.loc[r,'Bonds']:+.1f}%, gold {reg.loc[r,'Gold']:+.1f}%,"
                       f" oil {reg.loc[r,'Oil']:+.1f}%" for r in reg.index))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw={"width_ratios": [1.28, 1]})
    fig.suptitle("Apply the engine to every asset: gold and bonds hedge stocks — but only gold survives a supply shock",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.3)

    # Panel A — the response matrix: each shock × each asset, green = you made money
    norm = TwoSlopeNorm(vmin=-30, vcenter=0, vmax=30)
    ax1.imshow(np.clip(M, -30, 30), cmap="RdYlGn", norm=norm, aspect="auto")
    ax1.set_xticks(range(len(cols)), cols, fontsize=9.5)
    ax1.xaxis.tick_top()
    ylab = [f"{n[:26]} ({d[:4]})" for n, d in zip(df["name"], df["date"])]
    ax1.set_yticks(range(len(df)), ylab, fontsize=7.7)
    for i in range(len(df)):
        for j, c in enumerate(cols):
            v = M[i, j]
            ax1.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=7.6,
                     color="white" if abs(v) > 17 else "#1a1a1a")
    # mark each shock's regime in the left margin
    for i, rg in enumerate(df["regime"]):
        ax1.text(-0.95, i, "▲" if "Supply" in rg else "▼", ha="center", va="center",
                 fontsize=7.5, color="#b45309" if "Supply" in rg else "#0d6e78")
    ax1.set_title("1-month response to each shock (%)   ▲ oil-up  ▼ oil-down", fontsize=9, loc="left", pad=20)
    ax1.set_xlim(-1.4, len(cols) - 0.5)
    for sp in ax1.spines.values():
        sp.set_visible(False)
    ax1.tick_params(length=0)

    # Panel B — the two regimes: does oil's sign predict whether bonds protect you?
    x = np.arange(len(cols))
    dem, sup = reg.loc["Demand (oil ↓)"], reg.loc["Supply (oil ↑)"]
    ax2.bar(x - 0.2, dem, 0.4, color="#0d6e78", label="Demand shock (oil ↓)")
    ax2.bar(x + 0.2, sup, 0.4, color="#b45309", label="Supply shock (oil ↑)")
    ax2.axhline(0, color="#57606a", lw=0.8)
    for xi, (d, s) in enumerate(zip(dem, sup)):
        ax2.text(xi - 0.2, d + (0.5 if d >= 0 else -0.5), f"{d:+.0f}", ha="center",
                 va="bottom" if d >= 0 else "top", fontsize=8)
        ax2.text(xi + 0.2, s + (0.5 if s >= 0 else -0.5), f"{s:+.0f}", ha="center",
                 va="bottom" if s >= 0 else "top", fontsize=8)
    ax2.set_xticks(x, cols, fontsize=9.5)
    ax2.set_ylabel("average 1-month response, %")
    ax2.set_title("Bonds hedge a demand panic but fail a supply shock;\ngold is the only universal hedge",
                  fontsize=9, loc="left")
    ax2.legend(fontsize=8, loc="upper right")
    ax2.margins(y=0.18)

    source_note(ax1, "S&P 500, 10y Treasury (yield → price via 8y duration), gold & WTI front-month futures. "
                     "Response = change over the month after the last close before the event. 21st-century shocks (daily data for all four).")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "03_safe_havens")


def fig_global_contagion() -> None:
    """Widen the event study across borders: do global markets crash together?"""
    import matplotlib.pyplot as plt

    from .events import CONTAGION_INDICES, run_global_contagion

    df, corr, means = run_global_contagion()
    order = sorted(corr.items(), key=lambda x: x[1])   # low corr (decoupled) at bottom
    print("[ch03] contagion corr w/ S&P: " + ", ".join(
        f"{CONTAGION_INDICES[k].split(' ')[0]} {v:.2f}" for k, v in sorted(corr.items(), key=lambda x: -x[1])))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1.05]})
    fig.suptitle("Widen the lens: developed markets crash in lockstep — only Greater China decouples",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.4)

    labels = [CONTAGION_INDICES[k] for k, _ in order]
    vals = [v for _, v in order]
    cols = ["#b45309" if v < 0.75 else "#0d6e78" for v in vals]
    ax1.barh(range(len(order)), vals, color=cols)
    ax1.set_yticks(range(len(order)), labels, fontsize=8.5)
    for i, v in enumerate(vals):
        ax1.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8.3)
    ax1.set_title("Correlation with the S&P's shock drawdown\n(across 14 shocks, 2000–2023)", fontsize=9.2, loc="left")
    ax1.set_xlabel("correlation of 1-month drawdowns with the S&P 500")
    ax1.set_xlim(0, 1.08)
    ax1.axvline(0.75, color="#8593a0", lw=0.8, ls=":")
    ax1.scatter([], [], color="#0d6e78", marker="s", label="crashes with the US (≥0.75)")
    ax1.scatter([], [], color="#b45309", marker="s", label="decouples")
    ax1.legend(fontsize=7.6, loc="lower right")

    # Panel B — the decoupling shown directly: DAX hugs the diagonal, Shanghai scatters
    ax2.plot([-40, 5], [-40, 5], color="#8593a0", lw=0.9, ls="--", zorder=1)
    ax2.text(-37, -34, "45° = moves\nwith the US", fontsize=7.2, color="#8593a0")
    for sid, lab, col in [("markets/dax", "DAX (Germany)", "#0d6e78"), ("markets/shanghai", "Shanghai (China)", "#b45309")]:
        ax2.scatter(df["markets/spx"], df[sid], color=col, s=34, label=lab, zorder=3, edgecolor="white", linewidth=0.5)
    ax2.set_xlabel("S&P 500 1-month drawdown, %")
    ax2.set_ylabel("index 1-month drawdown, %")
    ax2.set_title("Every shock: the foreign market vs the S&P\n(on the line = perfect contagion)", fontsize=9.2, loc="left")
    ax2.legend(fontsize=8, loc="upper left")

    source_note(ax1, "Daily index prices (markets/*). Drawdown = trough over 32 days from the last close before each of the "
                     "14 multi-asset shock events. Shanghai fell a mean −6.2% vs the S&P's −9.7% — shallowest and least synced.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "03_global_contagion")


def fig_currency_havens() -> None:
    """The FX leg of the multi-asset study: which currencies are the crisis havens?"""
    import matplotlib.pyplot as plt
    import numpy as np

    from .events import HAVEN_FX, run_currency_havens

    cur = run_currency_havens()
    cols = list(HAVEN_FX)
    med = cur.groupby("regime")[cols].median()
    labels = [HAVEN_FX[c][0] for c in cols]
    print("[ch03] FX havens | " + " | ".join(
        f"{r}: " + ", ".join(f"{HAVEN_FX[c][0].split(' ')[0]} {med.loc[r, c]:+.1f}" for c in cols) for r in med.index))

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    fig.suptitle("The FX leg: the dollar and yen hedge a demand panic — but the haven trade breaks in a supply shock",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)
    x = np.arange(len(cols))
    dem = med.loc["Demand (oil ↓)"]
    sup = med.loc["Supply (oil ↑)"]
    ax.bar(x - 0.2, dem, 0.4, color="#0d6e78", label="Demand shock (oil ↓ — the real crashes)")
    ax.bar(x + 0.2, sup, 0.4, color="#b45309", label="Supply shock (oil ↑ — geopolitical)")
    ax.axhline(0, color="#57606a", lw=0.8)
    for xi, (d, s) in enumerate(zip(dem, sup)):
        ax.text(xi - 0.2, d + (0.06 if d >= 0 else -0.06), f"{d:+.1f}", ha="center",
                va="bottom" if d >= 0 else "top", fontsize=8.5)
        ax.text(xi + 0.2, s + (0.06 if s >= 0 else -0.06), f"{s:+.1f}", ha="center",
                va="bottom" if s >= 0 else "top", fontsize=8.5)
    ax.set_xticks(x, labels, fontsize=10)
    ax.set_ylabel("median 1-month move, % (positive = the currency strengthened)")
    ax.set_title("In a demand panic money runs to the dollar and yen (euro weakens); in a supply shock the signal dissolves",
                 fontsize=9, loc="left")
    ax.legend(fontsize=8.5, loc="upper right")
    ax.margins(y=0.16)
    source_note(ax, "Broad dollar index (fred/DTWEXBGS, 2006+), USD/JPY, EUR/USD; 1-month move from the last close before each "
                    "shock, oriented so + = that currency strengthened. Small samples (7–8 demand, 4–5 supply events).")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "03_currency_havens")


def main() -> None:
    fig_return_on_everything()
    fig_long_rates()
    fig_crash_catalog()
    fig_market_shocks()
    fig_shock_aftermath()
    fig_market_upside()
    fig_safe_havens()
    fig_global_contagion()
    fig_currency_havens()
    fig_yield_curve()
    fig_cape_forward()
    fig_credit_crises()
    fig_concentration()


if __name__ == "__main__":
    main()
