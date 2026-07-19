"""Chapter 9 — What Things Cost: the household experience of prices.

The prices of the things people actually buy — home, fuel, groceries,
childcare, healthcare, clothing — computed from BLS CPI item detail (via FRED
and the BLS API), house-price indices, and wages. Four cuts: the goods-vs-
services divergence, necessities vs wages (the affordability squeeze),
housing (levels, price-to-income, by state), and the socioeconomic core —
inflation is not one number; the poor and the rich buy different baskets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note


def annual(series_id: str) -> pd.Series:
    """Annual-average value of a series (collapses monthly/quarterly)."""
    with connect() as con:
        return con.execute(
            "SELECT year, avg(value) v FROM obs WHERE series_id=? GROUP BY 1 ORDER BY 1",
            [series_id],
        ).df().set_index("year")["v"]


def indexed(series_id: str, base: int) -> pd.Series | None:
    """Series rebased to base=100; None if empty or the base year is missing."""
    s = annual(series_id)
    if s.empty or base not in s.index:
        return None
    return s / s.loc[base] * 100


# what each line is, and its FRED/BLS series id
DIVERGENCE = {
    "Childcare": ("bls/childcare", "up"),
    "College & school fees": ("fred/CUUR0000SEEB", "up"),
    "Hospital services": ("fred/CUUR0000SEMD", "up"),
    "Housing": ("fred/CPIHOSSL", "up"),
    "All items (CPI)": ("fred/CPIAUCSL", "ref"),
    "New cars": ("fred/CUUR0000SETA01", "down"),
    "Apparel": ("fred/CPIAPPSL", "down"),
    "Toys": ("fred/CUUR0000SERE01", "down"),
    "Software": ("fred/CUUR0000SEEE01", "down"),
    "Televisions": ("bls/televisions", "down"),
}


def price_divergence(base: int = 2000) -> pd.DataFrame:
    cols = {}
    for label, (sid, _) in DIVERGENCE.items():
        s = indexed(sid, base)
        if s is not None:
            cols[label] = s
    cols["Wages"] = indexed("fred/AHETPI", base)
    return pd.DataFrame(cols).loc[base:2024]


NECESSITIES = {
    "Rent": "fred/CUUR0000SEHA",
    "Groceries (food at home)": "fred/CUUR0000SAF11",
    "Gasoline": "fred/CUUR0000SETB01",
    "Electricity": "fred/CUUR0000SEHF01",
}


def necessities_vs_wages(base: int = 1970) -> pd.DataFrame:
    cols = {k: indexed(v, base) for k, v in NECESSITIES.items()}
    cols["Wages"] = indexed("fred/AHETPI", base)
    cols["All items (CPI)"] = indexed("fred/CPIAUCSL", base)
    return pd.DataFrame({k: v for k, v in cols.items() if v is not None})


def housing_view() -> dict:
    """Real home price (deflated by CPI), price-to-income, and state HPI."""
    price = annual("fred/MSPUS")                 # median sale price, $
    cpi = annual("fred/CPIAUCSL")
    inc = annual("fred/MEHOINUSA646N")           # median household income, $
    real_price = (price / cpi * cpi.loc[2024]).dropna()
    p2i = (price / inc).dropna()
    states = {s: indexed(f"fred/{s}STHPI", 1990) for s in ("CA", "TX", "OH", "FL", "NY")}
    us_hpi = indexed("fred/USSTHPI", 1990)
    return {"real_price": real_price, "p2i": p2i, "states": pd.DataFrame(states),
            "us_hpi": us_hpi, "nominal": price}


# Curated CEX expenditure shares (% of total spending) by income quintile,
# mapped to CPI major groups. Approximate, from BLS Consumer Expenditure Survey
# (2022 tables). The gradient — the poor spend far more on necessities — is the
# robust fact; exact shares vary a few points by year.
CEX_SHARES = {          # category: (lowest 20%, highest 20%)  -> CPI series
    "Housing":        ((40, 30), "fred/CPIHOSSL"),
    "Food":           ((16, 11), "fred/CPIUFDSL"),
    "Energy":         (( 9,  5), "fred/CPIENGSL"),
    "Transportation": ((11, 16), "fred/CPITRNSL"),
    "Medical":        (( 8,  6), "fred/CPIMEDSL"),
    "Apparel":        (( 3,  3), "fred/CPIAPPSL"),
    "Education":      (( 2,  6), "fred/CPIEDUSL"),
    "Other":          ((11, 23), "fred/CPIAUCSL"),
}


def inflation_by_income() -> pd.DataFrame:
    """Effective annual inflation for low- vs high-income baskets (CEX-weighted)."""
    yoy = {}
    for _, (_, sid) in CEX_SHARES.items():
        s = annual(sid)
        yoy[sid] = s.pct_change() * 100
    low_w = np.array([s[0] for s, _ in CEX_SHARES.values()], float)
    high_w = np.array([s[1] for s, _ in CEX_SHARES.values()], float)
    low_w /= low_w.sum(); high_w /= high_w.sum()
    sids = [sid for _, sid in CEX_SHARES.values()]
    M = pd.DataFrame({sid: yoy[sid] for sid in sids}).dropna()
    out = pd.DataFrame({
        "low_income": M[sids].values @ low_w,
        "high_income": M[sids].values @ high_w,
    }, index=M.index)
    out["gap"] = out.low_income - out.high_income
    return out.loc[2001:]


# ---------- figures ----------

def fig_price_divergence() -> None:
    d = price_divergence()
    end = d.iloc[-1]
    print("[ch09] divergence 2000->2024:", {k: round(end[k]) for k in
          ("Childcare", "Hospital services", "Televisions", "Software", "Wages") if k in end.index})
    fig, ax = new_fig(
        "The great price divergence: services soared, goods collapsed",
        subtitle="Price of each category, 2000 = 100 (BLS/FRED). What you buy from people (care, school, hospitals) "
        "outran wages; what you buy from factories (TVs, toys, clothes) fell — often absolutely.",
        ylabel="price index, 2000 = 100",
    )
    color = {"up": "#d1242f", "down": "#1f6feb", "ref": "#24292f"}
    for label, (sid, kind) in DIVERGENCE.items():
        if label not in d.columns:
            continue
        s = d[label].dropna()
        lw = 2.4 if kind == "ref" else 1.7
        ax.plot(s.index, s, lw=lw, color=color[kind],
                ls="--" if kind == "ref" else "-", alpha=0.9)
        ax.annotate(f"{label} {s.iloc[-1]:.0f}", (s.index[-1], s.iloc[-1]), xytext=(5, 0),
                    textcoords="offset points", fontsize=7.8, color=color[kind], va="center")
    w = d["Wages"].dropna()
    ax.plot(w.index, w, lw=2.4, color="#1a7f37", label="Wages")
    ax.annotate(f"Wages {w.iloc[-1]:.0f}", (w.index[-1], w.iloc[-1]), xytext=(5, 0),
                textcoords="offset points", fontsize=8.2, color="#1a7f37", fontweight="bold", va="center")
    ax.set_xlim(2000, 2032)
    ax.axhline(100, color="#57606a", lw=0.7, ls=":")
    ax.text(2001, 320, "red = rose faster than wages (less affordable)\nblue = fell in dollar terms (cheaper)",
            fontsize=8.5, color="#57606a", va="top")
    source_note(ax, "Source: computed from BLS CPI item detail via FRED + BLS API, avg hourly earnings (econlab warehouse)")
    save(fig, "09_price_divergence")


def fig_necessities() -> None:
    n = necessities_vs_wages()
    print("[ch09] necessities 1970->2024 (index):", {k: round(n[k].dropna().iloc[-1]) for k in NECESSITIES})
    fig, ax = new_fig(
        "The staples mostly held the line against the paycheck",
        subtitle="Rent, groceries, electricity, gasoline vs the average hourly wage, 1970 = 100 (BLS/FRED). In work-hours "
        "the staples barely moved in 50 years (groceries fell); gasoline is volatile. The squeeze is F1's — homes, care, college.",
        ylabel="index, 1970 = 100",
    )
    colors = {"Rent": "#d1242f", "Groceries (food at home)": "#9a6700",
              "Gasoline": "#8250df", "Electricity": "#0969da"}
    for k, c in colors.items():
        s = n[k].dropna()
        ax.plot(s.index, s, lw=1.8, color=c, label=k)
    ax.plot(n.index, n["Wages"], lw=2.6, color="#1a7f37", label="Wages")
    ax.plot(n.index, n["All items (CPI)"], lw=1.4, color="#24292f", ls="--", label="All items (CPI)")
    ax.legend(fontsize=8.5, ncol=2, loc="upper left")
    source_note(ax, "Source: computed from BLS CPI rent/food/gasoline/electricity + avg hourly earnings (econlab warehouse)")
    save(fig, "09_necessities")


def fig_housing() -> None:
    import matplotlib.pyplot as plt

    h = housing_view()
    p2i_1970 = h["p2i"].loc[1970] if 1970 in h["p2i"].index else h["p2i"].iloc[0]
    print("[ch09] real home price 1963 vs 2024:", round(h["real_price"].iloc[0]),
          round(h["real_price"].iloc[-1]), "| price/income latest:", round(h["p2i"].iloc[-1], 1))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Housing: the biggest line item in every budget", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    ax1.plot(h["real_price"].index, h["real_price"] / 1000, lw=2, color=PALETTE[1], label="real median price (2024 \\$)")
    ax1b = ax1.twinx()
    ax1b.plot(h["p2i"].index, h["p2i"], lw=2, color=PALETTE[0], label="price-to-income (right)")
    ax1.set_title("Real median home price & price-to-income ratio", fontsize=10, loc="left")
    ax1.set_ylabel("real median price, \\$k (2024)", color=PALETTE[1])
    ax1b.set_ylabel("price ÷ median income", color=PALETTE[0])
    ax1.set_xlim(1963, 2026)

    for st, c in zip(["CA", "FL", "TX", "OH", "NY"], [PALETTE[1], PALETTE[4], PALETTE[3], PALETTE[2], PALETTE[0]]):
        s = h["states"][st].dropna()
        ax2.plot(s.index, s, lw=1.8, color=c, label=st)
    ax2.set_title("House prices by state, 1990 = 100 (FHFA)", fontsize=10, loc="left")
    ax2.set_ylabel("index, 1990 = 100")
    ax2.legend(fontsize=8.5, ncol=2)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: computed from FRED median sale price, median household income, FHFA state HPI, CPI (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_housing")


def fig_inflation_inequality() -> None:
    import matplotlib.pyplot as plt

    inf = inflation_by_income()
    cum_low = (1 + inf.low_income / 100).cumprod() * 100
    cum_high = (1 + inf.high_income / 100).cumprod() * 100
    print(f"[ch09] cumulative 2001-25 inflation: low={cum_low.iloc[-1]-100:.0f}% high={cum_high.iloc[-1]-100:.0f}%; "
          f"biggest annual gap {inf.gap.max():.1f}pp in {int(inf.gap.idxmax())}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.3]})
    fig.suptitle("Inflation is not one number: the poor and the rich buy different baskets",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # left: expenditure-share composition (the WHY)
    cats = list(CEX_SHARES)
    low = np.array([CEX_SHARES[c][0][0] for c in cats], float)
    high = np.array([CEX_SHARES[c][0][1] for c in cats], float)
    low = low / low.sum() * 100
    high = high / high.sum() * 100
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(cats))]
    b_low = b_high = 0.0
    for i, c in enumerate(cats):
        ax1.bar(0, low[i], bottom=b_low, color=colors[i], width=0.7)
        ax1.bar(1, high[i], bottom=b_high, color=colors[i], width=0.7,
                label=c if i < len(cats) else None)
        if low[i] > 4:
            ax1.text(0, b_low + low[i] / 2, c, ha="center", va="center", fontsize=7, color="white")
        b_low += low[i]; b_high += high[i]
    ax1.set_xticks([0, 1], ["Lowest\nfifth", "Highest\nfifth"])
    ax1.set_ylabel("% of household spending")
    nec_low = low[:3].sum(); nec_high = high[:3].sum()
    ax1.set_title(f"Necessities = {nec_low:.0f}% of the poor's budget\nvs {nec_high:.0f}% of the rich's",
                  fontsize=9.5, loc="left")
    ax1.set_ylim(0, 100)

    # right: cumulative basket cost (the RESULT)
    ax2.plot(cum_low.index, cum_low, lw=2.4, color="#d1242f", label="lowest-income fifth")
    ax2.plot(cum_high.index, cum_high, lw=2.4, color="#1f6feb", label="highest-income fifth")
    ax2.fill_between(cum_low.index, cum_low, cum_high, color="#d1242f", alpha=0.12)
    ax2.set_title("Cost of each group's basket, 2001 = 100", fontsize=9.5, loc="left")
    ax2.set_ylabel("basket cost index")
    ax2.annotate(f"by 2025 the poor's basket\ncosts {cum_low.iloc[-1]:.0f} vs {cum_high.iloc[-1]:.0f} — a "
                 f"{cum_low.iloc[-1]-cum_high.iloc[-1]:.0f}-point gap",
                 (cum_low.index[-1], cum_low.iloc[-1]), xytext=(2004, 185),
                 fontsize=8.5, color="#d1242f", arrowprops=dict(arrowstyle="->", color="#d1242f"))
    ax2.legend(fontsize=9, loc="upper left")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02, "Source: computed from CPI major groups × curated BLS Consumer Expenditure Survey shares by income quintile (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_inflation_inequality")


def main() -> None:
    fig_price_divergence()
    fig_necessities()
    fig_housing()
    fig_inflation_inequality()


if __name__ == "__main__":
    main()
