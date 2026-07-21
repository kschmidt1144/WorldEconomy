"""Chapter 4 — The Debt Ledger: who owes, who owns, who pays.

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


# Curated: episodes of external sovereign default / restructuring since 1800,
# from Reinhart & Rogoff, "This Time Is Different" (2009) + Reinhart-Rogoff-
# Trebesch sovereign-defaults database. Counts vary by source/definition (±1-2);
# the *pattern* — a serial-defaulter club and a never-defaulted club — is robust.
SOVEREIGN_DEFAULTS = {
    "Spain": 13, "Venezuela": 11, "Ecuador": 10, "Brazil": 9, "Costa Rica": 9,
    "Chile": 9, "Argentina": 8, "Mexico": 8, "Uruguay": 8, "Peru": 8,
    "Germany": 8, "Turkey": 7, "Austria": 7, "Colombia": 7, "Greece": 6,
    "Portugal": 6, "Russia": 5,
}
NEVER_DEFAULTED = ["United States", "England/UK", "Canada", "Australia",
                   "New Zealand", "Norway", "Denmark", "Belgium", "Finland",
                   "Switzerland", "Singapore", "Hong Kong", "Malaysia", "Thailand"]


def sovereign_default_ledger() -> pd.Series:
    """External sovereign default/restructuring episodes since 1800 (curated)."""
    return pd.Series(SOVEREIGN_DEFAULTS).sort_values(ascending=False)


def crisis_clock() -> pd.DataFrame:
    """Average % of the 18 JST economies in a systemic banking crisis, by decade."""
    with connect() as con:
        df = con.execute(
            "SELECT (year - year % 10) AS decade, avg(annual_share) AS crisis_country_yrs FROM ("
            "  SELECT year, 100.0*sum(value)/count(DISTINCT entity) AS annual_share"
            "  FROM obs WHERE series_id='jst/crisisJST' GROUP BY year"
            ") GROUP BY 1 ORDER BY 1"
        ).df()
    return df.set_index("decade")


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

# Jurisdictions whose Treasury holdings are custody/booking, not the local
# public — and what the "position" actually is.
CUSTODY_CENTERS = {
    "GBR": "London custody", "BEL": "Euroclear (int'l depository)",
    "CYM": "hedge-fund / SPV domicile", "LUX": "fund domicile",
    "IRL": "fund domicile (ETFs)", "CHE": "private banking",
}
_HOLDER_NAMES = {
    "JPN": "Japan", "GBR": "United Kingdom", "CHN": "China", "BEL": "Belgium",
    "CYM": "Cayman Is.", "CAN": "Canada", "LUX": "Luxembourg", "FRA": "France",
    "IRL": "Ireland", "TWN": "Taiwan", "CHE": "Switzerland", "SGP": "Singapore",
}


def who_finances_america() -> dict:
    """Foreign holders of US Treasuries and the custody bloc whose beneficial
    owners are unreadable — roughly a third of 'foreign demand'."""
    with connect() as con:
        df = con.execute(
            "SELECT entity, max_by(value, date) / 1e9 AS bn FROM obs "
            "WHERE series_id='tic/us_treasury_holdings' GROUP BY 1").df()
        usd_reserve = _latest(con, "cofer/reserve_share.USD")
    foreign = float(df.loc[df.entity == "WLD", "bn"].iloc[0])
    df = df[df.entity != "WLD"].sort_values("bn", ascending=False).reset_index(drop=True)
    bloc = df[df.entity.isin(CUSTODY_CENTERS)]
    bloc_total = float(bloc["bn"].sum())
    china = float(df.loc[df.entity == "CHN", "bn"].iloc[0])
    return {"top": df, "foreign": foreign, "bloc_total": bloc_total,
            "bloc_share": 100 * bloc_total / foreign, "china": china,
            "china_share": 100 * china / foreign, "usd_reserve": usd_reserve}


def fig_who_finances_america() -> None:
    """Who really holds US Treasuries — and the custody veil over a third of it."""
    import matplotlib.pyplot as plt

    r = who_finances_america()
    print(f"[ch05] custody bloc ${r['bloc_total']:,.0f}B = {r['bloc_share']:.1f}% of "
          f"${r['foreign']:,.0f}B foreign; China ${r['china']:,.0f}B ({r['china_share']:.1f}%)")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.4), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.suptitle("A third of “foreign demand” for US Treasuries hides behind six custodians",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    top = r["top"].head(12).iloc[::-1]
    colors = ["#9a6700" if e in CUSTODY_CENTERS else "#3b6fb0" for e in top["entity"]]
    ax1.barh(range(len(top)), top["bn"], color=colors)
    ax1.set_yticks(range(len(top)), [_HOLDER_NAMES.get(e, e) for e in top["entity"]], fontsize=8.5)
    for i, bn in enumerate(top["bn"]):
        ax1.text(bn + 10, i, f"${bn:,.0f}B", va="center", fontsize=8)
    ax1.set_title("Top foreign holders — custodians (gold) rival real economies (blue)", fontsize=9.5, loc="left")
    ax1.set_xlabel("US Treasuries held, $ billions")
    ax1.set_xlim(0, top["bn"].max() * 1.16)
    ax1.barh([], []); ax1.scatter([], [], color="#9a6700", marker="s", label="custody / financial center")
    ax1.scatter([], [], color="#3b6fb0", marker="s", label="real economy")
    ax1.legend(fontsize=8, loc="lower right")

    b = r["top"][r["top"]["entity"].isin(CUSTODY_CENTERS)].sort_values("bn")
    ax2.barh(range(len(b)), b["bn"], color="#9a6700")
    ax2.set_yticks(range(len(b)),
                   [f"{_HOLDER_NAMES.get(e, e)} — {CUSTODY_CENTERS[e]}" for e in b["entity"]], fontsize=8)
    for i, bn in enumerate(b["bn"]):
        ax2.text(bn - 10, i, f"${bn:,.0f}B", va="center", ha="right", fontsize=8, color="white", fontweight="bold")
    ax2.set_title(f"The custody bloc: ${r['bloc_total']:,.0f}B = {r['bloc_share']:.0f}% of all foreign holdings",
                  fontsize=9.5, loc="left")
    ax2.set_xlabel("US Treasuries held, $ billions")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="x")
    fig.text(0.01, -0.02, "Source: US Treasury TIC (slt_table5, latest month) via econlab; custody labels curated. Belgium ≈ "
             "Euroclear; Cayman/Luxembourg/Ireland ≈ fund domiciles — the beneficial owners are not in the data.",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "05_who_finances_america")


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
    save(fig, "05_who_owns_federal_debt")


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
    save(fig, "05_debt_service")


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
    save(fig, "05_interest_by_income")


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
    save(fig, "05_burden_history")


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
    save(fig, "05_demographic_burdens")


def fig_sovereign_defaults() -> None:
    """The sovereign side of the ledger: who defaults, and who never has."""
    import matplotlib.pyplot as plt

    led = sovereign_default_ledger()
    clock = crisis_clock()
    print("[ch04] serial defaulter champion:", led.index[0], int(led.iloc[0]),
          "| never-defaulted club:", len(NEVER_DEFAULTED))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2))
    fig.suptitle("The sovereign ledger: default is a choice some make often, others never",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # left: serial defaulters
    top = led.head(14)[::-1]
    colors = ["#d1242f" if v >= 8 else "#9a6700" for v in top.values]
    ax1.barh(range(len(top)), top.values, color=colors)
    ax1.set_yticks(range(len(top)), top.index, fontsize=8.5)
    ax1.set_title("External sovereign defaults since 1800 (curated)", fontsize=10, loc="left")
    ax1.set_xlabel("number of default / restructuring episodes")
    for i, v in enumerate(top.values):
        ax1.text(v + 0.1, i, str(int(v)), va="center", fontsize=8)

    # right: the banking-crisis clock (computed)
    ax2.bar(clock.index, clock["crisis_country_yrs"], width=8, color="#1f6feb", alpha=0.8)
    ax2.set_title("Banking crises: % of 18 economies in crisis, by decade (JST)", fontsize=10, loc="left")
    ax2.set_xlabel("decade")
    ax2.set_ylabel("% of economies in systemic crisis")
    for dec, lbl in [(1930, "1930s"), (2000, "2000s")]:
        if dec in clock.index:
            ax2.annotate(lbl, (dec, clock.loc[dec, "crisis_country_yrs"]),
                         xytext=(0, 5), textcoords="offset points", ha="center", fontsize=8, color="#d1242f")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, 0.005, "Never defaulted on external sovereign debt: " + ", ".join(NEVER_DEFAULTED),
             fontsize=8, color="#1f6feb", ha="left", va="bottom",
             bbox=dict(boxstyle="round", fc="#eef6ff", ec="#1f6feb", alpha=0.9))
    fig.text(0.01, -0.05, "Source: default counts curated from Reinhart-Rogoff (2009) 'This Time Is Different'; "
             "crisis clock computed from JST crisis flags (econlab warehouse)", fontsize=7.5, color="#57606a")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "05_sovereign_defaults")


# computed BoC-BoE companion to the curated R&R ledger. Verified absent from the
# post-1960 default database (never-defaulted) with their 2024 gross debt/GDP.
_NEVER_DEFAULT = ["JPN", "SGP", "USA", "CAN", "NOR", "AUS", "NLD", "CHE", "SWE"]
_SERIAL_DEFAULT = ["PAK", "TUR", "ARG", "ZAF", "MEX", "NGA", "GRC", "EGY", "UKR", "BRA", "ECU"]


def largest_defaults(n: int = 12) -> pd.DataFrame:
    """Biggest sovereign defaults 1960-2023 by peak defaulted-debt stock ($bn)."""
    with connect() as con:
        df = con.execute(
            "SELECT country, \"group\", n_episodes, peak_stock_musd/1e3 peak_bn, peak_year "
            "FROM sovereign_defaults ORDER BY peak_stock_musd DESC LIMIT ?", [n]
        ).df()
    df["advanced"] = df["group"] == "Advanced economies"
    return df


def default_debt_scatter() -> pd.DataFrame:
    """Debt-intolerance test: gross debt/GDP (2024) vs number of default episodes
    since 1960. Never-defaulters (episodes=0) vs serial defaulters."""
    ents = _NEVER_DEFAULT + _SERIAL_DEFAULT
    with connect() as con:
        dg = con.execute(
            "SELECT entity, value debt_gdp FROM obs WHERE series_id='imf/GGXWDG_NGDP' "
            f"AND year=2024 AND entity IN ({','.join(repr(e) for e in ents)})"
        ).df().set_index("entity")["debt_gdp"]
        ep = con.execute("SELECT entity, n_episodes FROM sovereign_defaults "
                         "WHERE entity IS NOT NULL").df().set_index("entity")["n_episodes"]
    rows = []
    for e in ents:
        if e in dg.index:
            rows.append({"entity": e, "debt_gdp": float(dg[e]),
                         "episodes": int(ep.get(e, 0)), "never": e in _NEVER_DEFAULT})
    return pd.DataFrame(rows)


def fig_defaults_computed() -> None:
    """Upgrade the curated R&R ledger to a computed dataset: the modern default
    record in dollars, and the debt-intolerance test that institutions > debt levels."""
    import matplotlib.pyplot as plt

    big = largest_defaults(12)
    sc = default_debt_scatter()
    nd = sc[sc.never]
    sd = sc[~sc.never]
    print(f"[ch05] computed defaults: biggest {big.iloc[0]['country']} ${big.iloc[0]['peak_bn']:.0f}B; "
          f"never-defaulters avg debt {nd.debt_gdp.mean():.0f}% vs serial {sd.debt_gdp.mean():.0f}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.4))
    fig.suptitle("The sovereign ledger, computed: default is about institutions, not debt levels",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    b = big.iloc[::-1]
    cols = ["#1f6feb" if a else "#d1242f" for a in b["advanced"]]
    ax1.barh(range(len(b)), b["peak_bn"], color=cols)
    ax1.set_yticks(range(len(b)), [c.replace("USSR/Russia", "USSR/Rus.") for c in b["country"]], fontsize=8.5)
    for i, v in enumerate(b["peak_bn"]):
        ax1.text(v + 4, i, f"${v:.0f}B", va="center", fontsize=7.5)
    ax1.set_xlim(0, big["peak_bn"].max() * 1.16)
    ax1.set_title("Biggest defaults 1960–2023 — peak debt in default", fontsize=9.5, loc="left")
    ax1.set_xlabel("peak defaulted-debt stock, $ billions")
    ax1.scatter([], [], color="#1f6feb", marker="s", label="Advanced economy")
    ax1.scatter([], [], color="#d1242f", marker="s", label="Emerging / other")
    ax1.legend(fontsize=7.5, loc="lower right")

    ax2.scatter(nd["debt_gdp"], nd["episodes"], s=55, color="#1a7f37", zorder=3,
                label="Never defaulted since 1960")
    ax2.scatter(sd["debt_gdp"], sd["episodes"], s=55, color="#d1242f", zorder=3,
                label="Serial defaulter")
    _LAB = {"JPN": "Japan", "USA": "US", "CAN": "Canada", "SGP": "Singapore",
            "TUR": "Turkey", "PAK": "Pakistan", "ARG": "Argentina", "GRC": "Greece",
            "ECU": "Ecuador", "NGA": "Nigeria"}
    for _, r in sc.iterrows():
        if r["entity"] in _LAB:
            ax2.annotate(_LAB[r["entity"]], (r["debt_gdp"], r["episodes"]),
                         xytext=(4, 3), textcoords="offset points", fontsize=7.3,
                         color="#1a7f37" if r["never"] else "#d1242f")
    ax2.set_xlabel("gross government debt, % of GDP (2024)")
    ax2.set_ylabel("default episodes since 1960")
    ax2.set_title(f"No relationship: never-defaulters carry MORE debt ({nd.debt_gdp.mean():.0f}% avg) "
                  f"yet never fail", fontsize=8.6, loc="left")
    ax2.set_ylim(-0.6, sd["episodes"].max() + 1)
    ax2.legend(fontsize=7.5, loc="upper right")
    ax2.annotate("Japan: 215% debt,\nnever defaults", xy=(215, 0), xytext=(150, 2.2),
                 fontsize=7.3, color="#1a7f37", ha="center",
                 arrowprops=dict(arrowstyle="->", color="#1a7f37", lw=0.8))
    ax2.annotate("Turkey defaults\nat 24%", xy=(24, 7), xytext=(60, 7.6),
                 fontsize=7.3, color="#d1242f", ha="center",
                 arrowprops=dict(arrowstyle="->", color="#d1242f", lw=0.8))

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    ax1.grid(alpha=0.25, axis="x")
    ax2.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: computed from the Bank of Canada–Bank of England sovereign-default database (defaulted-debt stock, "
             "1960–2023) + IMF gross government debt/GDP (econlab). Pre-1960 defaults (e.g. Spain's) are outside the panel.",
             fontsize=7.2, color="#57606a")
    fig.tight_layout()
    save(fig, "05_defaults_computed")


def main() -> None:
    fig_who_owns_federal_debt()
    fig_who_finances_america()
    fig_sovereign_defaults()
    fig_defaults_computed()
    fig_debt_service()
    fig_interest_by_income()
    fig_burden_history()
    fig_demographic_burdens()


if __name__ == "__main__":
    main()
