"""Chapter 7 — The Balance Sheets of Power.

Financial institutions (private banks, the central bank) and private wealth
(top shares, billionaires) measured through what can actually be measured:
balance sheets, credit aggregates, and ownership ledgers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

EQUITY_GROUPS = {
    "toppt1": "Top 0.1%", "remainingtop1": "99-99.9%",
    "next9": "90-99%", "next40": "50-90%", "bottom50": "Bottom 50%",
}


# ---------- data ----------

def credit_gdp_panel() -> pd.DataFrame:
    """Bank loans / GDP: 18-economy mean and USA, 1870-2020 (%)."""
    with connect() as con:
        df = con.execute(
            """
            SELECT l.entity, l.year, 100 * l.value / g.value AS pct
            FROM obs l JOIN obs g
              ON g.series_id='jst/gdp' AND g.entity=l.entity AND g.year=l.year
            WHERE l.series_id='jst/tloans'
            """
        ).df()
    mean = df.groupby("year")["pct"].mean().rename("mean18")
    usa = df[df.entity == "USA"].set_index("year")["pct"].rename("usa")
    return pd.concat([mean, usa], axis=1)


def fed_footprint() -> tuple[pd.Series, pd.Series]:
    """(Fed assets / GDP annual %, weekly remittances $B)."""
    with connect() as con:
        ratio = con.execute(
            """
            SELECT w.year AS yr, max(w.value) / avg(g.value) * 100 AS pct
            FROM obs w JOIN obs g
              ON g.series_id='fred/GDP' AND g.year=w.year AND g.entity='USA'
            WHERE w.series_id='fred/WALCL' GROUP BY 1 ORDER BY 1
            """
        ).df().set_index("yr")["pct"]
        rem = con.execute(
            "SELECT date, value/1e9 AS bn FROM obs WHERE series_id='fred/RESPPLLOPNWW' ORDER BY date"
        ).df().set_index("date")["bn"]
    rem.index = pd.to_datetime(rem.index)
    return ratio, rem


def equity_ownership() -> pd.DataFrame:
    """Share of US corporate equities & mutual funds held by each wealth group (%)."""
    with connect() as con:
        df = con.execute(
            """
            SELECT date, series_id, value FROM obs
            WHERE series_id LIKE 'dfa/nwd.corporate_equities%'
            ORDER BY date
            """
        ).df()
    df["grp"] = df.series_id.str.rsplit(".", n=1).str[-1].map(EQUITY_GROUPS)
    wide = df.pivot_table(index="date", columns="grp", values="value")
    shares = 100 * wide.div(wide.sum(axis=1), axis=0)
    shares.index = pd.to_datetime(shares.index)
    return shares.groupby(shares.index.year).mean()


def us_wealth_top_shares() -> pd.DataFrame:
    with connect() as con:
        df = con.execute(
            "SELECT year, series_id, value FROM obs WHERE entity='USA' AND series_id IN "
            "('wid/shwealj992.p99p100','wid/shwealj992.p99_9p100') ORDER BY year"
        ).df().pivot(index="year", columns="series_id", values="value")
    return df.rename(columns={
        "wid/shwealj992.p99p100": "top1", "wid/shwealj992.p99_9p100": "top01"
    })


def billionaire_stats() -> dict:
    with connect() as con:
        n, total, us_total = con.execute(
            "SELECT count(*), sum(worth_usd), "
            "sum(CASE WHEN country='United States' THEN worth_usd END) FROM billionaires"
        ).fetchone()
        top10 = con.execute(
            "SELECT name, worth_usd FROM billionaires ORDER BY rank LIMIT 10"
        ).df()
        bottom50 = con.execute(
            "SELECT max_by(value, date) FROM obs WHERE series_id='dfa/nw.net_worth.bottom50'"
        ).fetchone()[0]
        world_gdp = con.execute(
            "SELECT sum(value) FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
        ).fetchone()[0]
    return {"n": n, "total": total, "us_total": us_total, "top10": top10,
            "bottom50_us": bottom50, "world_gdp": world_gdp}


def finance_profit_share(years=(2012, 2018, 2024)) -> pd.Series:
    """Financial firms' share of top-500 filers' net income (%)."""
    fin = {"$JPM", "$BAC", "$WFC", "$C", "$GS", "$MS", "$SCHW", "$BLK", "$BK",
           "$STT", "$AXP", "$V", "$MA", "$COF", "$USB", "$PNC", "$TFC", "$MET",
           "$PRU", "$AIG", "$ALL", "$TRV", "$CB", "$PGR", "$BX", "$KKR", "$APO",
           "$SPGI", "$ICE", "$CME", "$MCO", "$BRK-A", "$BRK-B"}
    with connect() as con:
        ni = con.execute(
            "SELECT year, entity, value FROM obs WHERE series_id='edgar/net_income'"
        ).df()
    out = {}
    for y in years:
        s = ni[ni.year == y].nlargest(500, "value")
        out[y] = 100 * s[s.entity.isin(fin)].value.sum() / s.value.sum()
    return pd.Series(out)


def bank_concentration() -> dict:
    """Top-5 bank holding companies' assets vs all commercial banks."""
    top5 = ["$JPM", "$BAC", "$C", "$WFC", "$USB"]
    with connect() as con:
        assets = con.execute(
            f"""
            SELECT entity, max_by(value, date) AS v FROM obs
            WHERE series_id='edgar/assets_q' AND entity IN ({','.join("?"*5)})
            GROUP BY 1
            """, top5
        ).df()
        allbanks = con.execute(
            "SELECT max_by(value, date) FROM obs WHERE series_id='fred/TLAACBW027SBOG'"
        ).fetchone()[0]
    return {"top5_sum": float(assets.v.sum()), "all_banks": float(allbanks),
            "detail": dict(zip(assets.entity, assets.v))}


