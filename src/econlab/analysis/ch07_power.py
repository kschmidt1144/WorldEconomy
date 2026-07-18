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
    save(fig, "07_hockey_stick")


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
    save(fig, "07_state_balance")


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
    save(fig, "07_who_owns_market")


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
    save(fig, "07_private_summits")


def main() -> None:
    fig_hockey_stick()
    fig_state_balance()
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
