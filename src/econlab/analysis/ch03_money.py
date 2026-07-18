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


def main() -> None:
    fig_return_on_everything()
    fig_cape_forward()
    fig_credit_crises()
    fig_concentration()


if __name__ == "__main__":
    main()