# ===== Part I: the evolution of the forms =====

# Curated: US commercial-bank counts before FRED's USNUM starts (1984).
# FDIC Historical Statistics on Banking + Historical Statistics of the US.
# American banking was uniquely fragmented — anti-branch-banking laws bred tens
# of thousands of tiny unit banks, peaking ~1921, culled by the Depression.
BANK_COUNT_ANCHORS = {1900: 12427, 1910: 24514, 1921: 30456, 1929: 24633,
                      1933: 14207, 1950: 14676, 1970: 13511, 1980: 14435}


def bank_count() -> pd.DataFrame:
    """US commercial banks over time: curated anchors (pre-1984) + FRED USNUM."""
    with connect() as con:
        usnum = con.execute(
            "SELECT year, round(avg(value)) v FROM obs WHERE series_id='fred/USNUM' GROUP BY 1"
        ).df().set_index("year")["v"]
        current = con.execute(
            "SELECT max_by(value, date) FROM obs WHERE series_id='fred/QBPBSNUMINST'"
        ).fetchone()[0]
    anchors = pd.Series(BANK_COUNT_ANCHORS)
    return {"anchors": anchors, "usnum": usnum, "current": float(current)}


def bank_failures() -> pd.Series:
    with connect() as con:
        return con.execute(
            "SELECT year, value FROM obs WHERE series_id='fred/BKFTTLA641N' ORDER BY year"
        ).df().set_index("year")["value"]


SHIFT = {
    "Banks (depository)": "fred/BOGZ1FL764090005A",
    "Pension funds": "fred/BOGZ1FL594090005A",
    "Mutual funds": "fred/BOGZ1FL654090000A",
    "Money-market funds": "fred/MMMFFAA027N",
}


def the_great_shift() -> pd.DataFrame:
    """Financial-institution assets as % of GDP, 1945-> (banks vs the rest)."""
    with connect() as con:
        gdp = con.execute(
            "SELECT year, avg(value) g FROM obs WHERE series_id='fred/GDP' GROUP BY 1"
        ).df().set_index("year")["g"]
        cols = {}
        for label, sid in SHIFT.items():
            s = con.execute(
                "SELECT year, avg(value) v FROM obs WHERE series_id=? GROUP BY 1", [sid]
            ).df().set_index("year")["v"]
            cols[label] = 100 * s / gdp
    return pd.DataFrame(cols).dropna(how="all")


