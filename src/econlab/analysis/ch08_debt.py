"""Chapter 8 — The Debt Ledger: who owes, who owns, who pays.

Ownership of the US federal debt (holder decomposition + foreign holders),
what households pay (measured ratios + stocks-x-rates estimates), and how the
burden distributes across countries, income groups, and demographics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

MORT_EFF, STU_RATE, OTHER_RATE = 4.3, 5.5, 8.0  # stated assumptions (see prose)

INCOME_GROUPS = {
    "pct00to20": "Bottom 20%", "pct20to40": "20-40%", "pct40to60": "40-60%",
    "pct60to80": "60-80%", "pct80to99": "80-99%", "pct99to100": "Top 1%",
}
RACE_GROUPS = {"white": "White", "black": "Black", "hispanic": "Hispanic", "other": "Other"}
AGE_GROUPS = {"ageunder40": "Under 40", "age40to54": "40-54",
              "age55to69": "55-69", "age70plus": "70+"}


def _latest(con, sid: str) -> float:
    v = con.execute(
        "SELECT max_by(value, date) FROM obs WHERE series_id=?", [sid]
    ).fetchone()[0]
    return float(v) if v is not None else 0.0


# ---------- data ----------

def federal_debt_holders() -> pd.DataFrame:
    """Annual shares of US federal debt by holder class, 1970->."""
    with connect() as con:
        frames = {}
        for sid, label in [("fred/GFDEBTN", "total"), ("fred/FDHBFIN", "foreign"),
                           ("fred/FDHBFRBN", "fed"), ("fred/FDHBPIN", "private")]:
            frames[label] = con.execute(
                "SELECT year, avg(value) v FROM obs WHERE series_id=? GROUP BY 1 ORDER BY 1",
                [sid],
            ).df().set_index("year")["v"]
    df = pd.DataFrame(frames).dropna()
    out = pd.DataFrame(index=df.index)
    out["Foreign & international"] = 100 * df["foreign"] / df["total"]
    out["Federal Reserve"] = 100 * df["fed"] / df["total"]
    out["Domestic private"] = 100 * df["private"] / df["total"]
    out["Gov. trust funds & other"] = (100 - out.sum(axis=1)).clip(lower=0)
    return out


def top_foreign_holders(n: int = 10) -> pd.DataFrame:
    with connect() as con:
        return con.execute(
            """
            SELECT e.name, max_by(o.value, o.date) AS v
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='tic/us_treasury_holdings' AND o.entity != 'WLD'
            GROUP BY 1 ORDER BY v DESC LIMIT ?
            """, [n],
        ).df()


def consumer_blend_rate(con) -> float:
    rev, nonrev = _latest(con, "fred/REVOLSL"), _latest(con, "fred/NONREVSL")
    stu, auto = _latest(con, "fred/SLOAS"), _latest(con, "fred/MVLOAS")
    cc, ar = _latest(con, "fred/TERMCBCCALLNS"), _latest(con, "fred/TERMCBAUTO48NS")
    return (rev * cc + auto * ar + stu * STU_RATE + (nonrev - stu - auto) * OTHER_RATE) / (rev + nonrev)


def group_burdens(prefix: str, groups: dict[str, str]) -> pd.DataFrame:
    """Per-household mortgage/consumer stocks + est. interest for a DFA dimension."""
    with connect() as con:
        blend = consumer_blend_rate(con)
        rows = []
        for grp, label in groups.items():
            hh = _latest(con, f"dfa/{prefix}.household_count.{grp}")
            m = _latest(con, f"dfa/{prefix}.home_mortgages.{grp}")
            c = _latest(con, f"dfa/{prefix}.consumer_credit.{grp}")
            if not hh:
                continue
            rows.append({
                "group": label, "households": hh,
                "mortgage_hh": m / hh, "consumer_hh": c / hh,
                "int_mortgage_hh": m / hh * MORT_EFF / 100,
                "int_consumer_hh": c / hh * blend / 100,
                "consumer_share": 100 * c / (m + c),
            })
    return pd.DataFrame(rows).set_index("group")


def burden_history() -> pd.DataFrame:
    """Estimated interest / income by income bracket, annual 1995->2024.

    Rates are time-varying: mortgage effective proxy = 10-yr trailing mean of
    the 30-yr rate; consumer rate = card/auto rates weighted by the national
    revolving/nonrevolving stock mix. Income = Census H-3 mean per quintile.
    """
    with connect() as con:
        def annual(sid: str) -> pd.Series:
            return con.execute(
                "SELECT year, avg(value) v FROM obs WHERE series_id=? GROUP BY 1 ORDER BY 1",
                [sid],
            ).df().set_index("year")["v"]

        m_eff = annual("fred/MORTGAGE30US").rolling(10, min_periods=5).mean()
        cc, au = annual("fred/TERMCBCCALLNS").ffill(), annual("fred/TERMCBAUTO48NS").ffill()
        rev, nonrev = annual("fred/REVOLSL"), annual("fred/NONREVSL")
        c_rate = (rev * cc + nonrev * au) / (rev + nonrev)

        out = {}
        quintiles = [("pct00to20", "q1"), ("pct20to40", "q2"),
                     ("pct40to60", "q3"), ("pct60to80", "q4")]
        for grp, q in quintiles + [("TOP20", "q5")]:
            if grp == "TOP20":
                hh = annual("dfa/inc.household_count.pct80to99") + annual("dfa/inc.household_count.pct99to100")
                m = annual("dfa/inc.home_mortgages.pct80to99") + annual("dfa/inc.home_mortgages.pct99to100")
                c = annual("dfa/inc.consumer_credit.pct80to99") + annual("dfa/inc.consumer_credit.pct99to100")
            else:
                hh = annual(f"dfa/inc.household_count.{grp}")
                m = annual(f"dfa/inc.home_mortgages.{grp}")
                c = annual(f"dfa/inc.consumer_credit.{grp}")
            inc = annual(f"census/mean_hh_income.{q}")
            out[q] = 100 * ((m / hh) * m_eff / 100 + (c / hh) * c_rate / 100) / inc
    return pd.DataFrame(out).dropna()


def debt_service_history() -> pd.DataFrame:
    with connect() as con:
        frames = {}
        for sid, label in [("fred/TDSP", "total"), ("fred/MDSP", "mortgage"),
                           ("fred/CDSP", "consumer")]:
            s = con.execute(
                "SELECT date, value FROM obs WHERE series_id=? ORDER BY date", [sid]
            ).df()
            s["date"] = pd.to_datetime(s["date"])
            frames[label] = s.set_index("date")["value"]
    return pd.DataFrame(frames)


def bis_dsr_latest() -> pd.DataFrame:
    with connect() as con:
        return con.execute(
            """
            SELECT e.name, max_by(o.value, o.date) AS dsr
            FROM obs o JOIN entities e USING (entity)
            WHERE o.series_id='bis/dsr_households'
            GROUP BY 1 ORDER BY dsr DESC
            """
        ).df()


# ---------- figures ----------

def fig_who_owns_federal_debt() -> None:
    import matplotlib.pyplot as plt

    shares = federal_debt_holders()
    top = top_foreign_holders()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Who owns the US federal debt", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    ax1.stackplot(shares.index, [shares[c] for c in shares.columns],
                  labels=shares.columns, colors=PALETTE[:4], alpha=0.85)
    ax1.set_title("Holder shares of gross federal debt, %", fontsize=10, loc="left")
    ax1.legend(fontsize=8, loc="lower left")
    ax1.set_ylim(0, 100)

    ax2.barh(top.name.iloc[::-1], top.v.iloc[::-1] / 1e9, color=PALETTE[0])
    ax2.set_title("Top foreign holders, \\$B (several are custodial centers)",
                  fontsize=10, loc="left")
    ax2.tick_params(axis="y", labelsize=8.5)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from FRED holder series + Treasury TIC slt_table5 (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "08_who_owns_federal_debt")


def fig_debt_service() -> None:
    import matplotlib.pyplot as plt

    hist = debt_service_history()
    bis = bis_dsr_latest()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("What households pay: the US in time, the world in cross-section",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    ax1.plot(hist.index, hist["total"], lw=2, color=PALETTE[0], label="total (15.7% peak in 2007)")
    ax1.plot(hist.index, hist["mortgage"], lw=1.6, color=PALETTE[1], label="mortgage")
    ax1.plot(hist.index, hist["consumer"], lw=1.6, color=PALETTE[2], label="consumer")
    ax1.set_title("US debt service, % of disposable income (Fed)", fontsize=10, loc="left")
    ax1.legend(fontsize=8.5)

    colors = ["#d1242f" if n == "United States" else "#1f6feb" for n in bis.name]
    ax2.barh(bis.name.iloc[::-1], bis.dsr.iloc[::-1], color=colors[::-1])
    ax2.set_title("Household DSR, latest (BIS common method)", fontsize=10, loc="left")
    ax2.tick_params(axis="y", labelsize=8)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from FRED TDSP/MDSP/CDSP + BIS WS_DSR (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "08_debt_service")


def fig_interest_by_income() -> None:
    b = group_burdens("inc", INCOME_GROUPS)
    fig, ax = new_fig(
        "Estimated interest paid per household, by income group",
        subtitle="Stocks (Fed DFA) x rates (mortgage 4.3% effective; consumer blend ~10.4%). The poor's debt is half consumer credit at card rates; the top's is cheap mortgage money.",
        ylabel="est. $ interest per household per year",
    )
    x = np.arange(len(b))
    ax.bar(x, b["int_mortgage_hh"], color=PALETTE[0], label="mortgage interest")
    ax.bar(x, b["int_consumer_hh"], bottom=b["int_mortgage_hh"], color=PALETTE[1],
           label="consumer interest")
    for i, (_, r) in enumerate(b.iterrows()):
        total = r["int_mortgage_hh"] + r["int_consumer_hh"]
        ax.text(i, total + 400, f"${total:,.0f}", ha="center", fontsize=9)
    ax.set_xticks(x, b.index)
    ax.legend()
    source_note(ax, "Source: computed from Fed DFA income-percentile detail + FRED rates (econlab warehouse)")
    save(fig, "08_interest_by_income")


def fig_burden_history() -> None:
    b = burden_history()
    labels = {"q1": "Bottom 20%", "q2": "20-40%", "q3": "40-60%",
              "q4": "60-80%", "q5": "Top 20%"}
    fig, ax = new_fig(
        "The interest burden through time: regressivity is post-2008",
        subtitle=(
            "Est. interest / mean income by bracket (time-varying rates). Flat across classes before 2008; "
            "cheap money then rescued the mortgage classes - the bottom quintile never got the discount."
        ),
        ylabel="est. interest, % of bracket mean income",
    )
    for i, (q, label) in enumerate(labels.items()):
        lw = 2.6 if q in ("q1", "q5") else 1.2
        color = "#d1242f" if q == "q1" else ("#1f6feb" if q == "q5" else "#57606a")
        alpha = 1.0 if q in ("q1", "q5") else 0.55
        ax.plot(b.index, b[q], lw=lw, color=color, alpha=alpha, label=label)
    ax.annotate("2010: income crash,\nsticky debt -> 18.1%", (2010, b.loc[2010, "q1"]),
                xytext=(2013.2, 16.5), fontsize=8.5, color="#d1242f",
                arrowprops=dict(arrowstyle="->", color="#d1242f", lw=1))
    gap = b.loc[2024, "q1"] - b.loc[2024, "q5"]
    ax.annotate(f"2024 gap: {gap:.1f}pp", (2024, (b.loc[2024, 'q1'] + b.loc[2024, 'q5']) / 2),
                xytext=(2016.5, 3.2), fontsize=8.5, color="#57606a",
                arrowprops=dict(arrowstyle="-[", color="#57606a", lw=1))
    ax.legend(fontsize=8.5, ncol=3)
    source_note(
        ax,
        "Source: computed from Fed DFA income detail, Census H-3, FRED rates (econlab warehouse)",
    )
    save(fig, "08_burden_history")


def fig_demographic_burdens() -> None:
    import matplotlib.pyplot as plt

    race = group_burdens("race", RACE_GROUPS)
    age = group_burdens("age", AGE_GROUPS)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The demographics of debt", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    x = np.arange(len(race))
    ax1.bar(x, race["mortgage_hh"] / 1e3, color=PALETTE[0], label="mortgage")
    ax1.bar(x, race["consumer_hh"] / 1e3, bottom=race["mortgage_hh"] / 1e3,
            color=PALETTE[1], label="consumer")
    for i, (_, r) in enumerate(race.iterrows()):
        ax1.text(i, (r["mortgage_hh"] + r["consumer_hh"]) / 1e3 + 3,
                 f"{r['consumer_share']:.0f}% consumer", ha="center", fontsize=8.5)
    ax1.set_xticks(x, race.index)
    ax1.set_title("Debt per household by race, $k — and its composition",
                  fontsize=10, loc="left")
    ax1.set_ylabel("$ thousands per household")
    ax1.legend(fontsize=9)

    x2 = np.arange(len(age))
    totals = age["int_mortgage_hh"] + age["int_consumer_hh"]
    ax2.bar(x2, totals, color=PALETTE[4])
    for i, v in enumerate(totals):
        ax2.text(i, v + 150, f"${v:,.0f}", ha="center", fontsize=9)
    ax2.set_xticks(x2, age.index)
    ax2.set_title("Est. interest per household per year, by age", fontsize=10, loc="left")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from Fed DFA race/age detail + FRED rates (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "08_demographic_burdens")


def main() -> None:
    fig_who_owns_federal_debt()
    fig_debt_service()
    fig_interest_by_income()
    fig_burden_history()
    fig_demographic_burdens()


if __name__ == "__main__":
    main()
