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


def main() -> None:
    fig_return_on_everything()
    fig_long_rates()
    fig_crash_catalog()
    fig_yield_curve()
    fig_cape_forward()
    fig_credit_crises()
    fig_concentration()


if __name__ == "__main__":
    main()