# Curated: the spread of central banking (BIS + central-bank histories). Count
# of countries with a central bank at each date, plus marquee foundings.
CB_COUNT = {1668: 1, 1700: 2, 1800: 3, 1850: 8, 1900: 18, 1935: 32, 1950: 59, 1970: 110, 2000: 174, 2024: 182}
CB_FOUNDINGS = {"Sweden (Riksbank)": 1668, "England (BoE)": 1694, "France": 1800,
                "Germany (Reichsbank)": 1876, "Japan": 1882, "USA (Federal Reserve)": 1913,
                "China (PBoC)": 1948, "Euro area (ECB)": 1998}

# Curated: the non-bank giants (2024 AUM, $tn — company reports / HFR / Preqin)
NEW_TITANS = {"BlackRock": 11.5, "Vanguard": 9.3, "Fidelity": 5.3, "State Street": 4.3,
              "hedge funds (industry)": 4.5, "private equity (industry)": 5.8}
HEDGE_FUND_AUM = {1990: 0.039, 1997: 0.12, 2000: 0.49, 2004: 1.0, 2008: 1.4,
                  2012: 2.3, 2016: 3.0, 2020: 3.6, 2024: 4.5}  # $tn, HFR

# Curated: the milestones that reshaped institutional form (US-centric)
FINANCE_MILESTONES = [
    (1933, "Glass-Steagall", "splits commercial from investment banking"),
    (1975, "May Day", "brokerage commissions deregulated → discount brokers"),
    (1994, "Riegle-Neal", "interstate branching → the merger wave"),
    (1999, "Gramm-Leach-Bliley", "repeals Glass-Steagall → universal 'umbrella' banks"),
    (2008, "The extinction", "Bear/Lehman/Merrill gone; Goldman & Morgan → bank holding cos"),
]


# ---------- figures ----------

def fig_hockey_stick() -> None:
    p = credit_gdp_panel()
    fig, ax = new_fig(
        "The financial hockey stick, 1870-2020",
        subtitle="Bank loans to the private sector / GDP. Flat for a century, then finance outgrew the economy it serves - double the 1913 peak.",
        ylabel="% of GDP",
    )
    ax.plot(p.index, p.mean18, lw=2.2, color=PALETTE[0], label="mean, 18 economies")
    ax.plot(p.index, p.usa, lw=1.4, color=PALETTE[1], alpha=0.8, label="United States")
    for y, txt in [(1913, "1913: 58%"), (1950, "1950: 35%"), (2007, "2007: 111%")]:
        ax.annotate(txt, (y, p.mean18.loc[y]), xytext=(0, 10),
                    textcoords="offset points", fontsize=8.5, ha="center", color="#57606a")
    ax.legend()
    source_note(ax, "Source: computed from JST Macrohistory loans & GDP (econlab warehouse)")
    save(fig, "06_hockey_stick")


def fig_state_balance() -> None:
    import matplotlib.pyplot as plt

    ratio, rem = fed_footprint()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The central bank's new size - and its new losses", x=0.01,
                 ha="left", fontweight="bold", fontsize=13)

    ax1.plot(ratio.index, ratio.values, lw=2, color=PALETTE[0])
    for y, label in [(2008, "QE1"), (2020, "COVID QE")]:
        ax1.axvline(y, color="#57606a", lw=0.7, ls=":")
        ax1.text(y, ax1.get_ylim()[1] * 0.05 + 30, label, rotation=90, fontsize=8, color="#57606a")
    ax1.set_title("Fed assets / GDP, % (6% in 2007 -> 34% peak -> 21%)", fontsize=10, loc="left")

    ax2.plot(rem.index, rem.values, lw=1.5, color=PALETTE[1])
    ax2.axhline(0, color="#57606a", lw=0.8)
    ax2.set_title("Earnings remittances due to Treasury, $B\n(negative = accumulated losses since Sep 2022)",
                  fontsize=10, loc="left")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: computed from FRED WALCL, GDP, RESPPLLOPNWW (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "06_state_balance")


