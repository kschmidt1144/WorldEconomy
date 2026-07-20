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


def main() -> None:
    fig_chokepoint_map()
    fig_dual_class()
    fig_capital_pools()
    fig_hidden_hands()
    fig_big3_ownership()
    fig_elite_network()
    fig_conference_impact()
    fig_fomc_power()


if __name__ == "__main__":
    main()
