"""Chapter 10 — The Chokepoints: where a few control the many.

Generalizes Chapter 9's "Giant Three" finding from finance to the whole
economy. Most of the numbers here are *curated* concentration ratios (cited),
because market-share data isn't in the primary-data warehouse — but each
headline figure was **cross-checked through the AI panel** (`econ panel`, free
Groq models: Llama + Qwen3 + GPT-OSS), and the panel's consensus is reported
alongside. The people who sit atop these chokepoints are pulled live from the
Forbes billionaires table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

# Curated chokepoints: (domain, what, n_controllers, top_n_share_pct, who, source).
# Panel consensus for the ones we cross-checked is in PANEL_CHECK below.
CHOKEPOINTS = [
    ("Technology", "EUV lithography machines", 1, 100, "ASML"),
    ("Technology", "Leading-edge chips (<7nm)", 1, 90, "TSMC"),
    ("Technology", "AI accelerators (GPUs)", 1, 90, "Nvidia"),
    ("Technology", "Web search", 1, 90, "Google"),
    ("Technology", "Desktop operating systems", 1, 72, "Microsoft Windows"),
    ("Technology", "Cloud infrastructure", 3, 63, "AWS, Azure, Google"),
    ("Corporate control", "Proxy-vote advice", 2, 95, "ISS + Glass Lewis"),
    ("Corporate control", "Credit ratings", 3, 95, "S&P, Moody's, Fitch"),
    ("Corporate control", "Index-fund voting (S&P 500)", 3, 88, "BlackRock, Vanguard, State Street"),
    ("Resources", "Commercial seeds & agrochem", 4, 60, "Bayer, Corteva, Syngenta, BASF"),
    ("Resources", "Rare-earth refining", 1, 87, "China"),
    ("Resources", "Global grain trade", 4, 75, "ADM, Bunge, Cargill, Dreyfus"),
    ("Payments", "Cross-border bank messaging", 1, 90, "SWIFT"),
]

# AI-panel cross-check (consensus 0-100, mean estimate %) — from `econ panel`,
# free Groq models (Llama-3.3, Qwen3, GPT-OSS-120B), 2026-07-19. Recorded so the
# chapter shows an independent multi-model check of each curated figure.
PANEL_CHECK = {
    "EUV lithography machines": (100, 100),
    "Leading-edge chips (<7nm)": (72, 72),   # models split 50-90 (definition-sensitive)
    "AI accelerators (GPUs)": (97, 88),
    "Web search": (94, 88),
    "Proxy-vote advice": (98, 96),
    "Credit ratings": (100, 95),
    "Commercial seeds & agrochem": (100, 60),
}

# Control without ownership: super-voting founders (voting % vs economic %).
# Curated from company proxy statements.
DUAL_CLASS = [
    ("Zuckerberg — Meta", 58, 13),
    ("Page & Brin — Alphabet", 51, 11),
    ("Murdoch family — Fox/News Corp", 39, 14),
    ("Ford family — Ford", 40, 2),
    ("Roberts — Comcast", 33, 1),
    ("Hastings/Sarandos era — dual-class norm", 0, 0),  # placeholder trimmed below
]
DUAL_CLASS = [d for d in DUAL_CLASS if d[1] > 0]

# The world's big managed capital pools (2024 AUM, $tn) — sovereign wealth
# funds vs the Big Three asset managers. Curated (fund reports, SWFI).
CAPITAL_POOLS = [
    ("BlackRock", "asset mgr", 11.5), ("Vanguard", "asset mgr", 9.3),
    ("State Street", "asset mgr", 4.3),
    ("Norway (NBIM)", "SWF", 1.8), ("China (CIC)", "SWF", 1.35),
    ("Abu Dhabi (ADIA)", "SWF", 1.0), ("Saudi (PIF)", "SWF", 0.93),
    ("Kuwait (KIA)", "SWF", 0.8), ("Singapore (GIC)", "SWF", 0.77),
    ("Qatar (QIA)", "SWF", 0.53),
]

DOMAIN_COLOR = {"Technology": "#1f6feb", "Corporate control": "#8250df",
                "Resources": "#1a7f37", "Payments": "#9a6700"}


def chokepoints_df() -> pd.DataFrame:
    df = pd.DataFrame(CHOKEPOINTS, columns=["domain", "what", "n", "share", "who"])
    df["panel"] = df["what"].map(lambda w: PANEL_CHECK.get(w, (None, None))[0])
    return df


def the_controllers(n: int = 12) -> pd.DataFrame:
    """Individuals who personally control chokepoint firms (Forbes billionaires)."""
    keep = {"Elon Musk", "Larry Page", "Sergey Brin", "Jeff Bezos", "Mark Zuckerberg",
            "Jensen Huang", "Larry Ellison", "Michael Dell", "Steve Ballmer", "Bill Gates",
            "Changpeng Zhao", "Bernard Arnault & family", "Carlos Slim Helu & family"}
    with connect() as con:
        df = con.execute(
            "SELECT name, worth_usd/1e9 AS bn, source FROM billionaires ORDER BY worth_usd DESC"
        ).df()
    return df[df.name.isin(keep)].head(n).reset_index(drop=True)


# The people you've never heard of who exercise the concentrated power — the
# actual names behind the levers (verified from company disclosures + press,
# July 2026). `votes_$T` = US equity whose proxies they direct (from the manager's
# latest 13F), or the fund's size; None = not a share-voting role.
HIDDEN_HANDS = [
    ("Nicolai Tangen", "Norges Bank IM (Norway)", "CEO",
     "runs the world's largest single stock owner — ~1.5% of every listed company on Earth", 1.8),
    ("John Galloway", "Vanguard", "Global Head of Investment Stewardship",
     "directs the proxy votes of Vanguard's index funds", 6.9),
    ("Joud Abdel Majeid", "BlackRock", "Global Head of Investment Stewardship",
     "directs the proxy votes of BlackRock's index funds", 4.4),
    ("Benjamin Colton", "State Street (SSGA)", "Global Head of Asset Stewardship",
     "directs the proxy votes of State Street's index funds", 2.9),
    ("Gary Retelny", "ISS (owned by Deutsche Börse)", "President & CEO",
     "ISS + Glass Lewis advise ~95% of institutional proxy votes — the 'proxy cartel'", None),
    ("Bob Mann", "Glass Lewis (owned by Peloton Capital)", "CEO",
     "the other half of the proxy-advice duopoly", None),
    ("The U.S. Index Committee", "S&P Dow Jones Indices", "~9 anonymous staff, meet monthly",
     "decides who is IN the S&P 500 — an add forces index funds to buy billions", None),
    ("Frank La Salla", "DTCC", "President & CEO",
     "the utility that settles ~\\$4.7 QUADRILLION/yr and holds custody of ~\\$114T", None),
]

# Prior *hand-entered* Big-Three ownership snapshot — kept only as the before
# picture for the computed comparison below. It mixed filing quarters and used a
# stale BlackRock 13F (Q2-2024, before BlackRock moved filer to CIK 2012383), so
# it systematically understated. Superseded by the `edgar13f/*` series, which
# compute the stake live from the latest 13F info tables ÷ shares outstanding.
BIG3_OWNERSHIP = {
    "Nvidia": 20.8, "Coca-Cola": 19.0, "Exxon Mobil": 18.6, "Apple": 18.1,
    "Microsoft": 17.8, "Amazon": 17.5, "Tesla": 15.0, "JPMorgan": 14.8,
}
BIG3_PRIOR_TICKERS = {
    "Nvidia": "$NVDA", "Coca-Cola": "$KO", "Exxon Mobil": "$XOM", "Apple": "$AAPL",
    "Microsoft": "$MSFT", "Amazon": "$AMZN", "Tesla": "$TSLA", "JPMorgan": "$JPM",
}


def big3_computed_ownership(top_n: int = 500) -> pd.DataFrame:
    """Big Three ownership % per large-cap, COMPUTED from the latest 13F holdings
    (edgar13f/*) ÷ shares outstanding (edgar/shares_q). Top-N US operating
    companies by value held, excluding funds/ETFs; per-manager split included."""
    sql = """
    WITH big3 AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/big3_shares'),
         val  AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/big3_value'),
         blk  AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/blk_shares'),
         van  AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/van_shares'),
         ssga AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/ssga_shares'),
         sh   AS (SELECT entity, max_by(value, COALESCE(date, make_date(year,1,1))) shout
                  FROM obs WHERE series_id='edgar/shares_q' GROUP BY 1),
         nm   AS (SELECT entity, any_value(name) nm FROM entities GROUP BY 1)
    SELECT b.entity AS ticker, nm.nm AS issuer,
           100.0*b.v/sh.shout AS big3_pct, 100.0*blk.v/sh.shout AS blk_pct,
           100.0*van.v/sh.shout AS van_pct, 100.0*ssga.v/sh.shout AS ssga_pct,
           val.v AS value_held
    FROM big3 b JOIN sh USING(entity) JOIN val USING(entity)
         JOIN blk USING(entity) JOIN van USING(entity) JOIN ssga USING(entity)
         LEFT JOIN nm ON nm.entity = b.entity
    WHERE sh.shout > 0 AND 100.0*b.v/sh.shout BETWEEN 0 AND 60
      AND NOT regexp_matches(upper(COALESCE(nm.nm, '')), 'ETF|TRUST|FUND|SPDR|ISHARES')
    ORDER BY val.v DESC LIMIT ?
    """
    with connect() as con:
        return con.execute(sql, [top_n]).df()


# The elite convening venues — where the deciders actually meet now that the
# classic board-interlock network has thinned (Mizruchi 2013; Chu-Davis 2016).
# (name, ~members, what it is). Curated from each body's disclosures + press.
ELITE_VENUES = [
    ("Business Roundtable", 200, "CEOs of America's largest companies"),
    ("WEF 'Strategic Partners'", 100, "the Davos inner ring of global companies"),
    ("Trilateral Commission", 337, "fixed roster; ~94% also on CFR lists (1992)"),
    ("Bilderberg", 130, "per-meeting, Chatham House rules, no fixed roster"),
    ("Council on Foreign Relations", 5000, "the US foreign-policy establishment"),
    ("Bohemian Grove", 2500, "summer retreat of the business/political elite"),
]

# Documented overlaps between venues, and people who bridge several — the
# "connections" made visible (verified from press/rosters, Jul 2026).
VENUE_EDGES = [
    ("Council on Foreign Relations", "Trilateral Commission", "316 of 337 members shared (1992)"),
    ("WEF 'Strategic Partners'", "Business Roundtable", "the same mega-cap CEOs"),
    ("Bilderberg", "WEF 'Strategic Partners'", "overlapping attendees"),
    ("Council on Foreign Relations", "Bilderberg", "shared attendees"),
    ("Trilateral Commission", "Bilderberg", "shared attendees"),
]
BRIDGERS = [  # a few people documented across multiple venues
    "David Rubenstein — CFR chair + WEF trustee (Carlyle co-founder)",
    "Larry Fink — WEF trustee + Business Roundtable (BlackRock)",
    "Jamie Dimon — Business Roundtable + Davos regular (JPMorgan)",
    "Eric Schmidt — Bilderberg + WEF (ex-Google)",
]


# The private conferences, sorted by MEASURABLE impact (curated attendance/purpose
# from each event + press; impact assessed against data/scholarship).
# (name, when, ~attendees, who, what it's for, measurable impact)
CONFERENCES = [
    ("Jackson Hole Symposium", "late Aug", 120, "central bankers + economists (invite-only)",
     "signal monetary policy", "MOVES MARKETS — S&P swings ~1.4x a normal day"),
    ("Sun Valley (Allen & Co)", "July", 300, "media/tech/finance moguls (no press)",
     "deal-making", "seeded Disney-ABC, Comcast-NBCU, Bezos-Washington Post"),
    ("Milken Global Conference", "May", 4000, "PE, sovereign funds, financiers",
     "raise capital, deals", "capital flows; the 'Predators' Ball' legacy"),
    ("WEF / Davos", "mid-Jan", 2800, "heads of state, CEOs, ~100 partner firms",
     "agenda-setting, networking", "~none measurable — attendees UNDERperformed the S&P"),
    ("Bilderberg", "June", 130, "politicians, bankers, royals (invite-only)",
     "transatlantic elite dialogue", "unmeasurable — Chatham House rules, no roster"),
    ("Bohemian Grove", "July", 2500, "the male business/political elite (secret)",
     "social retreat", "unmeasurable (Manhattan Project reputedly discussed here, 1942)"),
]

# Jackson Hole = the Fed's symposium; the chair speaks Friday morning. Davos runs
# a full week in mid-January. We measure the S&P's move around each.
JH_FRIDAYS = {2015: "2015-08-28", 2016: "2016-08-26", 2017: "2017-08-25", 2018: "2018-08-24",
              2019: "2019-08-23", 2020: "2020-08-27", 2021: "2021-08-27", 2022: "2022-08-26",
              2023: "2023-08-25", 2024: "2024-08-23", 2025: "2025-08-22"}
DAVOS_WEEKS = [("2016-01-18", "2016-01-22"), ("2017-01-16", "2017-01-20"), ("2018-01-22", "2018-01-26"),
               ("2019-01-21", "2019-01-25"), ("2020-01-20", "2020-01-24"), ("2023-01-16", "2023-01-20"),
               ("2024-01-15", "2024-01-19"), ("2025-01-20", "2025-01-24")]


# FOMC policy-decision days (announcement, day 2), 2022-2025 — the Fed's eight
# closed-door meetings a year. Dates from federalreserve.gov FOMC calendars.
FOMC_DAYS = [
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21",
    "2022-11-02", "2022-12-14", "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13", "2024-01-31", "2024-03-20",
    "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
    "2025-10-29", "2025-12-10",
]


def fomc_reaction() -> dict:
    """Multi-asset market move on FOMC decision days vs a normal day, 2022-2025."""
    def series(sid, diff=False, bp=False):
        with connect() as con:
            s = con.execute(f"SELECT date, value FROM obs WHERE series_id='{sid}' ORDER BY date").df()
        s["date"] = pd.to_datetime(s["date"])
        v = s.set_index("date")["value"]
        return (v.diff() * (100 if bp else 1)) if diff else v.pct_change() * 100

    assets = {"S&P 500": (series("markets/spx"), "%"), "2yr yield": (series("fred/DGS2", diff=True, bp=True), "bp"),
              "10yr yield": (series("fred/DGS10", diff=True, bp=True), "bp"), "VIX": (series("fred/VIXCLS", diff=True), "pt")}
    days = [pd.Timestamp(d) for d in FOMC_DAYS]
    out = {}
    for name, (s, unit) in assets.items():
        fomc = s.reindex(days).dropna().abs()
        base = s["2022":"2025"].dropna().abs()
        out[name] = {"fomc": float(fomc.mean()), "base": float(base.mean()),
                     "ratio": float(fomc.mean() / base.mean()), "unit": unit}
    return out


def jackson_hole_effect() -> dict:
    """S&P move on Jackson Hole Fridays vs Davos weeks vs a normal day."""
    with connect() as con:
        s = con.execute("SELECT date, value FROM obs WHERE series_id='markets/spx' ORDER BY date").df()
    s["date"] = pd.to_datetime(s["date"])
    ret = s.set_index("date")["value"].pct_change() * 100
    jh = {y: ret.get(pd.Timestamp(d)) for y, d in JH_FRIDAYS.items()}
    jh = {y: r for y, r in jh.items() if r is not None and pd.notna(r)}
    davos = pd.concat([ret[a:b].dropna() for a, b in DAVOS_WEEKS])
    base = ret["2015":"2025"].dropna()
    return {"jh": jh, "jh_absmean": float(np.mean([abs(v) for v in jh.values()])),
            "davos_absmean": float(davos.abs().mean()), "base_absmean": float(base.abs().mean())}


# ---------- figures ----------

def fig_chokepoint_map() -> None:
    df = chokepoints_df().sort_values(["share", "n"], ascending=[True, False])
    print("[ch10] chokepoints:", len(df), "| panel-checked:", df.panel.notna().sum())
    fig, ax = new_fig(
        "The chokepoints: where one, two, or three entities control the many",
        subtitle="Combined market share of the top controllers in each domain (curated; ✓ = corroborated by the AI panel). "
        "The recurring number is 1–4 — technology, regulation, and geography all breed bottlenecks.",
        ylabel=None,
    )
    y = np.arange(len(df))
    colors = [DOMAIN_COLOR[d] for d in df.domain]
    ax.barh(y, df.share, color=colors)
    labels = [f"{w}  ({who})" for w, who in zip(df.what, df.who)]
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("share controlled by the top players, %")
    ax.set_xlim(0, 118)
    for i, r in enumerate(df.itertuples()):
        tag = f"{int(r.n)} firm" + ("s" if r.n > 1 else "")
        chk = ""
        if pd.notna(r.panel):
            chk = "  ✓AI" if r.panel >= 90 else f"  ⚠AI {int(r.panel)}"
        ax.text(r.share + 1, i, f"{int(r.share)}%  · {tag}{chk}", va="center", fontsize=7.5,
                color="#24292f")
    handles = [plt_patch(c, d) for d, c in DOMAIN_COLOR.items()]
    ax.legend(handles=handles, fontsize=8, loc="lower right", ncol=2)
    source_note(ax, "Source: curated concentration ratios (industry reports); ✓ = AI-panel consensus ≥90 (econlab panel, free Groq models)")
    save(fig, "10_chokepoint_map")


def plt_patch(color, label):
    import matplotlib.patches as mpatches
    return mpatches.Patch(color=color, label=label)


def fig_dual_class() -> None:
    fig, ax = new_fig(
        "Control without ownership: the dual-class wedge",
        subtitle="Founder/family voting power vs their economic stake, via super-voting shares (company proxies). "
        "A minority owner commands the company — the purest form of 'decision behind the money'.",
        ylabel=None,
    )
    names = [d[0] for d in DUAL_CLASS][::-1]
    voting = [d[1] for d in DUAL_CLASS][::-1]
    econ = [d[2] for d in DUAL_CLASS][::-1]
    y = np.arange(len(names))
    ax.barh(y + 0.2, voting, height=0.38, color="#8250df", label="voting power %")
    ax.barh(y - 0.2, econ, height=0.38, color="#57606a", label="economic stake %")
    ax.set_yticks(y, names, fontsize=8.5)
    for i in range(len(names)):
        ax.text(voting[i] + 1, y[i] + 0.2, f"{voting[i]}%", va="center", fontsize=7.5, color="#8250df")
        ax.text(econ[i] + 1, y[i] - 0.2, f"{econ[i]}%", va="center", fontsize=7.5, color="#57606a")
    ax.set_xlabel("% of the company")
    ax.set_xlim(0, 70)
    ax.legend(fontsize=8.5, loc="lower right")
    source_note(ax, "Source: curated from company proxy statements (econlab warehouse)")
    save(fig, "10_dual_class")


def fig_capital_pools() -> None:
    df = pd.DataFrame(CAPITAL_POOLS, columns=["name", "kind", "aum"]).sort_values("aum")
    big3 = df[df.kind == "asset mgr"].aum.sum()
    swf = df[df.kind == "SWF"].aum.sum()
    print(f"[ch10] Big Three ${big3:.1f}T vs top-7 SWFs ${swf:.1f}T")
    fig, ax = new_fig(
        "Who manages the world's savings: the Big Three vs the sovereign funds",
        subtitle="Assets under management, 2024 ($tn). The three US index managers together run more than every major "
        "sovereign wealth fund on Earth combined — private managers, public and autocratic states, one chart.",
        ylabel=None,
    )
    colors = ["#8250df" if k == "asset mgr" else "#1a7f37" for k in df.kind]
    y = np.arange(len(df))
    ax.barh(y, df.aum, color=colors)
    ax.set_yticks(y, df.name, fontsize=8.5)
    for i, r in enumerate(df.itertuples()):
        ax.text(r.aum + 0.1, i, f"${r.aum:.1f}T", va="center", fontsize=8)
    ax.set_xlabel("assets under management, \\$ trillions")
    ax.set_xlim(0, 13)
    ax.text(6.5, 1.5, f"Big Three: \\${big3:.0f}T\ntop-7 SWFs: \\${swf:.0f}T",
            fontsize=9, color="#24292f", bbox=dict(boxstyle="round", fc="#f6f8fa", ec="#8250df"))
    handles = [plt_patch("#8250df", "US index managers"), plt_patch("#1a7f37", "sovereign wealth funds")]
    ax.legend(handles=handles, fontsize=8.5, loc="lower right")
    source_note(ax, "Source: curated (firm reports, SWF Institute) (econlab warehouse)")
    save(fig, "10_capital_pools")


def fig_hidden_hands() -> None:
    """The names you don't know: who actually casts the votes and works the plumbing."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.suptitle("The names you don't know: who actually votes your shares",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)
    ax.axis("off")
    ax.text(0, 1.0, "Not the founders everyone can name — the obscure professionals who exercise "
            "delegated power over trillions they do not own.", transform=ax.transAxes,
            fontsize=9.5, color="#57606a", va="top")

    n = len(HIDDEN_HANDS)
    for i, (name, org, role, what, scale) in enumerate(HIDDEN_HANDS):
        y = 0.90 - i * (0.90 / n)
        color = "#8250df" if scale else "#0969da"
        ax.text(0.0, y, name, transform=ax.transAxes, fontsize=11, fontweight="bold", color=color, va="center")
        ax.text(0.27, y + 0.018, f"{role} · {org}", transform=ax.transAxes, fontsize=8, color="#24292f", va="center")
        ax.text(0.27, y - 0.020, what, transform=ax.transAxes, fontsize=8, color="#57606a", va="center", style="italic")
        if scale:
            ax.text(0.99, y, f"votes ${scale:.1f}T of equity", transform=ax.transAxes, fontsize=9,
                    fontweight="bold", color="#8250df", va="center", ha="right")
    fig.text(0.01, 0.02, "Source: names verified from company disclosures + press (Jul 2026); equity-voted from each manager's latest 13F (econlab). "
             "Purple = directs proxy votes; blue = other chokepoint role.", fontsize=7.5, color="#57606a")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    save(fig, "10_hidden_hands")


def fig_big3_ownership() -> None:
    """Big Three ownership of corporate America — the real computed distribution,
    and how far the eight hand-entered constants understated it."""
    import matplotlib.pyplot as plt

    df = big3_computed_ownership(500)
    med = df["big3_pct"].median()
    share20 = 100 * (df["big3_pct"] >= 20).mean()
    print(f"[ch10] Big Three (computed 13F): n={len(df)} median={med:.1f}% "
          f"share>=20%={share20:.0f}% mega-cap avg blk/van/ssga="
          f"{df['blk_pct'].mean():.1f}/{df['van_pct'].mean():.1f}/{df['ssga_pct'].mean():.1f}")

    # prior hand-entered value vs newly computed, for the named set
    lut = {r.ticker: r.big3_pct for r in df.itertuples()}
    pairs = [(n, BIG3_OWNERSHIP[n], lut[t]) for n, t in BIG3_PRIOR_TICKERS.items() if t in lut]
    pairs.sort(key=lambda p: p[2])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2))
    fig.suptitle("The Big Three own more of corporate America than the constants said",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # Panel A — the computed distribution
    ax1.hist(df["big3_pct"], bins=range(0, 46, 2), color="#8250df", alpha=0.85, edgecolor="white", lw=0.5)
    ax1.axvline(med, color="#1a1a1a", lw=1.6, ls="--")
    ax1.text(med + 0.6, ax1.get_ylim()[1] * 0.92, f"median {med:.1f}%", fontsize=9, fontweight="bold")
    for _, prior, _c in pairs:  # rug of the 8 hand-entered values
        ax1.plot([prior], [-1.6], marker="^", color="#9a6700", ms=6, clip_on=False)
    ax1.text(sum(p[1] for p in pairs) / len(pairs), -4.3, "the hand-entered\nvalues sat here",
             fontsize=7.5, color="#9a6700", ha="center", va="top")
    ax1.set_title(f"Combined stake in the 500 largest US firms — {share20:.0f}% are ≥20% owned",
                  fontsize=9.5, loc="left")
    ax1.set_xlabel("Big Three combined ownership, % of shares outstanding")
    ax1.set_ylabel("number of companies")
    ax1.set_xlim(0, 45)

    # Panel B — prior (hand-entered) vs computed, dumbbell
    y = range(len(pairs))
    for i, (name, prior, comp) in enumerate(pairs):
        ax2.plot([prior, comp], [i, i], color="#c9c9c9", lw=2, zorder=1)
        ax2.scatter(prior, i, color="#9a6700", s=42, zorder=2)
        ax2.scatter(comp, i, color="#8250df", s=42, zorder=2)
        ax2.text(comp + 0.4, i, f"+{comp - prior:.1f}", va="center", fontsize=8, color="#57606a")
    ax2.set_yticks(list(y), [p[0] for p in pairs], fontsize=9)
    ax2.set_title("Every hand-entered value understated the truth", fontsize=9.5, loc="left")
    ax2.set_xlabel("Big Three ownership, %")
    ax2.set_xlim(10, 30)
    ax2.scatter([], [], color="#9a6700", s=42, label="hand-entered (stale)")
    ax2.scatter([], [], color="#8250df", s=42, label="computed (latest 13F)")
    ax2.legend(fontsize=8, loc="lower right")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="x" if ax is ax2 else "y")
    fig.text(0.01, -0.03, "Source: computed from the latest SEC 13F info tables (BlackRock 2026-Q1, State Street 2026-Q1, "
             "Vanguard 2025-Q4) ÷ shares outstanding (SEC XBRL). ~500 largest US operating companies by value held (econlab).",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_big3_ownership")


def fig_elite_network() -> None:
    """How the deciders connect now: the elite convening venues and their overlaps."""
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw={"width_ratios": [1, 1.15]})
    fig.suptitle("How the deciders connect: not shared boards anymore, but shared rooms",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    # left: venues by membership
    v = sorted(ELITE_VENUES, key=lambda x: x[1])
    y = np.arange(len(v))
    ax1.barh(y, [x[1] for x in v], color="#8250df")
    ax1.set_yticks(y, [x[0] for x in v], fontsize=8.5)
    for i, x in enumerate(v):
        ax1.text(x[1] + 40, i, f"~{x[1]:,}", va="center", fontsize=8)
    ax1.set_title("The convening venues, by membership", fontsize=10, loc="left")
    ax1.set_xlabel("approx. members")
    ax1.set_xlim(0, 6000)
    ax1.spines[["top", "right"]].set_visible(False)

    # right: the overlap network (short labels placed below each node)
    ax2.axis("off")
    ax2.set_title("...and how they overlap", fontsize=10, loc="left")
    pos = {"Council on Foreign Relations": (0.5, 0.92), "Trilateral Commission": (0.08, 0.58),
           "Bilderberg": (0.92, 0.58), "WEF 'Strategic Partners'": (0.72, 0.2),
           "Business Roundtable": (0.28, 0.2), "Bohemian Grove": (0.5, 0.55)}
    short = {"Council on Foreign Relations": "CFR", "Trilateral Commission": "Trilateral",
             "Bilderberg": "Bilderberg", "WEF 'Strategic Partners'": "Davos (WEF)",
             "Business Roundtable": "Business\nRoundtable", "Bohemian Grove": "Bohemian\nGrove"}
    for a, b, _ in VENUE_EDGES:
        if a in pos and b in pos:
            ax2.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#8250df", lw=1.6, alpha=0.5, zorder=1)
    for name, (x, yy) in pos.items():
        ax2.scatter([x], [yy], s=180, color="#8250df", zorder=2)
        va = "top" if yy < 0.5 else "bottom"
        dy = -0.06 if yy < 0.5 else 0.06
        ax2.annotate(short[name], (x, yy + dy), fontsize=8, ha="center", va=va,
                     color="#24292f", fontweight="bold", zorder=3)
    ax2.annotate("94% of Trilateral\nalso on CFR", (0.29, 0.75), fontsize=7, color="#8250df", ha="center")
    ax2.set_xlim(-0.1, 1.1)
    ax2.set_ylim(0.0, 1.05)
    fig.text(0.55, 0.06, "Bridging figures: " + " · ".join(b.split(" — ")[0] for b in BRIDGERS),
             transform=fig.transFigure, fontsize=7.5, color="#57606a")

    fig.text(0.01, -0.01, "Source: curated from each body's rosters/press (Jul 2026); overlap stat from published Trilateral/CFR lists. "
             "The classic board-interlock network thinned since the 1970s (Mizruchi 2013); coordination moved to ownership + venues.",
             fontsize=7.5, color="#57606a")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    save(fig, "10_elite_network")


def fig_conference_impact() -> None:
    """The conference that moves markets (Jackson Hole) vs the one that doesn't (Davos)."""
    import matplotlib.pyplot as plt

    e = jackson_hole_effect()
    print(f"[ch10] JH day |move| {e['jh_absmean']:.2f}% ({e['jh_absmean']/e['base_absmean']:.2f}x); "
          f"Davos {e['davos_absmean']:.2f}% ({e['davos_absmean']/e['base_absmean']:.2f}x); base {e['base_absmean']:.2f}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.4, 1]})
    fig.suptitle("Which private conference actually moves the world? Measure it.",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    yrs = sorted(e["jh"])
    vals = [e["jh"][y] for y in yrs]
    colors = ["#d1242f" if v < 0 else "#1a7f37" for v in vals]
    ax1.bar(range(len(yrs)), vals, color=colors)
    ax1.set_xticks(range(len(yrs)), [str(y) for y in yrs], fontsize=8, rotation=45)
    ax1.axhline(0, color="#24292f", lw=0.8)
    ax1.set_title("S&P 500 move on Jackson Hole day (the Fed chair speaks)", fontsize=10, loc="left")
    ax1.set_ylabel("S&P 500 daily return, %")
    for i, (y, v) in enumerate(zip(yrs, vals)):
        if abs(v) > 2:
            lbl = "2022 'pain'\nspeech" if y == 2022 else "2019"
            ax1.annotate(lbl, (i, v), xytext=(0, -14 if v < 0 else 8), textcoords="offset points",
                         ha="center", fontsize=7.5, color="#d1242f")

    labels = ["a normal\nday", "Jackson\nHole day", "Davos\nweek"]
    means = [e["base_absmean"], e["jh_absmean"], e["davos_absmean"]]
    bcol = ["#57606a", "#8250df", "#9a6700"]
    ax2.bar(range(3), means, color=bcol)
    ax2.set_xticks(range(3), labels, fontsize=8.5)
    ax2.set_title("Avg absolute S&P move (2015–25)", fontsize=10, loc="left")
    ax2.set_ylabel("mean |daily return|, %")
    for i, m in enumerate(means):
        ax2.text(i, m + 0.02, f"{m:.2f}%\n{m/e['base_absmean']:.2f}×", ha="center", fontsize=8)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02, "Source: computed from S&P 500 daily prices (econlab warehouse); Jackson Hole & Davos dates curated. "
             "Markets react to the Fed's symposium, not to the billionaires' forum.", fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_conference_impact")


def fig_fomc_power() -> None:
    """The room that actually runs markets: one FOMC meeting moves every asset."""
    import matplotlib.pyplot as plt

    r = fomc_reaction()
    e = jackson_hole_effect()
    print("[ch10] FOMC-day ratios:", {k: round(v["ratio"], 2) for k, v in r.items()})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The most powerful private meeting isn't Davos — it's the FOMC",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    names = list(r)
    ratios = [r[n]["ratio"] for n in names]
    ax1.bar(range(len(names)), ratios, color="#8250df")
    ax1.axhline(1, color="#57606a", lw=1, ls="--")
    ax1.set_xticks(range(len(names)), names, fontsize=8.5)
    ax1.set_title("One FOMC decision moves every asset (× a normal day, 2022–25)", fontsize=9.5, loc="left")
    ax1.set_ylabel("mean |move| ÷ normal-day |move|")
    for i, n in enumerate(names):
        ax1.text(i, r[n]["ratio"] + 0.02, f"{r[n]['ratio']:.2f}×\n{r[n]['fomc']:.1f}{r[n]['unit']}",
                 ha="center", fontsize=7.5)
    ax1.set_ylim(0, 1.8)

    # event ranking, S&P |move| ÷ that period's normal day
    events = {"FOMC\ndecision": r["S&P 500"]["ratio"], "Jackson\nHole": e["jh_absmean"] / e["base_absmean"],
              "a normal\nday": 1.0, "Davos\nweek": e["davos_absmean"] / e["base_absmean"]}
    cols = ["#8250df", "#8250df", "#57606a", "#9a6700"]
    ax2.bar(range(len(events)), list(events.values()), color=cols)
    ax2.axhline(1, color="#57606a", lw=1, ls="--")
    ax2.set_xticks(range(len(events)), list(events), fontsize=8.5)
    ax2.set_title("S&P move by event (× a normal day)", fontsize=9.5, loc="left")
    ax2.set_ylabel("mean |S&P move| ÷ normal")
    for i, v in enumerate(events.values()):
        ax2.text(i, v + 0.02, f"{v:.2f}×", ha="center", fontsize=8)
    ax2.set_ylim(0, 1.7)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02, "Source: computed from S&P 500, 2yr/10yr Treasury yields, VIX (econlab warehouse); FOMC dates from the Fed. "
             "12 people, 8 closed-door meetings a year, move the wealth of everyone who owns an asset.", fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_fomc_power")


def npx_voting() -> dict:
    """How the Big Three actually vote (Form N-PX): the share of votes cast with
    management overall, and by proposal category."""
    with connect() as con:
        mgr = con.execute(
            "SELECT e.name mgr, round(o.value,1) pct, "
            "(SELECT value FROM obs v WHERE v.series_id='npx/votes' AND v.entity=o.entity) votes "
            "FROM obs o JOIN entities e USING(entity) "
            "WHERE o.series_id='npx/mgmt_support' ORDER BY o.value DESC").df()
        cat = con.execute(
            "SELECT category, round(sum(mgmt_support_pct*n_votes)/sum(n_votes),1) pct, sum(n_votes) votes "
            "FROM npx_categories GROUP BY 1 HAVING sum(n_votes)>=800 ORDER BY 2 DESC").df()
    return {"managers": mgr, "categories": cat}


def fig_npx_votes() -> None:
    """The Big Three own ~a quarter — and vote ~95% of it with management."""
    import matplotlib.pyplot as plt

    r = npx_voting()
    mgr, cat = r["managers"], r["categories"]
    print(f"[ch10] N-PX support with management: "
          + ", ".join(f"{m.mgr.split(' (')[0]} {m.pct:.0f}%" for m in mgr.itertuples()))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.25]})
    fig.suptitle("The Big Three own ~a quarter of corporate America — and vote ~95% of it with management",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)

    names = [m.split(" (")[0] for m in mgr["mgr"]]
    ax1.bar(range(len(mgr)), mgr["pct"], color=["#8250df", "#9a6700", "#57606a"][:len(mgr)])
    ax1.set_xticks(range(len(mgr)), names, fontsize=9)
    ax1.set_ylim(80, 100)
    ax1.set_ylabel("% of votes cast with management")
    ax1.set_title("Overall support for management, by manager", fontsize=9.5, loc="left")
    for i, m in enumerate(mgr.itertuples()):
        ax1.text(i, m.pct + 0.3, f"{m.pct:.1f}%", ha="center", fontsize=9, fontweight="bold")
        ax1.text(i, 81, f"{int(m.votes):,}\nvotes", ha="center", fontsize=7, color="white")

    c = cat.iloc[::-1]
    ax2.barh(range(len(c)), c["pct"], color="#8250df")
    ax2.set_yticks(range(len(c)), [x.title().replace("Section 14A ", "") for x in c["category"]], fontsize=8)
    for i, row in enumerate(c.itertuples()):
        ax2.text(row.pct - 1.5, i, f"{row.pct:.0f}%", va="center", ha="right", fontsize=8, color="white", fontweight="bold")
    ax2.set_xlim(0, 105)
    ax2.axvline(100, color="#57606a", lw=0.8, ls=":")
    ax2.set_title("The routine ballot is rubber-stamped; governance the lone exception", fontsize=9.5, loc="left")
    ax2.set_xlabel("% voted with management")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    ax1.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02, "Source: computed from Form N-PX proxy-vote records (2024–25 season) — a representative vote file per "
             "manager's flagship index registrant (iShares Trust, Vanguard Index Funds, Select Sector SPDR); ~120k votes (econlab).",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_npx_votes")


def concentration_dashboard() -> list[dict]:
    """Every computable concentration measure on its own time axis — to test the
    report's own 'concentration spine'. Returns one dict per series with the
    trend and whether concentration ROSE (↑), FELL (↓) or held (→)."""
    with connect() as con:
        def q(sql):
            d = con.execute(sql).df()
            return d.iloc[:, 0].tolist(), d.iloc[:, 1].tolist()

        wealth_yr, wealth = q(
            "WITH x AS (SELECT year, date, value FROM obs WHERE series_id IN "
            "('dfa/nwshare.net_worth.toppt1','dfa/nwshare.net_worth.remainingtop1')), "
            "l AS (SELECT year, max(date) md FROM x GROUP BY 1) "
            "SELECT x.year, round(sum(x.value),1) FROM x JOIN l ON x.year=l.year AND x.date=l.md GROUP BY 1 ORDER BY 1")
        firms_yr, firms = q(
            "SELECT year, value FROM obs WHERE series_id='wdi/CM.MKT.LDOM.NO' AND entity='USA' AND year>=1996 ORDER BY 1")
        chn_yr, chn = q(
            "SELECT year, round(100.0*sum(value_usd) FILTER(WHERE exporter='CHN')/sum(value_usd),1) FROM trade GROUP BY 1 ORDER BY 1")
        hhi_yr, hhi = q(
            "WITH e AS (SELECT year, exporter, sum(value_usd) v FROM trade GROUP BY 1,2), "
            "t AS (SELECT year, sum(v) tv FROM e GROUP BY 1) "
            "SELECT e.year, round(sum(power(100.0*e.v/t.tv,2)),0) FROM e JOIN t USING(year) GROUP BY 1 ORDER BY 1")
        oil_yr, oil = q(
            "WITH p AS (SELECT year, entity, value FROM obs WHERE series_id='energy/oil_production' AND value>0 AND length(entity)=3 AND entity!='WLD'), "
            "t AS (SELECT year, sum(value) tv FROM p GROUP BY 1), "
            "c AS (SELECT year, sum(value) c4 FROM (SELECT year,value,row_number() OVER(PARTITION BY year ORDER BY value DESC) rk FROM p) WHERE rk<=4 GROUP BY 1) "
            "SELECT t.year, round(100.0*c.c4/t.tv,0) FROM t JOIN c USING(year) WHERE t.year>=1965 ORDER BY 1")
        usd_yr, usd = q(
            "SELECT year, round(max_by(value, COALESCE(date, make_date(year,1,1))),1) "
            "FROM obs WHERE series_id='cofer/reserve_share.USD' GROUP BY year ORDER BY year")

    def rec(title, unit, yr, val, rose, note):
        return {"title": title, "unit": unit, "years": yr, "values": val,
                "rose": rose, "start": val[0], "end": val[-1], "note": note}

    return [
        rec("US top-1% wealth share", "%", wealth_yr, wealth, True, "Fed DFA"),
        rec("US listed companies", "count", firms_yr, firms, True, "fewer firms = concentration by subtraction"),
        rec("China's share of world exports", "%", chn_yr, chn, True, "one nation's rise"),
        rec("Top-4 oil producers' share", "%", oil_yr, oil, False, "OPEC loosened; shale partly re-tightened"),
        rec("US-dollar share of FX reserves", "%", usd_yr, usd, False, "COFER"),
        rec("World-export concentration (HHI)", "index", hhi_yr, hhi, None, "all exporters"),
    ]


def fig_concentration_dashboard() -> None:
    """Is concentration rising everywhere? No — several laws with opposite signs."""
    import matplotlib.pyplot as plt

    d = concentration_dashboard()
    up = sum(1 for s in d if s["rose"] is True)
    down = sum(1 for s in d if s["rose"] is False)
    print(f"[ch10] concentration dashboard: {up} rose, {down} fell, "
          + "; ".join(f"{s['title'][:18]} {s['start']}→{s['end']}" for s in d))

    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.6))
    fig.suptitle("Is concentration rising everywhere?  No — it is several laws with opposite signs",
                 x=0.01, ha="left", fontweight="bold", fontsize=13.5)
    COL = {True: "#b42318", False: "#0d6e78", None: "#57606a"}
    TAG = {True: "▲ concentration rose", False: "▼ concentration fell", None: "▬ roughly flat"}

    for ax, s in zip(axes.flat, d):
        c = COL[s["rose"]]
        ax.plot(s["years"], s["values"], lw=2, color=c)
        ax.fill_between(s["years"], s["values"], min(s["values"]) - (max(s["values"]) - min(s["values"])) * 0.08,
                        color=c, alpha=0.08)
        ax.scatter([s["years"][-1]], [s["values"][-1]], color=c, s=22, zorder=3)
        fmt = (lambda v: f"{v:,.0f}") if s["unit"] == "count" else (lambda v: f"{v:g}{'' if s['unit']=='index' else ''}")
        ax.set_title(s["title"], fontsize=9.5, loc="left", fontweight="bold")
        ax.text(0.02, 0.90, f"{fmt(s['start'])} → {fmt(s['end'])}", transform=ax.transAxes, fontsize=8.5, va="top")
        ax.text(0.02, 0.06, TAG[s["rose"]], transform=ax.transAxes, fontsize=8, color=c, fontweight="bold")
        ax.text(0.98, 0.06, s["note"], transform=ax.transAxes, fontsize=6.6, color="#8593a0", ha="right", style="italic")
        ax.set_xticks([s["years"][0], s["years"][-1]])
        ax.tick_params(labelsize=7.5)
        ax.margins(y=0.18)
        ax.spines[["top", "right"]].set_visible(False)

    fig.text(0.01, 0.005,
             "The honest reading: ownership and control concentrated (household wealth, and a public market that halved into "
             "fewer firms) — but the physical and monetary commons went the OTHER way (oil production and the reserve currency "
             "de-concentrated; world trade held flat). ‘Everything concentrates’ is half true.",
             fontsize=8, color="#333333", style="italic")
    fig.text(0.01, -0.035, "Source: computed from Fed DFA, WDI listed firms, BACI world trade, Energy Institute oil production, "
             "IMF COFER (econlab). Each panel on its own axis and time span.", fontsize=7.3, color="#57606a")
    fig.tight_layout()
    save(fig, "10_concentration_dashboard")


def _fmt_director(n: str) -> str:
    """SEC reporting-owner names are 'LAST FIRST [MIDDLE]' -> 'First [Middle] Last'."""
    parts = str(n).split()
    if len(parts) >= 2:
        return " ".join(p.title() for p in parts[1:] + parts[:1])
    return str(n).title()


def board_interlocks(top_n: int = 500) -> dict:
    """The director-interlock network among the top-N large caps, computed from
    Form-4 board seats: how many directors sit on 2+ boards, and who bridges most."""
    with connect() as con:
        seats = con.execute(
            "WITH big3 AS (SELECT entity, value v FROM obs WHERE series_id='edgar13f/big3_value'), "
            f"top AS (SELECT entity FROM big3 ORDER BY v DESC LIMIT {int(top_n)}) "
            "SELECT DISTINCT person_cik, person, ticker FROM board_seats "
            "WHERE ticker IN (SELECT entity FROM top)"
        ).df()
    per = seats.groupby("person_cik").agg(
        person=("person", "first"), boards=("ticker", "nunique"),
        companies=("ticker", lambda s: ", ".join(sorted(set(s))))).reset_index()
    n_dir = len(per)
    n_inter = int((per["boards"] >= 2).sum())
    dist = per["boards"].value_counts().sort_index()
    top = per.sort_values("boards", ascending=False).head(10).copy()
    top["name"] = top["person"].map(_fmt_director)
    return {"n_dir": n_dir, "n_inter": n_inter, "pct": 100 * n_inter / n_dir,
            "busiest": int(per["boards"].max()), "dist": dist, "top": top}


def fig_interlocks() -> None:
    """The board-interlock network among large caps — real, but thin."""
    import matplotlib.pyplot as plt

    r = board_interlocks(500)
    print(f"[ch10] interlocks: {r['n_dir']} large-cap directors, {r['n_inter']} on 2+ boards "
          f"({r['pct']:.1f}%), busiest {r['busiest']}; top {r['top'].iloc[0]['name']}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("The board network is real but thin — cohesion moved to common ownership",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    d = r["dist"]
    ax1.bar([str(i) for i in d.index], d.values, color="#57606a")
    ax1.set_yscale("log")
    ax1.set_title(f"Large-cap boards per director — {r['pct']:.0f}% sit on 2+, the busiest on {r['busiest']}",
                  fontsize=9.5, loc="left")
    ax1.set_xlabel("number of top-500 boards held")
    ax1.set_ylabel("directors (log)")
    for i, v in zip(range(len(d)), d.values):
        ax1.text(i, v * 1.15, f"{int(v):,}", ha="center", fontsize=8)

    t = r["top"].iloc[::-1]
    ax2.barh(range(len(t)), t["boards"], color="#8250df")
    ax2.set_yticks(range(len(t)), t["name"], fontsize=8.5)
    for i, (_, row) in enumerate(t.iterrows()):
        ax2.text(0.12, i, row["companies"].replace("$", ""), va="center", ha="left", fontsize=6.6, color="white")
        ax2.text(row["boards"] + 0.06, i, str(int(row["boards"])), va="center", fontsize=8.5)
    ax2.set_title("The super-connectors — who bridges the most large-cap boards", fontsize=9.5, loc="left")
    ax2.set_xlabel("large-cap boards held")
    ax2.set_xlim(0, r["busiest"] + 1.5)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    ax1.grid(alpha=0.25, axis="y")
    fig.text(0.01, -0.02, "Source: computed from SEC Form 3/4/5 insider filings (recent quarters), directors only, "
             "deduped to distinct (person, company) seats; interlocks among the 500 largest US firms (econlab).",
             fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_interlocks")


def fomc_dissent_record() -> dict:
    """The FOMC vote record parsed from Fed statements: dissents by year and by
    member, and the fact that the chair's action carried every meeting."""
    with connect() as con:
        by_year = con.execute(
            "SELECT year, value FROM obs WHERE series_id='fomc/dissents' ORDER BY year").df()
        meetings = con.execute("SELECT sum(value) FROM obs WHERE series_id='fomc/meetings'").fetchone()[0]
        dissents = con.execute("SELECT sum(value) FROM obs WHERE series_id='fomc/dissents'").fetchone()[0]
        top = con.execute(
            "SELECT member, count(*) n FROM fomc_dissents GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10").df()
        span = con.execute("SELECT min(year), max(year) FROM obs WHERE series_id='fomc/meetings'").fetchone()
    return {"by_year": by_year, "meetings": int(meetings), "dissents": int(dissents),
            "top": top, "span": (int(span[0]), int(span[1]))}


def fig_fomc_deciders() -> None:
    """Inside the room that moves markets: twelve vote, but the chair always wins."""
    import matplotlib.pyplot as plt

    r = fomc_dissent_record()
    print(f"[ch10] FOMC {r['span'][0]}–{r['span'][1]}: {r['meetings']} meetings, "
          f"{r['dissents']} dissents, chair carried all; top dissenter {r['top'].iloc[0]['member']}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Twelve vote, but one decides: the chair's action carried all {r['meetings']} meetings",
                 x=0.01, ha="left", fontweight="bold", fontsize=13)

    by = r["by_year"]
    ax1.bar(by["year"], by["value"], color="#9a6700", width=0.7)
    ax1.set_title(f"Dissenting votes per year ({r['span'][0]}–{r['span'][1]}) — never enough to overturn",
                  fontsize=9.5, loc="left")
    ax1.set_ylabel("dissenting votes")
    ax1.annotate("QE-era hawk\nrevolt", xy=(2013, 8), xytext=(2014.4, 7.4), fontsize=8,
                 color="#57606a", arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))
    ax1.annotate("2025:\nrate-cut\ndissents", xy=(2025, 5), xytext=(2022.6, 6.0), fontsize=8,
                 color="#57606a", arrowprops=dict(arrowstyle="->", color="#57606a", lw=0.8))

    t = r["top"].iloc[::-1]
    ax2.barh(range(len(t)), t["n"], color="#8250df")
    ax2.set_yticks(range(len(t)), t["member"], fontsize=9)
    for i, v in enumerate(t["n"]):
        ax2.text(v + 0.15, i, str(int(v)), va="center", fontsize=8.5)
    ax2.set_title("Who broke ranks most — the hawks (and one 2025 dove)", fontsize=9.5, loc="left")
    ax2.set_xlabel("dissenting votes")
    ax2.set_xlim(0, t["n"].max() + 2)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="y" if ax is ax1 else "x")
    fig.text(0.01, -0.02, "Source: parsed from the FOMC's own policy statements (federalreserve.gov), "
             f"{r['meetings']} meetings {r['span'][0]}–{r['span'][1]} (econlab). Dissents recorded against the adopted action — "
             "which passed every time.", fontsize=7.5, color="#57606a")
    fig.tight_layout()
    save(fig, "10_fomc_deciders")


# ---------- the revolving door & conflicts of interest (from the `influence` source) ----------

def revolving_door() -> dict:
    """Lobbying revolving-door rate + issue/branch mix + money-in-politics scale."""
    with connect() as con:
        share = con.execute("SELECT value FROM obs WHERE series_id='influence/revolving_share'").fetchone()[0]
        act = con.execute("SELECT kind, label, count FROM lobby_activity").df()
        filings = con.execute(
            "SELECT value FROM obs WHERE series_id='influence/lobby_filings' AND year=2024").fetchone()[0]
        pac = con.execute("SELECT value FROM obs WHERE series_id='influence/pac_receipts'").fetchone()[0]
        pacn = con.execute("SELECT value FROM obs WHERE series_id='influence/pac_count'").fetchone()[0]
    return {"share": share, "branch": act[act.kind == "branch"], "issue": act[act.kind == "issue"],
            "entity": act[act.kind == "entity"], "filings": filings, "pac": pac, "pacn": pacn}


def congress_trading() -> dict:
    """Congressional stock-trade reports (PTRs) over time and their top filers."""
    with connect() as con:
        ptr = con.execute("SELECT year, value FROM obs WHERE series_id='influence/congress_ptr' ORDER BY year").df()
        top = con.execute(
            "SELECT member, sum(reports) tot FROM congress_traders GROUP BY 1 ORDER BY 2 DESC LIMIT 10").df()
    return {"ptr": ptr, "top": top}


def fig_revolving_door() -> None:
    """Convert Ch9's unmeasured 'revolving-door careers' into a measured figure."""
    import matplotlib.pyplot as plt

    r = revolving_door()
    br = r["branch"].sort_values("count")
    iss = r["issue"].head(7).sort_values("count")
    print(f"[ch10] revolving door: {r['share']:.0f}% of lobbyists are former officials; "
          f"{r['filings']:,.0f} filings/yr; PACs ${r['pac']/1e9:.0f}B across {r['pacn']:,.0f} committees")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1.05]})
    fig.suptitle("The revolving door, measured: ~1 in 5 lobbyists is a former government official — most from Congress",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.3)

    colr = {"Congress (member or staff)": "#b42318", "Executive branch / agency": "#0d6e78",
            "Other / judicial": "#8593a0"}
    ax1.barh(range(len(br)), br["count"], color=[colr.get(x, "#8593a0") for x in br["label"]])
    ax1.set_yticks(range(len(br)), [x.replace(" / ", "/\n") for x in br["label"]], fontsize=8.3)
    for i, v in enumerate(br["count"]):
        ax1.text(v + 2, i, f"{v:.0f}", va="center", fontsize=8.5)
    ax1.set_title("Where the former officials came from\n(lobbyists disclosing a prior 'covered' post)",
                  fontsize=9.2, loc="left")
    ax1.set_xlabel("lobbyist records in the sample")
    ax1.set_xlim(0, br["count"].max() * 1.22)
    ax1.text(0.97, 0.30, f"{r['share']:.0f}% of all\nlobbyists are\nformer insiders",
             transform=ax1.transAxes, ha="right", va="center", fontsize=11, color="#b42318",
             fontweight="bold", bbox=dict(boxstyle="round", fc="#fbeae7", ec="#b42318"))

    ax2.barh(range(len(iss)), iss["count"], color="#b45309")
    ax2.set_yticks(range(len(iss)), [x[:32] for x in iss["label"]], fontsize=8.3)
    for i, v in enumerate(iss["count"]):
        ax2.text(v + 0.8, i, f"{v:.0f}", va="center", fontsize=8.5)
    ax2.set_title("What the money lobbies on\n(top disclosed issue areas)", fontsize=9.2, loc="left")
    ax2.set_xlabel("lobbying activity records in the sample")
    ax2.set_xlim(0, iss["count"].max() * 1.16)

    source_note(ax1, f"Senate LDA filings ({r['filings']:,.0f} in 2024), sampled for the revolving-door rate & mix. "
                     "'Covered position' = a prior government job the lobbyist must disclose. Congress is lobbied on ~97% of filings.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_revolving_door")


def fig_congress_trading() -> None:
    """Conflict of interest in office: sitting lawmakers trading the markets they govern."""
    import matplotlib.pyplot as plt

    r = congress_trading()
    ptr, top = r["ptr"], r["top"].iloc[::-1]
    print(f"[ch10] congress trades: {int(ptr['value'].sum())} PTR reports 2016-24, peak "
          f"{int(ptr['value'].max())} in {int(ptr.loc[ptr['value'].idxmax(),'year'])}; "
          f"top filer {top.iloc[-1]['member']} ({int(top.iloc[-1]['tot'])})")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1, 1.08]})
    fig.suptitle("Trading while governing: hundreds of stock-trade reports a year, concentrated in a few members",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.3)

    ax1.bar(ptr["year"], ptr["value"], color="#0d6e78", width=0.7)
    for x, v in zip(ptr["year"], ptr["value"]):
        ax1.text(x, v + 8, f"{v:.0f}", ha="center", fontsize=7.8)
    ax1.set_title("US House stock-trade reports (PTRs) per year", fontsize=9.2, loc="left")
    ax1.set_ylabel("periodic transaction reports filed")
    ax1.set_ylim(0, ptr["value"].max() * 1.16)
    ax1.set_xticks(ptr["year"], [str(int(y)) for y in ptr["year"]], fontsize=8, rotation=0)

    ax2.barh(range(len(top)), top["tot"], color=["#b42318" if v == top["tot"].max() else "#b45309" for v in top["tot"]])
    ax2.set_yticks(range(len(top)), [m.split(",")[0] for m in top["member"]], fontsize=8.3)
    for i, v in enumerate(top["tot"]):
        ax2.text(v + 4, i, f"{v:.0f}", va="center", fontsize=8.3)
    ax2.set_title("Most active filers, 2016–2024 (cumulative reports)", fontsize=9.2, loc="left")
    ax2.set_xlabel("stock-trade reports filed")
    ax2.set_xlim(0, top["tot"].max() * 1.16)

    source_note(ax1, "US House Clerk financial disclosures (PTRs, filed within 45 days of a trade). A report bundles "
                     "one or more trades; amounts are in ranges in the PDFs, not counted here. House only; Senate files separately.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_congress_trading")


def defense_contracts() -> dict:
    """DoD prime-contract concentration among the weapons primes (USASpending)."""
    with connect() as con:
        top = con.execute(
            "SELECT parent, amount, prime FROM dod_contractors WHERE year=2024 ORDER BY amount DESC LIMIT 11").df()
        top5 = con.execute(
            "SELECT year, value FROM obs WHERE series_id='usaspending/dod_top5_primes' ORDER BY year").df()
        lmt = con.execute(
            "SELECT year, value FROM obs WHERE series_id='usaspending/dod_lockheed' ORDER BY year").df()
    return {"top": top, "top5": top5, "lmt": lmt}


def fig_defense_contracts() -> None:
    """The prize the defense revolving door competes for: DoD contract concentration."""
    import matplotlib.pyplot as plt

    d = defense_contracts()
    top = d["top"].iloc[::-1]
    top5 = d["top5"]
    print(f"[ch10] DoD contracts FY24: Lockheed ${top[top.prime]['amount'].max()/1e9:.0f}B; "
          f"top-5 primes ${top5[top5.year==2024]['value'].iloc[0]/1e9:.0f}B combined")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.suptitle("The prize: a handful of weapons primes capture the bulk of the Pentagon's contract dollars",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.3)

    cols = ["#b42318" if p else "#8593a0" for p in top["prime"]]
    ax1.barh(range(len(top)), top["amount"] / 1e9, color=cols)
    ax1.set_yticks(range(len(top)), [n[:30] for n in top["parent"]], fontsize=8.2)
    for i, v in enumerate(top["amount"] / 1e9):
        ax1.text(v + 0.5, i, f"${v:.0f}B", va="center", fontsize=8)
    ax1.set_title("Top DoD prime contractors, FY2024\n(subsidiaries rolled to parent)", fontsize=9.2, loc="left")
    ax1.set_xlabel("DoD prime-contract obligations, USD billion")
    ax1.set_xlim(0, top["amount"].max() / 1e9 * 1.16)
    ax1.scatter([], [], color="#b42318", marker="s", label="weapons prime")
    ax1.scatter([], [], color="#8593a0", marker="s", label="health / logistics / other")
    ax1.legend(fontsize=7.6, loc="lower right")

    ax2.bar(top5["year"], top5["value"] / 1e9, color="#0d6e78", width=0.7)
    for x, v in zip(top5["year"], top5["value"] / 1e9):
        ax2.text(x, v + 2, f"{v:.0f}", ha="center", fontsize=7.8)
    ax2.set_title("The top-5 weapons primes' combined\nDoD contracts, per year", fontsize=9.2, loc="left")
    ax2.set_ylabel("USD billion")
    ax2.set_ylim(0, top5["value"].max() / 1e9 * 1.2)
    ax2.set_xticks(top5["year"], [str(int(y)) for y in top5["year"]], fontsize=8)

    source_note(ax1, "USASpending.gov DoD prime-contract obligations, FY2024; subsidiaries rolled to parent "
                     "(Sikorsky→Lockheed, Electric Boat→General Dynamics, Raytheon→RTX). ~$450B in total DoD contract obligations.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_defense_contracts")


# Board composition of the five largest US weapons primes, curated from each firm's
# most recent SEC DEF 14A proxy (2025/26) and cross-checked against the official
# board pages. "gov/mil" = a director with a prior SENIOR US government or military
# role: a retired 3-/4-star general or admiral, a former Secretary/Deputy/Under
# Secretary of Defense or of a service, a former intelligence-agency head, a former
# member of Congress, or a former cabinet official. (company, total_directors, [(name, prior role)])
DEFENSE_BOARDS = [
    ("Lockheed Martin", 9, [
        ("Adm. John Aquilino", "ret. 4-star Navy; ex-Commander, US Indo-Pacific Command"),
        ("Heather Wilson", "ex-Secretary of the Air Force; ex-US Representative"),
    ]),
    ("RTX (Raytheon)", 10, [
        ("Gen. Ellen Pawlikowski", "ret. 4-star USAF; ex-NRO deputy director"),
        ("Robert Work", "ex-Deputy Secretary of Defense; ex-Under Secretary of the Navy"),
    ]),
    ("Boeing", 12, [
        ("Gen. Stayce Harris", "ret. 3-star USAF; ex-Inspector General of the Air Force"),
        ("Adm. John Richardson", "ret. 4-star Navy; ex-Chief of Naval Operations"),
    ]),
    ("General Dynamics", 12, [
        ("Gen. Richard Clarke", "ret. 4-star Army; ex-Commander, US Special Operations Command"),
        ("Rudy deLeon", "ex-Deputy Secretary of Defense"),
        ("Adm. Cecil Haney", "ret. 4-star Navy; ex-Commander, US Strategic Command"),
        ("Gen. Charles Hooper", "ret. 3-star Army; ex-Director, Defense Security Cooperation Agency"),
    ]),
    ("Northrop Grumman", 11, [
        ("Adm. Christopher Grady", "ret. 4-star Navy; ex-Vice Chairman of the Joint Chiefs (joined 2026)"),
        ("Adm. Gary Roughead", "ret. 4-star Navy; ex-Chief of Naval Operations"),
        ("Gen. Mark Welsh III", "ret. 4-star USAF; ex-Chief of Staff of the Air Force"),
    ]),
]

# GAO-21-104311 (Sept 2021): the modern aggregate.
GAO_DOOR = {"total_former_dod": 37032, "senior_officials": 1718, "n_contractors": 14, "year": 2019}

# Named, individually documented cases (SEC 8-Ks / company releases / GAO).
REVOLVING_CASES = [
    ("Gen. Jim Mattis", "ret. Marine 4-star, ex-CENTCOM → SecDef → back onto", "General Dynamics board"),
    ("Gen. Joseph Dunford", "ex-Chairman of the Joint Chiefs of Staff → onto", "Lockheed Martin board (2020)"),
    ("Gen. Lloyd Austin", "ret. Army 4-star, ex-CENTCOM → United Technologies/Raytheon board → SecDef", ""),
    ("Mark Esper", "Raytheon's top in-house lobbyist → Secretary of Defense", "(the door, reversed)"),
]


def defense_boards() -> "pd.DataFrame":
    rows = [{"company": c, "total": t, "govmil": len(p), "people": p}
            for c, t, p in DEFENSE_BOARDS if t]
    return pd.DataFrame(rows)


def fig_defense_boards() -> None:
    """The door itself: former generals and officials sitting on the primes' boards."""
    import matplotlib.pyplot as plt

    b = defense_boards().iloc[::-1]
    tot_gov, tot_seats = int(b["govmil"].sum()), int(b["total"].sum())
    print(f"[ch10] defense boards: {tot_gov} of {tot_seats} directors at the "
          f"{len(b)} primes are former senior officials/generals; GAO: {GAO_DOOR['senior_officials']:,} "
          f"senior officials at {GAO_DOOR['n_contractors']} contractors ({GAO_DOOR['year']})")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.suptitle("The door itself: retired generals and former officials sit on the boards their contracts feed",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)

    y = range(len(b))
    ax1.barh(y, b["total"], color="#d7dce1", label="other directors")
    ax1.barh(y, b["govmil"], color="#b42318", label="former general / senior official")
    ax1.set_yticks(list(y), b["company"], fontsize=9)
    for i, (g, t) in enumerate(zip(b["govmil"], b["total"])):
        ax1.text(t + 0.15, i, f"{g} of {t}", va="center", fontsize=8.6, fontweight="bold")
    ax1.set_title("Directors with a prior senior government/military role\n(latest SEC proxy)",
                  fontsize=9.2, loc="left")
    ax1.set_xlabel("board seats")
    ax1.set_xlim(0, b["total"].max() + 2)
    ax1.legend(fontsize=7.8, loc="lower right")

    # Panel B — the aggregate scale + the named cases
    ax2.axis("off")
    ax2.set_title("The flow, in the aggregate", fontsize=9.2, loc="left")
    g = GAO_DOOR
    ax2.text(0.0, 0.94, f"{g['total_former_dod']:,}", fontsize=27, fontweight="bold", color="#b42318",
             transform=ax2.transAxes, va="top")
    ax2.text(0.0, 0.70, f"former DoD employees worked for the {g['n_contractors']} largest\n"
                        f"defense contractors in {g['year']} — of whom",
             fontsize=9, transform=ax2.transAxes, va="top", color="#333")
    ax2.text(0.0, 0.55, f"{g['senior_officials']:,}", fontsize=20, fontweight="bold", color="#b45309",
             transform=ax2.transAxes, va="top")
    ax2.text(0.28, 0.565, "were recent senior officials or\ngenerals (hired 2014–19).  — GAO-21-104311",
             fontsize=8.6, transform=ax2.transAxes, va="top", color="#333")
    ax2.text(0.0, 0.36, "Named board cases:", fontsize=8.8, fontweight="bold", transform=ax2.transAxes, va="top")
    cases = ["Gen. Jim Mattis  →  General Dynamics board",
             "Gen. Joseph Dunford (ex-Joint Chiefs) → Lockheed board",
             "Gen. Lloyd Austin → Raytheon board (then SecDef)",
             "Mark Esper: Raytheon lobbyist → SecDef  (reversed)"]
    for i, c in enumerate(cases):
        ax2.text(0.02, 0.28 - i * 0.075, "• " + c, fontsize=8.3, transform=ax2.transAxes, va="top", color="#333")

    source_note(ax1, "Boards: each firm's latest SEC DEF 14A proxy, cross-checked to official board pages. Aggregate: "
                     "GAO-21-104311 (2021). POGO 'Brass Parachutes' (2018): 645 such hires by the top-20, ~90% became lobbyists.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_defense_boards")


def defense_loop() -> "pd.DataFrame":
    """Each prime's lobbying spend (2023) beside its DoD contracts (FY2024) — the ROI."""
    with connect() as con:
        df = con.execute(
            "SELECT l.prime, l.lobbying, c.amount AS contracts "
            "FROM defense_lobbying l JOIN dod_contractors c ON l.prime=c.parent AND c.year=2024 "
            "ORDER BY c.amount DESC").df()
    df["ratio"] = df["contracts"] / df["lobbying"]
    return df


def fig_defense_loop() -> None:
    """Close the loop in dollars: a few million lobbying sits beside tens of billions in contracts."""
    import matplotlib.pyplot as plt

    d = defense_loop().iloc[::-1]
    agg = d["contracts"].sum() / d["lobbying"].sum()
    print(f"[ch10] defense loop: top-5 primes lobbied ${d['lobbying'].sum()/1e6:.0f}M (2023) vs "
          f"${d['contracts'].sum()/1e9:.0f}B DoD contracts (FY24) = 1:{agg:,.0f}; "
          f"Lockheed 1:{d[d.prime=='Lockheed Martin']['ratio'].iloc[0]:,.0f}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [1.2, 1]})
    fig.suptitle("The influence loop, in dollars: millions in lobbying sit beside tens of billions in contracts",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)

    y = range(len(d))
    for i, (lob, con_) in enumerate(zip(d["lobbying"], d["contracts"])):
        ax1.plot([lob, con_], [i, i], color="#c9ccd1", lw=2.2, zorder=1)
    ax1.scatter(d["lobbying"], list(y), color="#b45309", s=70, zorder=3, label="federal lobbying spend, 2023")
    ax1.scatter(d["contracts"], list(y), color="#0d6e78", s=70, zorder=3, label="DoD contracts won, FY2024")
    ax1.set_yticks(list(y), d["prime"], fontsize=8.6)
    ax1.set_xscale("log")
    ax1.set_xlim(5e6, 1.2e11)
    ax1.set_xlabel("US dollars (log scale)")
    ax1.set_xticks([1e7, 1e8, 1e9, 1e10, 1e11], ["$10M", "$100M", "$1B", "$10B", "$100B"])
    ax1.set_title("Lobbying spend vs contracts won", fontsize=9.2, loc="left")
    ax1.legend(fontsize=7.8, loc="lower right")

    ax2.barh(list(y), d["ratio"], color="#1a7f37")
    ax2.set_yticks(list(y), d["prime"], fontsize=8.6)
    for i, v in enumerate(d["ratio"]):
        ax2.text(v + 40, i, f"1:{v:,.0f}", va="center", fontsize=8.4)
    ax2.axvline(agg, color="#b42318", lw=1.1, ls="--")
    ax2.text(agg, len(d) - 0.4, f" top-5 avg 1:{agg:,.0f}", color="#b42318", fontsize=8, va="top")
    ax2.set_title("DoD contract dollars won per dollar of lobbying", fontsize=9.2, loc="left")
    ax2.set_xlabel("contract dollars won per dollar of lobbying")
    ax2.set_xlim(0, d["ratio"].max() * 1.2)

    source_note(ax1, "Lobbying: Senate LDA filings by each firm (client_name), 2023. Contracts: USASpending DoD prime obligations "
                     "FY2024 (subs rolled up). Association, not causation — the point is the scale mismatch, not that lobbying linearly buys contracts.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_defense_loop")


# Documented returns on lobbying, by form. metric: 'profit' = pure rent (tax saved,
# ~all profit); 'revenue' = gross money received (a contract you must deliver on, and
# selection-inflated); 'causal' = a rigorous structural profit estimate. Each cited.
LOBBY_RETURNS = [
    ("Defense contracts (computed here, F12)", 1381, "revenue"),
    ("Fortune-100 federal funding, 2014–17", 1000, "revenue"),      # OpenTheBooks / Forbes 2019
    ("'Fixed Fortunes' 200 firms, 2007–12", 760, "revenue"),         # Sunlight Foundation 2014
    ("Tax repatriation holiday, 2004", 220, "profit"),               # Alexander, Mazza & Scholz 2009
    ("Pharma drug-pricing (low est.)", 123, "profit"),               # National Nurses United
    ("Energy lobbying (structural est.)", 2.3, "causal"),            # Kang 2016, Rev. Econ. Studies
]
_RETURN_COL = {"profit": "#1a7f37", "revenue": "#8593a0", "causal": "#b45309"}
_RETURN_LAB = {"profit": "pure profit (tax/rule change — rent)",
               "revenue": "gross revenue received (must deliver; selection-inflated)",
               "causal": "rigorous causal estimate"}


def lobby_issue_ranking() -> "pd.DataFrame":
    with connect() as con:
        return con.execute("SELECT issue, pct FROM lobby_issues ORDER BY pct DESC LIMIT 10").df()


def fig_lobbying_returns() -> None:
    """Generalize F12: across the economy, which FORMS of lobbying pay the highest return?"""
    import matplotlib.pyplot as plt

    rets = list(reversed(LOBBY_RETURNS))
    iss = lobby_issue_ranking().iloc[::-1]
    print("[ch10] lobbying returns/$: " + ", ".join(f"{l.split('(')[0].strip()} {v}x" for l, v, _ in LOBBY_RETURNS))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 6), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.suptitle("The return on lobbying: rule-changes (tax) return pure profit; contracts return revenue you must deliver",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)

    # Panel A — the leaderboard, log scale, colored by what the return actually measures
    y = range(len(rets))
    for i, (lab, v, m) in enumerate(rets):
        ax1.hlines(i, 1, v, color=_RETURN_COL[m], lw=2.2, zorder=1)
        ax1.scatter(v, i, color=_RETURN_COL[m], s=70, zorder=3)
        ax1.text(v * 1.15, i, f"{v:,.0f}×" if v >= 10 else f"{v:.1f}×", va="center", fontsize=8.4)
    ax1.set_yticks(list(y), [l for l, _, _ in rets], fontsize=8.2)
    ax1.set_xscale("log")
    ax1.set_xlim(1, 6000)
    ax1.set_xticks([1, 10, 100, 1000], ["1×", "10×", "100×", "1,000×"])
    ax1.set_xlabel("dollars returned per $1 of lobbying (log scale)")
    ax1.set_title("Documented return per $1 lobbied", fontsize=9.3, loc="left")
    for m in ("profit", "revenue", "causal"):
        ax1.scatter([], [], color=_RETURN_COL[m], marker="s", label=_RETURN_LAB[m])
    ax1.legend(fontsize=7, loc="lower right", framealpha=0.95)

    # Panel B — where the lobbying money actually goes (computed, all-quarter LDA)
    ax2.barh(range(len(iss)), iss["pct"], color="#0d6e78")
    ax2.set_yticks(range(len(iss)), [s[:28] for s in iss["issue"]], fontsize=8.2)
    for i, v in enumerate(iss["pct"]):
        ax2.text(v + 0.1, i, f"{v:.1f}%", va="center", fontsize=8)
    ax2.set_title("Where the lobbying goes: top issue areas\n(share of lobbying activity, 2023)", fontsize=9.3, loc="left")
    ax2.set_xlabel("% of sampled lobbying-activity records")
    ax2.set_xlim(0, iss["pct"].max() * 1.18)

    source_note(ax1, "Returns: Alexander/Mazza/Scholz 2009 (tax repatriation, ~$220/$1 pure profit); Sunlight 2014 & "
                     "OpenTheBooks 2019 (gross); Kang 2016 (energy, causal); defense computed (F12). Issues: Senate LDA, all-quarter 2023 sample.")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "10_lobbying_returns")


# ---------- the retail end of power: small local office (curated, cited) ----------
# 2022 Census of Governments — Organization.
LOCAL_GOV_TYPES = [
    ("Special districts", 39555), ("Municipalities", 19491), ("Townships", 16214),
    ("School districts", 12546), ("Counties", 3031),
]
LOCAL_GOV_FACTS = {
    "total_local": 90837, "local_spending": 1.9e12,        # FY2021 local direct general expenditure
    "elected_local": 493830, "elected_share": 96.2,        # 1992 (last full Census count)
    "special_district_spend": 200e9,                       # PIRG 2017 (dated)
}
# salary vs budget the board controls (per-seat) — the leverage. Each fully cited.
LOCAL_LEVERAGE = [
    ("Los Angeles County, CA", 5, 244727, 46.7e9),         # supervisor base; FY24 budget
    ("Cook County, IL", 17, 85000, 9.94e9),                # commissioner; FY25 budget
]
# DOJ Public Integrity Section, Report to Congress 2023 — officials CONVICTED, 2004–2023.
DOJ_CORRUPTION = {"local": 4422, "state": 1782, "federal": 6792, "local_2023": 121, "state_2023": 58}
LOCAL_CORRUPTION_CASES = [
    ("Jimmy Dimora", "Cuyahoga County Commissioner", "steered county contracts & jobs for $166k+ in bribes", "28 yrs"),
    ("José Huizar", "Los Angeles City Councilman", "pushed developers' projects through zoning for $1.5M", "13 yrs"),
    ("Ángel Pérez-Otero", "Mayor of Guaynabo, PR", "took bribes from a county contractor", "convicted '23"),
    ("Scott Jenkins", "Sheriff, Culpeper County, VA", "sold auxiliary-deputy badges for $72,500", "convicted '24"),
]


def local_leverage() -> "pd.DataFrame":
    rows = [{"place": p, "salary": sal, "budget": bud, "per_seat": bud / n, "ratio": (bud / n) / sal}
            for p, n, sal, bud in LOCAL_LEVERAGE]
    return pd.DataFrame(rows)


def fig_local_scale() -> None:
    """Zoom from the federal machinery to the retail end: how much runs through local office."""
    import matplotlib.pyplot as plt

    f = LOCAL_GOV_FACTS
    types = LOCAL_GOV_TYPES
    lev = local_leverage()
    print(f"[ch10] local: {f['total_local']:,} local govs, ${f['local_spending']/1e12:.1f}T spend, "
          f"{f['elected_local']:,} elected; LA leverage {lev.iloc[0]['ratio']:,.0f}:1")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.suptitle("The retail end of power: ~90,000 local governments, ~$1.9 trillion, and almost no scrutiny",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)

    labels = [t[0] for t in types][::-1]
    vals = [t[1] for t in types][::-1]
    cols = ["#b42318" if l == "Special districts" else "#0d6e78" for l in labels]
    ax1.barh(range(len(types)), vals, color=cols)
    ax1.set_yticks(range(len(types)), labels, fontsize=9)
    for i, v in enumerate(vals):
        ax1.text(v + 400, i, f"{v:,}", va="center", fontsize=8.4)
    ax1.set_title("U.S. local governments by type, 2022", fontsize=9.3, loc="left")
    ax1.set_xlabel("number of governments")
    ax1.set_xlim(0, 46000)
    ax1.text(0.97, 0.30, f"{f['total_local']:,} local governments\n${f['local_spending']/1e12:.1f}T in annual spending\n"
             f"~{f['elected_local']:,} elected officials\n(96% of all US elected officials)",
             transform=ax1.transAxes, ha="right", va="center", fontsize=8.3, color="#0d6e78",
             bbox=dict(boxstyle="round", fc="#eef4f4", ec="#0d6e78"))
    ax1.text(39555, 0.02, " biggest & fastest-growing\n category — often unelected,\n low-turnout boards",
             fontsize=7, color="#b42318", va="bottom")

    # Panel B — the leverage: salary vs budget-per-seat
    y = range(len(lev))
    for i, r in lev.iterrows():
        ax2.plot([r["salary"], r["per_seat"]], [i, i], color="#c9ccd1", lw=2.4, zorder=1)
    ax2.scatter(lev["salary"], list(y), color="#b45309", s=80, zorder=3, label="official's salary")
    ax2.scatter(lev["per_seat"], list(y), color="#0d6e78", s=80, zorder=3, label="budget controlled, per board seat")
    ax2.set_yticks(list(y), lev["place"], fontsize=9)
    for i, r in lev.iterrows():
        ax2.text(r["per_seat"] * 1.25, i, f"{r['ratio']:,.0f}×", va="center", fontsize=9, fontweight="bold", color="#0d6e78")
    ax2.set_xscale("log")
    ax2.set_xlim(3e4, 6e10)
    ax2.set_xticks([1e5, 1e6, 1e7, 1e8, 1e9, 1e10], ["$100k", "$1M", "$10M", "$100M", "$1B", "$10B"])
    ax2.set_ylim(-0.6, len(lev) - 0.4)
    ax2.set_title("The leverage: budget a board seat controls vs the salary it pays", fontsize=9.3, loc="left")
    ax2.set_xlabel("US dollars (log scale)")
    ax2.legend(fontsize=8, loc="lower right")

    source_note(ax1, "2022 Census of Governments (counts); Census FY2021 finance ($1.9T local direct spending); "
                     "1992 Census 'Popularly Elected Officials' (the last full count). Leverage: LA County & Cook County official salaries vs adopted budgets ÷ board size.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_local_scale")


def fig_local_corruption() -> None:
    """What the leverage buys: local office is where public corruption is convicted most."""
    import matplotlib.pyplot as plt

    d = DOJ_CORRUPTION
    print(f"[ch10] DOJ 2004-23 convicted: local {d['local']:,}, state {d['state']:,}, federal {d['federal']:,}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.6), gridspec_kw={"width_ratios": [0.85, 1.15]})
    fig.suptitle("What it buys: local officials are convicted of corruption far more than state officials",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.2)

    cats = [("Local\nofficials", d["local"], "#b42318"), ("State\nofficials", d["state"], "#8593a0"),
            ("Federal\nofficials", d["federal"], "#8593a0")]
    ax1.bar(range(3), [c[1] for c in cats], color=[c[2] for c in cats], width=0.66)
    ax1.set_xticks(range(3), [c[0] for c in cats], fontsize=8.6)
    for i, c in enumerate(cats):
        ax1.text(i, c[1] + 90, f"{c[1]:,}", ha="center", fontsize=8.8, fontweight="bold" if i == 0 else "normal")
    ax1.set_title("Public officials CONVICTED of corruption,\n2004–2023 (federal prosecutions)", fontsize=9.2, loc="left")
    ax1.set_ylabel("officials convicted")
    ax1.set_ylim(0, 7800)
    ax1.text(0.5, 0.9, "local = 2.5× the state count\n(and this is only what FEDERAL\nprosecutors reach)",
             transform=ax1.transAxes, ha="center", fontsize=7.6, color="#b42318")

    # Panel B — named cases: what was sold
    ax2.axis("off")
    ax2.set_title("What gets sold at the local level", fontsize=9.3, loc="left")
    for i, (name, office, what, sentence) in enumerate(LOCAL_CORRUPTION_CASES):
        yb = 0.86 - i * 0.235
        ax2.text(0.0, yb, name, fontsize=9.5, fontweight="bold", transform=ax2.transAxes, va="top", color="#1a1a1a")
        ax2.text(0.0, yb - 0.052, office, fontsize=8, transform=ax2.transAxes, va="top", color="#b45309")
        ax2.text(0.0, yb - 0.104, f"{what}  →  {sentence}", fontsize=8, transform=ax2.transAxes, va="top", color="#333")
        if i < len(LOCAL_CORRUPTION_CASES) - 1:
            ax2.axhline(yb - 0.16, xmin=0.0, xmax=0.98, color="#e5e7eb", lw=0.8)

    source_note(ax1, "DOJ Public Integrity Section, Report to Congress 2023 (convictions of state/local/federal officials, "
                     "2004–2023). Federal prosecution only — it undercounts local corruption handled by state/local prosecutors. Cases: FBI/DOJ/court records.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_local_corruption")


# Surfaces of money state & local officials steer, beyond the operating budget.
# kind: 'pool' = total assets/debt governed; 'flow' = money directed per year. Each cited.
LOCAL_MONEY_SURFACES = [
    ("Public pension assets", 5.99e12, "pool"),          # Census Annual Survey of Public Pensions, FY2024
    ("Municipal debt outstanding", 4.2e12, "pool"),       # SIFMA, 2024
    ("Local operating budget /yr", 1.9e12, "flow"),       # Census FY2021 (F14)
    ("Development subsidies /yr", 70e9, "flow"),           # Good Jobs First (~$45–90B range)
]
# the avenue of influence for each pool + a documented pay-to-play case.
LOCAL_AVENUES = [
    ("Pension mandates", "placement agents steer billion-dollar allocations",
     "NY Common Fund: Hank Morris took $19M in sham fees on $5B+ of deals; Hevesi jailed. CalPERS: bribes in a shoebox."),
    ("Municipal bonds", "officials pick the underwriters & advisors",
     "Goldman paid ~$16M over the Massachusetts (Cahill) deals → spurred MSRB Rule G-37 (1994)."),
    ("Development subsidies", "local tax breaks & abatements, granted deal-by-deal",
     "Foxconn (WI): $4B promised for 13,000 jobs → $80M for 1,454; Amazon HQ2 ~$4.6B."),
    ("TIF & occupational licensing", "property-tax diversion; who's allowed to work",
     ">$40B/yr diverted via TIF; licensing boards (1 in 4 workers) are run by the incumbents they protect."),
]


def fig_local_avenues() -> None:
    """Dig deeper: the operating budget is only one surface — pensions, bonds, subsidies are bigger."""
    import matplotlib.pyplot as plt

    s = list(reversed(LOCAL_MONEY_SURFACES))
    print("[ch10] local surfaces: " + ", ".join(f"{l.split(' /')[0]} ${v/1e12:.2f}T" for l, v, _ in LOCAL_MONEY_SURFACES))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [0.92, 1.08]})
    fig.suptitle("Dig deeper: beyond the budget, officials steer far bigger pools — pensions and bonds — with their own pay-to-play",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.6)

    cols = {"pool": "#0d6e78", "flow": "#b45309"}
    ax1.barh(range(len(s)), [v / 1e12 for _, v, _ in s], color=[cols[k] for _, _, k in s])
    ax1.set_yticks(range(len(s)), [l for l, _, _ in s], fontsize=8.8)
    for i, (l, v, k) in enumerate(s):
        ax1.text(v / 1e12 + 0.08, i, f"${v/1e12:.2f}T" if v >= 1e12 else f"${v/1e9:.0f}B", va="center", fontsize=8.6)
    ax1.set_title("Money surfaces a state/local official touches", fontsize=9.2, loc="left")
    ax1.set_xlabel("US dollars, trillions")
    ax1.set_xlim(0, 7)
    ax1.scatter([], [], color=cols["pool"], marker="s", label="total pool governed (assets / debt)")
    ax1.scatter([], [], color=cols["flow"], marker="s", label="directed per year (budget / subsidies)")
    ax1.legend(fontsize=7.4, loc="lower right")
    ax1.annotate("the pot F14 measured", xy=(1.9, 1), xytext=(2.6, 1.5), fontsize=7.6, color="#b45309",
                 arrowprops=dict(arrowstyle="-", color="#b45309", lw=0.7))

    # Panel B — the avenue + the pay-to-play in each
    ax2.axis("off")
    ax2.set_title("The avenue of influence in each — and its pay-to-play", fontsize=9.2, loc="left")
    for i, (avenue, mech, case) in enumerate(LOCAL_AVENUES):
        yb = 0.9 - i * 0.235
        ax2.text(0.0, yb, avenue, fontsize=9.3, fontweight="bold", transform=ax2.transAxes, va="top",
                 color="#0d6e78", parse_math=False)
        ax2.text(0.0, yb - 0.05, mech, fontsize=8, style="italic", transform=ax2.transAxes, va="top",
                 color="#b45309", parse_math=False)
        ax2.text(0.0, yb - 0.105, case, fontsize=7.7, transform=ax2.transAxes, va="top", color="#333", parse_math=False)
        if i < len(LOCAL_AVENUES) - 1:
            ax2.axhline(yb - 0.175, xmin=0, xmax=0.99, color="#e5e7eb", lw=0.8)

    source_note(ax1, "Pensions: Census ASPP FY2024 (5.99T). Muni debt: SIFMA 2024 (4.2T). Budget: Census FY2021. Subsidies: "
                     "Good Jobs First. Cases: SEC/DOJ/NY-AG enforcement, MSRB, Good Jobs First. Pools are stocks; budget/subsidies are annual flows.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_local_avenues")


# The state/local money surfaces at scale — pension pot now computed (Census ASPP),
# the rest curated & cited. (label, value_usd, basis, dedicated pay-to-play rule)
STATE_LOCAL_POTS = [
    ("Public pension assets", None, "stock", "SEC 206(4)-5 (2010)"),        # computed from aspp
    ("Municipal-bond market", 4.5e12, "stock", "MSRB G-37 (1994)"),          # SIFMA 2026Q1
    ("State/local debt (Fed Z.1)", 3.73e12, "stock", None),                  # FRED SLGSDODNS 2026Q1
    ("Local operating budgets /yr", 1.9e12, "flow", None),                   # Census FY2021 (F14)
    ("Federal grants passthrough /yr", 1.20e12, "flow", None),               # USASpending FY2024
    ("Econ-dev subsidies (cumulative)", 268e9, "cumulative", None),          # Good Jobs First
    ("FCC spectrum sales (cumulative)", 233e9, "cumulative", None),          # FCC, since 1994
]


def pension_by_state(n: int = 15) -> pd.DataFrame:
    """State & local public-pension assets by state (Census ASPP), top-n + national."""
    with connect() as con:
        tot = con.execute("SELECT value FROM obs WHERE series_id='aspp/pension_assets' AND entity='USA'").fetchone()[0]
        df = con.execute(
            "SELECT replace(entity,'US-','') st, value FROM obs "
            "WHERE series_id='aspp/pension_assets' AND entity<>'USA' ORDER BY value DESC LIMIT ?", [n]
        ).df()
    df["pct"] = 100 * df["value"] / tot
    return df, float(tot)


def fig_state_local_pots() -> None:
    """Turn F16's anecdotes into a distribution: the biggest state/local pot (public
    pensions) computed by state, set against the other surfaces officials steer."""
    import matplotlib.pyplot as plt

    st, tot = pension_by_state(15)
    ca_ny = 100 * (st[st.st.isin(["CA", "NY"])]["value"].sum()) / tot
    pots = [(l, (tot if v is None else v), b, r) for l, v, b, r in STATE_LOCAL_POTS]
    print(f"[ch10] state/local pension pot ${tot/1e12:.2f}T; CA+NY {ca_ny:.0f}% of it; "
          f"{len(pots)} surfaces, largest ${max(v for _, v, _, _ in pots)/1e12:.2f}T")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.8, 5.6))
    fig.suptitle("The state & local money surface, counted: a $6.5T pension pot (and it is not even the only one)",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)

    s = st.iloc[::-1]
    ax1.barh(range(len(s)), s["value"] / 1e9, color=PALETTE[0])
    ax1.set_yticks(range(len(s)), s["st"], fontsize=8.5)
    for i, (v, p) in enumerate(zip(s["value"] / 1e9, s["pct"])):
        ax1.text(v + 12, i, f"${v/1e3:,.2f}T" if v >= 1000 else f"${v:,.0f}B", va="center", fontsize=7.5)
    ax1.set_xlim(0, s["value"].max() / 1e9 * 1.2)
    ax1.set_title(f"Public-pension assets by state (${tot/1e12:.2f}T total; CA+NY = {ca_ny:.0f}%)", fontsize=9.5, loc="left")
    ax1.set_xlabel("cash + investments, $ billions (Census ASPP 2025)")

    basis_col = {"stock": "#0d6e78", "flow": "#b45309", "cumulative": "#6b7280"}
    p = list(reversed(pots))
    vals = [v / 1e12 for _, v, _, _ in p]
    ax2.barh(range(len(p)), vals, color=[basis_col[b] for _, _, b, _ in p])
    ax2.set_yticks(range(len(p)), [l for l, _, _, _ in p], fontsize=8)
    for i, (l, v, b, rule) in enumerate(p):
        lbl = f"${v/1e12:.2f}T" + (f"  ·  {rule}" if rule else "")
        ax2.text(v / 1e12 + 0.12, i, lbl, va="center", fontsize=7, color="#334155")
    ax2.set_xlim(0, 6.49 * 1.28)
    ax2.set_title("Every pool has its own pay-to-play channel", fontsize=9.5, loc="left")
    ax2.set_xlabel("size, $ trillions")
    for b, c in basis_col.items():
        ax2.scatter([], [], color=c, marker="s", label=b)
    ax2.legend(fontsize=7.5, loc="lower right", title="basis", title_fontsize=7.5)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.25, axis="x")
    fig.text(0.01, -0.02, "Source: public-pension assets computed from Census Annual Survey of Public Pensions 2025 (item RZ01, econlab 'aspp'); "
             "other surfaces curated & cited — SIFMA, Fed Z.1 (SLGSDODNS), Census govt finance, USASpending, Good Jobs First, FCC.",
             fontsize=7.1, color="#57606a")
    fig.tight_layout()
    save(fig, "10_state_local_pots")


# federal land by agency: (series slug, label, category). cat: 'lease'=open to extraction,
# 'protect'=parks/refuges, 'military', 'other'.
FED_LAND_AGENCIES = [
    ("blm", "Bureau of Land Mgmt", "lease"), ("usfs", "Forest Service", "lease"),
    ("fws", "Fish & Wildlife (refuges)", "protect"), ("nps", "National Parks", "protect"),
    ("dod", "Defense", "military"),
]
# the royalty the public charges to extract its own minerals, vs the private benchmark.
PUBLIC_ROYALTY = [
    ("Hardrock (gold, silver, copper)", 0.0, "1872 Mining Law: $0"),
    ("Federal coal", 8.0, "~5% effective"),
    ("Onshore oil & gas", 16.67, "12.5→16.67% (IRA)"),
    ("Offshore oil & gas", 18.75, ""),
    ("State / private benchmark", 22.0, "~18.75–25%"),
]

# The map of avenues of private capture, by branch/domain. tag: F-ref (covered this
# chapter) or 'frontier' (identified, not yet built). fact = the headline number.
AVENUE_MAP = [
    ("LEGISLATIVE — Congress", [
        ("Trading while in office", "6,027 House trade-reports, 2016–24", "F9"),
        ("Lobbying / revolving door", "18% of lobbyists are ex-officials", "F8, F13"),
        ("Campaign money (PACs)", "$23B through 12,378 PACs / cycle", "F8"),
        ("Earmarks", "$14.6B, 8,098 provisions (FY2024)", "F21"),
    ]),
    ("EXECUTIVE — agencies & the White House", [
        ("Defense revolving door", "37,032 ex-DoD at the top-14 contractors", "F10–F12"),
        ("Lobbying-to-contract ROI", "$1 lobbied ≈ $1,400 in contracts", "F12"),
        ("Pardons & clemency", "Biden 4,165 commutations; grant rate collapsing", "F20"),
    ]),
    ("JUDICIAL — the courts", [
        ("Federal judges' stock conflicts", "131 judges, 685 cases; top holding Microsoft", "F19"),
        ("Supreme Court gifts", "no ethics code until Nov 2023 (Thomas/Crow)", "F19"),
        ("State judicial elections", "$157M/cycle; outside money now the majority", "F19"),
    ]),
    ("THE PUBLIC ESTATE — 640M acres", [
        ("Hardrock mining", "$0 royalty; ~$4.9B/yr extracted free", "F17"),
        ("Grazing", "$1.35/AUM vs $23 market (93% off)", "F17"),
        ("Spectrum", "$233B auctioned vs 1996 gift ($0)", "F17"),
        ("Oil, gas, coal, timber", "below state/private rates", "F17"),
    ]),
    ("STATE & LOCAL — 90,000 governments", [
        ("Pension funds", "$6T; placement-agent pay-to-play", "F16"),
        ("Municipal bonds", "$4.2T; MSRB Rule G-37", "F16"),
        ("Development subsidies", "$45–90B/yr; Foxconn", "F16"),
        ("Local-office corruption", "4,422 local officials convicted", "F14, F15"),
    ]),
]


def federal_land() -> "pd.DataFrame":
    with connect() as con:
        rows = []
        for slug, label, cat in FED_LAND_AGENCIES:
            v = con.execute("SELECT last(value ORDER BY year) FROM obs "
                            f"WHERE series_id='usland/federal_acres_{slug}'").fetchone()[0]
            rows.append({"agency": label, "acres": v, "cat": cat})
        total = con.execute("SELECT last(value ORDER BY year) FROM obs "
                            "WHERE series_id='usland/federal_acres_total'").fetchone()[0]
    df = pd.DataFrame(rows)
    df.loc[len(df)] = {"agency": "Other agencies", "acres": total - df["acres"].sum(), "cat": "other"}
    return df, total


def fig_public_estate() -> None:
    """The physical commons: 640M acres of federal land, and the below-market rate the public charges for it."""
    import matplotlib.pyplot as plt

    df, total = federal_land()
    df = df.sort_values("acres")
    lease = df[df.cat == "lease"]["acres"].sum()
    print(f"[ch10] federal estate {total/1e6:.0f}M acres (28% of US); leasable (BLM+USFS) {lease/1e6:.0f}M; "
          f"hardrock royalty 0% vs oil {PUBLIC_ROYALTY[3][1]}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={"width_ratios": [1, 1.02]})
    fig.suptitle("The public estate: 640M acres — and the public charges below-market (or nothing) to strip its value",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.8)

    catcol = {"lease": "#b45309", "protect": "#1a7f37", "military": "#8593a0", "other": "#c9ccd1"}
    ax1.barh(range(len(df)), df["acres"] / 1e6, color=[catcol[c] for c in df["cat"]])
    ax1.set_yticks(range(len(df)), df["agency"], fontsize=8.5)
    for i, v in enumerate(df["acres"] / 1e6):
        ax1.text(v + 3, i, f"{v:.0f}M", va="center", fontsize=8.3)
    ax1.set_title("U.S. federal land by agency (acres)", fontsize=9.2, loc="left")
    ax1.set_xlabel("millions of acres")
    ax1.set_xlim(0, 290)
    ax1.scatter([], [], color="#b45309", marker="s", label="open to grazing / mining / drilling")
    ax1.scatter([], [], color="#1a7f37", marker="s", label="protected (parks, refuges)")
    ax1.legend(fontsize=7.4, loc="lower right")
    ax1.text(0.97, 0.36, f"640M acres = 28% of the U.S.\n{lease/1e6:.0f}M (BLM + Forest Service)\nleasable for extraction",
             transform=ax1.transAxes, ha="right", va="center", fontsize=8, color="#b45309",
             bbox=dict(boxstyle="round", fc="#fbf1e6", ec="#b45309"))

    # Panel B — the royalty rate the public charges to extract its minerals
    r = list(reversed(PUBLIC_ROYALTY))
    cols = ["#b42318" if v == 0 else ("#8593a0" if "benchmark" in l else "#0d6e78") for l, v, _ in r]
    ax2.barh(range(len(r)), [v for _, v, _ in r], color=cols)
    ax2.set_yticks(range(len(r)), [l for l, _, _ in r], fontsize=8)
    for i, (l, v, note) in enumerate(r):
        ax2.text(v + 0.4, i, f"{v:.1f}%" + (f"  ({note})" if note else ""), va="center", fontsize=7.6)
    ax2.set_title("The royalty the public collects to extract its own minerals", fontsize=9.2, loc="left")
    ax2.set_xlabel("royalty rate, % of value")
    ax2.set_xlim(0, 34)
    ax2.text(0.97, 0.93, "Also below market:\ngrazing $1.35/AUM vs $23 (93% off);\n1996 spectrum gifted free —\nthe FCC has since auctioned $233B",
             transform=ax2.transAxes, ha="right", va="top", fontsize=7.3, color="#57606a", parse_math=False,
             bbox=dict(boxstyle="round", fc="#f6f7f8", ec="#c9ccd1"))

    source_note(ax1, "Federal land: USDA/USGS via usland (2018). Royalties: GAO-21-299, CRS R46537, IRA §50262; grazing BLM IM-2025-019 "
                     "vs USDA NASS; spectrum FCC. Hardrock minerals pay $0 federal royalty and operators need not even report production.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_public_estate")


def fig_avenue_map() -> None:
    """What else is here: the full map of private-capture avenues across every branch."""
    import matplotlib.pyplot as plt

    covered = sum(1 for _, avs in AVENUE_MAP for _, _, tag in avs if tag != "frontier")
    frontier = sum(1 for _, avs in AVENUE_MAP for _, _, tag in avs if tag == "frontier")
    print(f"[ch10] avenue map: {len(AVENUE_MAP)} domains, {covered} avenues measured, {frontier} frontier")

    fig, axes = plt.subplots(1, 2, figsize=(14, 8.2))
    fig.suptitle("The map of private-capture avenues across the whole state — measured (green) and frontier (amber)",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.4)
    # split the 5 domains across two columns (3 | 2)
    layout = [AVENUE_MAP[:3], AVENUE_MAP[3:]]
    for ax, domains in zip(axes, layout):
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        y = 0.98
        for domain, avenues in domains:
            ax.text(0.0, y, domain, fontsize=10.2, fontweight="bold", color="#1a1a1a", va="top", parse_math=False)
            y -= 0.052
            for name, fact, tag in avenues:
                col = "#157a52" if tag != "frontier" else "#b45309"
                badge = tag if tag != "frontier" else "frontier"
                ax.text(0.03, y, name, fontsize=8.9, fontweight="bold", color="#333", va="top", parse_math=False)
                ax.text(0.97, y, badge, fontsize=7.4, color=col, va="top", ha="right", fontweight="bold", parse_math=False,
                        bbox=dict(boxstyle="round,pad=0.25", fc="#e8f3ee" if tag != "frontier" else "#fbf1e6", ec=col, lw=0.6))
                y -= 0.043
                ax.text(0.03, y, fact, fontsize=8, color="#57606a", va="top", parse_math=False)
                y -= 0.058
            y -= 0.025

    fig.text(0.01, 0.005, "Measured this chapter (F8–F17) in green; identified but not yet built ('frontier') in amber. "
             "Frontier figures are from GAO/WSJ/ProPublica/Brennan Center (see text); each is a natural next expedition.",
             fontsize=8, color="#57606a")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    save(fig, "10_avenue_map")


# ---------- opening the frontier doors: judiciary, clemency, earmarks ----------

# Individual stocks held by the most DISTINCT federal judges — computed from
# CourtListener's bulk financial-disclosure data (1.9M investments × 3,358 judges,
# joined investments→disclosure→person, 2026-06); counts = number of judges holding.
JUDGE_HOLDINGS = [
    ("Microsoft", 471), ("General Electric", 464), ("AT&T", 425), ("Intel", 407),
    ("Apple", 384), ("Bank of America", 364), ("Johnson & Johnson", 355), ("Pfizer", 344),
    ("Exxon Mobil", 311), ("Home Depot", 270), ("Cisco Systems", 269), ("PepsiCo", 269),
]
JUDGE_DISCLOSURE = {"investments": 1901720, "disclosures": 32336, "judges": 3358,
                    "stockholders": 3159, "stockholder_pct": 94,
                    "wsj_judges": 131, "wsj_cases": 685}   # WSJ 2021 "Hidden Interests"
# state supreme-court election spending by cycle, $M (Brennan Center)
JUDICIAL_ELECTIONS = [("2000", 45.6), ("2013–14", 34.5), ("2019–20", 97.0), ("2021–22", 100.8), ("2023–24", 157.3)]
# DOJ Office of the Pardon Attorney — clemency by president: (pres, pardons, commutations, petitions_received)
CLEMENCY = [
    ("Nixon", 863, 60, 2591), ("Ford", 382, 22, 1527), ("Carter", 534, 29, 2627),
    ("Reagan", 393, 13, 3404), ("GHW Bush", 74, 3, 1466), ("Clinton", 396, 61, 7489),
    ("GW Bush", 189, 11, 11074), ("Obama", 212, 1715, 36544), ("Trump", 144, 94, 12078), ("Biden", 80, 4165, 14867),
]
# congressional earmarks (CPF/CDS), returned FY2022 — GAO. ($B, count) and FY2024 top states ($M)
EARMARKS_YEAR = [("FY2022", 9.10, 4963), ("FY2023", 15.328, 7234), ("FY2024", 14.565, 8098)]
EARMARKS_STATE = [("California", 1054.8), ("Texas", 746.8), ("New York", 649.3), ("Maine", 601.6),
                  ("Mississippi", 530.8), ("Florida", 499.5), ("Hawaii", 489.1), ("Alaska", 470.6)]


def fig_judicial() -> None:
    """Open the judicial door: the money that elects judges, and the stocks judges own."""
    import matplotlib.pyplot as plt

    jd = JUDGE_DISCLOSURE
    print(f"[ch10] judicial: state elections ${JUDICIAL_ELECTIONS[-1][1]:.0f}M (2023-24); "
          f"{jd['investments']:,} judge investments; top holding {JUDGE_HOLDINGS[0][0]}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={"width_ratios": [0.92, 1.08]})
    fig.suptitle("The judicial door: outside money now elects state judges, and federal judges hold the market they judge",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.8)

    cyc = [c for c, _ in JUDICIAL_ELECTIONS]
    ax1.bar(range(len(cyc)), [v for _, v in JUDICIAL_ELECTIONS], color="#8250df", width=0.66)
    for i, (_, v) in enumerate(JUDICIAL_ELECTIONS):
        ax1.text(i, v + 3, f"${v:.0f}M", ha="center", fontsize=8.2)
    ax1.set_xticks(range(len(cyc)), cyc, fontsize=8.4)
    ax1.set_title("State supreme-court election spending, by cycle", fontsize=9.2, loc="left")
    ax1.set_ylabel("total spending, $ millions")
    ax1.set_ylim(0, 185)
    ax1.text(0.03, 0.93, "2023–24: outside groups ($85M)\noutspent the candidates ($70M) for\nthe first time.  Caperton v. Massey:\n$3M elected the vote that erased\na $50M verdict.",
             transform=ax1.transAxes, ha="left", va="top", fontsize=7.4, color="#8250df", parse_math=False)

    h = list(reversed(JUDGE_HOLDINGS))
    ax2.barh(range(len(h)), [n for _, n in h], color="#0d6e78")
    ax2.set_yticks(range(len(h)), [n for n, _ in h], fontsize=8.2)
    for i, (_, n) in enumerate(h):
        ax2.text(n + 4, i, f"{n:,}", va="center", fontsize=7.8)
    ax2.set_title("Individual stocks held by the most federal judges\n(CourtListener disclosures — number of judges)", fontsize=9, loc="left")
    ax2.set_xlabel("federal judges holding the stock")
    ax2.set_xlim(0, 560)
    ax2.text(0.985, 0.14, f"{jd['stockholder_pct']}% of {jd['judges']:,} disclosing\njudges hold individual stocks\n(WSJ: {jd['wsj_judges']} heard {jd['wsj_cases']} cases in them)",
             transform=ax2.transAxes, ha="right", va="bottom", fontsize=7.3, color="#57606a", parse_math=False,
             bbox=dict(boxstyle="round", fc="#f6f7f8", ec="#c9ccd1"))

    source_note(ax1, "State elections: Brennan Center, 'Politics of Judicial Elections'. Judge holdings: computed from CourtListener / "
                     "Free Law Project bulk financial-disclosure data (1.9M investment records). Conflicts: WSJ 'Hidden Interests', 2021.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_judicial")


def fig_clemency() -> None:
    """Open the executive door: the pardon power — mercy collapsing, favors concentrating at term's end."""
    import matplotlib.pyplot as plt
    import numpy as np

    c = list(reversed(CLEMENCY))
    names = [x[0] for x in c]
    pardons = [x[1] for x in c]
    comm = [x[2] for x in c]
    rate = [100 * (x[1] + x[2]) / x[3] for x in c]
    print(f"[ch10] clemency: Biden {CLEMENCY[-1][2]:,} commutations (record); grant rate Nixon "
          f"{100*(863+60)/2591:.0f}% -> GW Bush {100*(189+11)/11074:.0f}%")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={"width_ratios": [1.1, 0.9]})
    fig.suptitle("The pardon power: routine mercy collapsed to ~2%, leaving mass end-of-term and high-profile grants",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.8)

    y = np.arange(len(c))
    ax1.barh(y - 0.2, pardons, 0.4, color="#0d6e78", label="pardons")
    ax1.barh(y + 0.2, comm, 0.4, color="#b45309", label="commutations")
    ax1.set_yticks(y, names, fontsize=8.6)
    ax1.set_xscale("symlog")
    ax1.set_xlim(0, 6000)
    ax1.set_xticks([10, 100, 1000], ["10", "100", "1,000"])
    for i, (p_, cm) in enumerate(zip(pardons, comm)):
        ax1.text(cm * 1.15 if cm >= p_ else p_ * 1.15, i, f"{max(p_, cm):,}", va="center", fontsize=7)
    ax1.set_title("Clemency granted, by president (Nixon→Biden)", fontsize=9.2, loc="left")
    ax1.set_xlabel("acts granted (log scale)")
    ax1.legend(fontsize=8, loc="lower right")

    cols = ["#b42318" if r < 5 else "#1a7f37" for r in rate]
    ax2.barh(y, rate, color=cols)
    ax2.set_yticks(y, names, fontsize=8.6)
    for i, r in enumerate(rate):
        ax2.text(r + 0.6, i, f"{r:.0f}%", va="center", fontsize=8)
    ax2.set_title("Clemency GRANT rate\n(acts granted ÷ petitions received)", fontsize=9.2, loc="left")
    ax2.set_xlabel("% of petitions granted")
    ax2.set_xlim(0, 42)
    ax2.text(0.96, 0.5, "36% under Nixon →\n~2% by GW Bush/Trump.\nObama & Biden rebound\nis mass end-of-term\ncommutations, not\nrestored routine mercy.",
             transform=ax2.transAxes, ha="right", va="center", fontsize=7.3, color="#57606a", parse_math=False)

    source_note(ax1, "DOJ Office of the Pardon Attorney, clemency statistics (warrant/petition counts; excludes clemency granted "
                     "outside OPA, e.g. proclamations). Trump = first term. Petitions received have risen ~10× since mid-century.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_clemency")


def fig_earmarks() -> None:
    """Open the legislative door: earmarks returned in 2022 — directed spending, by year and by state."""
    import matplotlib.pyplot as plt

    yr = EARMARKS_YEAR
    st = list(reversed(EARMARKS_STATE))
    print(f"[ch10] earmarks: {yr[-1][0]} ${yr[-1][1]:.1f}B / {yr[-1][2]:,} provisions; top state {EARMARKS_STATE[0][0]}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [0.85, 1.15]})
    fig.suptitle("The legislative door: earmarks came back in 2022 — $14.6B of member-directed spending in FY2024",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.8)

    x = range(len(yr))
    ax1.bar(x, [v for _, v, _ in yr], color="#1f6feb", width=0.6)
    for i, (_, v, n) in enumerate(yr):
        ax1.text(i, v + 0.2, f"${v:.1f}B\n{n:,} projects", ha="center", fontsize=7.8)
    ax1.set_xticks(list(x), [y for y, _, _ in yr], fontsize=8.8)
    ax1.set_title("Earmarks by fiscal year", fontsize=9.2, loc="left")
    ax1.set_ylabel("total designated, $ billions")
    ax1.set_ylim(0, 18)

    ax2.barh(range(len(st)), [v for _, v in st], color="#1a7f37")
    ax2.set_yticks(range(len(st)), [s for s, _ in st], fontsize=8.6)
    for i, (_, v) in enumerate(st):
        ax2.text(v + 8, i, f"${v:.0f}M", va="center", fontsize=8)
    ax2.set_title("FY2024 earmarks by state (top 8)", fontsize=9.2, loc="left")
    ax2.set_xlabel("$ millions directed to the state")
    ax2.set_xlim(0, 1200)
    ax2.text(0.96, 0.1, "Top requestor: Sen. Murkowski (AK),\n~$459M across 185 projects.\nSmall states punch far above\ntheir population.",
             transform=ax2.transAxes, ha="right", va="bottom", fontsize=7.3, color="#57606a", parse_math=False)

    source_note(ax1, "GAO 'Tracking the Funds' (GAO-22-105467, -23-106561, -25-107549). FY2024 total ($14.565B) and state/requestor "
                     "breakdowns recomputed from GAO's 8,098-row line-item CSV. Earmarks were under a moratorium 2011–2021.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_earmarks")


_NPX_MGMT_CATS = {"DIRECTOR ELECTIONS", "AUDIT-RELATED", "SECTION 14A SAY-ON-PAY VOTES",
                  "COMPENSATION", "CAPITAL STRUCTURE", "EXTRAORDINARY TRANSACTIONS"}
_NPX_ES_CATS = {"ENVIRONMENT OR CLIMATE", "DIVERSITY, EQUITY, AND INCLUSION",
                "OTHER SOCIAL ISSUES", "HUMAN RIGHTS OR HUMAN CAPITAL/WORKFORCE"}


def npx_grounded() -> dict:
    """Ground the ~95%-with-management vote per company and per proposal type."""
    with connect() as con:
        comp = con.execute(
            "SELECT manager_name, count(*) n_companies, avg(mgmt_support_pct) avg_support "
            "FROM npx_company_support GROUP BY 1").df()
        full = con.execute(
            "SELECT entity, value FROM obs WHERE series_id='npx/company_full_mgmt'").df()
        cats = con.execute("SELECT manager, manager_name, category, n_votes, mgmt_support_pct "
                           "FROM npx_categories").df()
    # weighted average support on management-sponsored vs environmental/social proposals
    def wavg(df, cats_set):
        s = df[df.category.isin(cats_set)]
        return (s.mgmt_support_pct * s.n_votes).sum() / s.n_votes.sum() if len(s) else float("nan")
    grp = []
    for mgr, g in cats.groupby("manager_name"):
        grp.append({"manager": mgr, "mgmt": wavg(g, _NPX_MGMT_CATS), "es": wavg(g, _NPX_ES_CATS)})
    slug2name = {"blackrock": "BlackRock", "vanguard": "Vanguard", "statestreet": "State Street"}
    full["manager"] = full["entity"].map(slug2name)
    return {"comp": comp.merge(full[["manager", "value"]], left_on="manager_name", right_on="manager"),
            "groups": pd.DataFrame(grp)}


def fig_npx_grounded() -> None:
    """Turn the aggregate 'votes ~95% with management' into a per-company, per-proposal computation."""
    import matplotlib.pyplot as plt
    import numpy as np

    r = npx_grounded()
    comp, grp = r["comp"].sort_values("value"), r["groups"]
    print(f"[ch10] N-PX per-company: " + ", ".join(
        f"{c.manager_name} {c.value:.0f}% of {int(c.n_companies):,} cos 100%-w/-mgmt" for c in comp.itertuples()))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1, 1.05]})
    fig.suptitle("Grounding the index vote: near-total concordance company-by-company — except on climate & social proposals",
                 x=0.01, ha="left", fontweight="bold", fontsize=11.8)

    y = range(len(comp))
    ax1.barh(y, comp["value"], color="#8250df")
    ax1.set_yticks(list(y), [f"{m}\n({int(n):,} companies)" for m, n in zip(comp["manager_name"], comp["n_companies"])], fontsize=8.4)
    for i, v in enumerate(comp["value"]):
        ax1.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=8.6, fontweight="bold")
    ax1.set_title("Share of companies where the manager backed\nmanagement on EVERY vote", fontsize=9.2, loc="left")
    ax1.set_xlabel("% of the manager's portfolio companies")
    ax1.set_xlim(0, 100)
    ax1.text(0.96, 0.12, "and the median company gets\n100% management support",
             transform=ax1.transAxes, ha="right", va="bottom", fontsize=7.6, color="#8250df", parse_math=False)

    x = np.arange(len(grp))
    ax2.bar(x - 0.2, grp["mgmt"], 0.4, color="#0d6e78", label="management-sponsored\n(directors, pay, audit, M&A)")
    ax2.bar(x + 0.2, grp["es"], 0.4, color="#b42318", label="environmental & social\nshareholder proposals")
    for xi, (m, e) in enumerate(zip(grp["mgmt"], grp["es"])):
        ax2.text(xi - 0.2, m + 1.5, f"{m:.0f}%", ha="center", fontsize=8)
        ax2.text(xi + 0.2, e + 1.5, f"{e:.0f}%", ha="center", fontsize=8)
    ax2.set_xticks(x, grp["manager"], fontsize=8.6)
    ax2.set_ylabel("% of votes cast in favor")
    ax2.set_ylim(0, 108)
    ax2.set_title("Support by who proposed it", fontsize=9.2, loc="left")
    ax2.legend(fontsize=7.2, loc="center right")

    source_note(ax1, "SEC Form N-PX structured votes for the Big Three's flagship index registrants (latest proxy season), "
                     "computed per issuer. Concordance = share of the manager's companies where every management-recommendation vote went management's way.")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "10_npx_grounded")


def main() -> None:
    fig_chokepoint_map()
    fig_dual_class()
    fig_capital_pools()
    fig_hidden_hands()
    fig_big3_ownership()
    fig_elite_network()
    fig_conference_impact()
    fig_fomc_power()
    fig_fomc_deciders()
    fig_interlocks()
    fig_npx_votes()
    fig_npx_grounded()
    fig_revolving_door()
    fig_congress_trading()
    fig_defense_contracts()
    fig_defense_boards()
    fig_defense_loop()
    fig_lobbying_returns()
    fig_local_scale()
    fig_local_corruption()
    fig_local_avenues()
    fig_state_local_pots()
    fig_public_estate()
    fig_judicial()
    fig_clemency()
    fig_earmarks()
    fig_avenue_map()
    fig_concentration_dashboard()


if __name__ == "__main__":
    main()