def fig_who_owns_market() -> None:
    sh = equity_ownership()
    fig, ax = new_fig(
        "Who owns the US stock market",
        subtitle="Share of corporate equities & mutual-fund shares by household wealth group. The top 10% hold ~87%; the bottom half ~1%.",
        ylabel="% of household equity holdings",
    )
    for i, grp in enumerate(EQUITY_GROUPS.values()):
        last = sh[grp].dropna().iloc[-1]
        ax.plot(sh.index, sh[grp], lw=2, color=PALETTE[i], label=f"{grp} ({last:.0f}%)")
    ax.legend(fontsize=9, ncol=2)
    source_note(ax, "Source: computed from Fed DFA asset-composition detail (econlab warehouse)")
    save(fig, "06_who_owns_market")


def fig_private_summits() -> None:
    import matplotlib.pyplot as plt

    tw = us_wealth_top_shares()
    b = billionaire_stats()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Private wealth at the summit", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    ax1.plot(tw.index, 100 * tw.top1, lw=2, color=PALETTE[0], label="top 1%")
    ax1.plot(tw.index, 100 * tw.top01, lw=2, color=PALETTE[1], label="top 0.1%")
    ax1.set_title("US wealth shares, 1850-2024 (WID)", fontsize=10, loc="left")
    ax1.set_ylabel("% of household wealth")
    ax1.set_xlim(1850, 2030)
    ax1.legend(fontsize=9)

    top10 = b["top10"].iloc[::-1]
    ax2.barh(top10.name, top10.worth_usd / 1e9, color=PALETTE[4])
    for i, (nm, w) in enumerate(zip(top10.name, top10.worth_usd)):
        ax2.text(w / 1e9 + 8, i, f"{w/1e9:.0f}", va="center", fontsize=8)
    ax2.set_title(
        f"Ten people = \\${b['top10'].worth_usd.sum()/1e12:.1f}T "
        f"(US bottom-50%: \\${b['bottom50_us']/1e12:.1f}T)", fontsize=10, loc="left")
    ax2.set_xlabel("net worth, $B (Forbes estimate)")
    ax2.tick_params(axis="y", labelsize=8)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02,
             "Source: computed from WID.world, Forbes snapshot (unofficial), Fed DFA (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "06_private_summits")


def fig_concentration_of_power() -> None:
    """Two faces of concentrated financial power: banking assets and profits."""
    import matplotlib.pyplot as plt

    bc = bank_concentration()
    fps = finance_profit_share((2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024))
    top5_share = 100 * bc["top5_sum"] / bc["all_banks"]
    print(f"[ch06] top-5 banks = {top5_share:.0f}% of US bank assets; finance profit share ~{fps.mean():.0f}%")

    names = {"$JPM": "JPMorgan", "$BAC": "Bank of America", "$C": "Citi",
             "$WFC": "Wells Fargo", "$USB": "US Bancorp"}
    detail = sorted(bc["detail"].items(), key=lambda kv: -kv[1])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The concentration of financial power", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    # left: the big five vs everyone else, as a single stacked bar
    bottom = 0.0
    for i, (tk, v) in enumerate(detail):
        ax1.bar(0, v / 1e12, bottom=bottom / 1e12, color=PALETTE[i % len(PALETTE)],
                width=0.6, label=f"{names.get(tk, tk)} (${v/1e12:.1f}T)")
        bottom += v
    rest = bc["all_banks"] - bc["top5_sum"]
    ax1.bar(0, rest / 1e12, bottom=bottom / 1e12, color="#d0d7de", width=0.6,
            label=f"all other banks (${rest/1e12:.1f}T)")
    ax1.set_title(f"Top 5 banks = {top5_share:.0f}% of all US bank assets", fontsize=10, loc="left")
    ax1.set_ylabel("US commercial bank assets, $ trillions")
    ax1.set_xticks([])
    ax1.set_xlim(-0.6, 1.4)
    ax1.legend(fontsize=8, loc="center right")

    # right: finance's share of the largest firms' profits
    ax2.plot(fps.index, fps.values, lw=2, marker="o", ms=5, color=PALETTE[3])
    ax2.axhline(fps.mean(), color="#57606a", lw=0.8, ls="--")
    ax2.set_title(f"Finance = ~{fps.mean():.0f}% of the top-500 firms' profits", fontsize=10, loc="left")
    ax2.set_ylabel("% of top-500 net income")
    ax2.set_ylim(0, max(fps) * 1.25)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: computed from EDGAR bank balance sheets & net income + FRED all-bank assets (econlab warehouse)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "06_concentration_of_power")


def fig_bank_consolidation() -> None:
    """From 30,000 unit banks to 4,000: the great American bank consolidation."""
    import matplotlib.pyplot as plt

    bc = bank_count()
    fails = bank_failures()
    print(f"[ch06] banks: peak {bc['anchors'].max():.0f} (1921) -> {bc['current']:.0f} today")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.4, 1]})
    fig.suptitle("The great bank consolidation: 30,000 banks became 4,000", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    a = bc["anchors"]
    ax1.plot(a.index, a / 1000, "o--", color="#57606a", lw=1.3, ms=5, alpha=0.8, label="curated (FDIC/HSUS)")
    u = bc["usnum"]
    ax1.plot(u.index, u / 1000, lw=2.4, color="#1f6feb", label="FRED USNUM (1984–2020)")
    ax1.plot([2024], [bc["current"] / 1000], "o", color="#1f6feb", ms=6)
    ax1.annotate("1921 peak:\n~30,000 unit banks", (1921, 30.5), xytext=(1928, 27),
                 fontsize=8.5, color="#d1242f", arrowprops=dict(arrowstyle="->", color="#d1242f"))
    ax1.annotate("Depression\ncull", (1933, 14.2), xytext=(1938, 6), fontsize=8, color="#57606a",
                 arrowprops=dict(arrowstyle="->", color="#57606a"))
    ax1.annotate("post-1994 merger wave\n(interstate branching)", (2005, 7.5), xytext=(1968, 2),
                 fontsize=8.5, color="#1f6feb", arrowprops=dict(arrowstyle="->", color="#1f6feb"))
    ax1.set_title("Number of US commercial banks (thousands)", fontsize=10, loc="left")
    ax1.set_ylabel("thousands of banks")
    ax1.set_ylim(0, 33)
    ax1.legend(fontsize=8, loc="upper right")

    ax2.bar(fails.index, fails.values, width=1.0, color="#d1242f", alpha=0.8)
    ax2.set_title("Bank failures per year (FDIC, 1934→)", fontsize=10, loc="left")
    ax2.set_ylabel("insured institutions failed")
    for yr, lbl in [(1989, "S&L\ncrisis"), (2010, "GFC")]:
        ax2.annotate(lbl, (yr, fails.get(yr, 0)), xytext=(0, 6), textcoords="offset points",
                     ha="center", fontsize=8, color="#d1242f")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: FRED USNUM/QBPBSNUMINST/BKFTTLA641N + curated FDIC/Historical-Statistics anchors (econlab warehouse)",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "06_bank_consolidation")


def fig_great_shift() -> None:
    """The shift from banks to non-bank finance: assets as % of GDP, 1945->."""
    sh = the_great_shift()
    print("[ch06] great shift 1950->2024 (% GDP):",
          {c: (round(sh[c].dropna().iloc[0]), round(sh[c].dropna().iloc[-1])) for c in sh.columns})
    fig, ax = new_fig(
        "The great shift: from banks to funds",
        subtitle="US financial-institution assets as % of GDP (Fed Flow of Funds). In 1950 banks were finance; since then "
        "pensions and mutual funds — the asset-management complex — grew from nothing to rival them.",
        ylabel="total assets, % of GDP",
    )
    colors = {"Banks (depository)": "#1f6feb", "Pension funds": "#1a7f37",
              "Mutual funds": "#d1242f", "Money-market funds": "#9a6700"}
    for label, c in colors.items():
        s = sh[label].dropna()
        ax.plot(s.index, s, lw=2.2, color=c, label=f"{label} ({s.iloc[-1]:.0f}%)")
    ax.legend(fontsize=9, loc="upper left")
    mf = sh["Mutual funds"].dropna()
    ax.annotate(f"mutual funds: 1% (1950) → {mf.iloc[-1]:.0f}% — now rivaling banks",
                (mf.index[-1], mf.iloc[-1]), xytext=(1966, 60), fontsize=8.5, color="#d1242f",
                arrowprops=dict(arrowstyle="->", color="#d1242f"))
    source_note(ax, "Source: computed from Fed Flow of Funds asset levels ÷ GDP (econlab warehouse)")
    save(fig, "06_great_shift")


def fig_central_bank_diffusion() -> None:
    """The spread of central banking, 1668 -> today."""
    yrs = sorted(CB_COUNT)
    counts = [CB_COUNT[y] for y in yrs]
    fig, ax = new_fig(
        "The spread of central banking, 1668 → today",
        subtitle="Number of countries with a central bank (curated, BIS + central-bank histories). One institution in 1668; "
        "three by 1800; the 20th century made it universal — every modern state now issues and manages its own money.",
        ylabel="countries with a central bank",
    )
    ax.plot(yrs, counts, "o-", lw=2.2, color="#8250df", ms=5)
    for name, yr in CB_FOUNDINGS.items():
        ax.axvline(yr, color="#57606a", lw=0.6, ls=":", alpha=0.6)
        ax.annotate(f"{name} {yr}", (yr, 3), rotation=90, fontsize=7.5, color="#57606a",
                    va="bottom", ha="right")
    ax.set_xlim(1650, 2040)
    source_note(ax, "Source: curated founding dates + count anchors (BIS, central-bank histories) (econlab warehouse)")
    save(fig, "06_central_bank_diffusion")


def fig_new_titans() -> None:
    """The non-bank giants and the milestones that made them."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.15]})
    fig.suptitle("The new titans: the asset-management era", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    titans = pd.Series(NEW_TITANS).sort_values()
    colors = ["#8250df" if "industry" in n else "#1f6feb" for n in titans.index]
    ax1.barh(range(len(titans)), titans.values, color=colors)
    ax1.set_yticks(range(len(titans)), titans.index, fontsize=8.5)
    ax1.set_title("Assets under management, 2024 (\\$tn)", fontsize=10, loc="left")
    ax1.set_xlabel("\\$ trillions")
    for i, v in enumerate(titans.values):
        ax1.text(v + 0.1, i, f"{v:.1f}", va="center", fontsize=8)

    hf = pd.Series(HEDGE_FUND_AUM)
    ax2.plot(hf.index, hf.values, "o-", lw=2.2, color="#d1242f", ms=4)
    ax2.set_title("Hedge-fund industry AUM (\\$tn): \\$39bn → \\$4.5tn", fontsize=10, loc="left")
    ax2.set_ylabel("\\$ trillions")
    for yr, name, _ in FINANCE_MILESTONES:
        if yr >= 1990:
            ax2.axvline(yr, color="#57606a", lw=0.7, ls=":")
            ax2.annotate(name, (yr, 4.3), rotation=90, fontsize=7.5, color="#57606a", va="top", ha="right")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.25)
    fig.text(0.01, -0.02, "Source: curated AUM (company reports, HFR, Preqin) + institutional milestones (econlab warehouse)",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "06_new_titans")


def main() -> None:
    fig_hockey_stick()
    fig_central_bank_diffusion()
    fig_bank_consolidation()
    fig_great_shift()
    fig_new_titans()
    fig_state_balance()
    fig_concentration_of_power()
    fig_who_owns_market()
    fig_private_summits()
    print("[ch07] finance share of top-500 net income:", finance_profit_share().round(1).to_dict())
    bc = bank_concentration()
    print("[ch07] top5 bank assets: $%.1fT of $%.1fT all-bank (%.0f%%)" % (
        bc["top5_sum"] / 1e12, bc["all_banks"] / 1e12, 100 * bc["top5_sum"] / bc["all_banks"]))
    b = billionaire_stats()
    print("[ch07] billionaires: n=%d, total $%.1fT (%.0f%% of world GDP), US $%.1fT" % (
        b["n"], b["total"] / 1e12, 100 * b["total"] / b["world_gdp"], b["us_total"] / 1e12))


if __name__ == "__main__":
    main()
