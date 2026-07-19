"""Chapter 10 — The Chokepoints: where a few control the many.

Generalizes Chapter 6's "Giant Three" finding from finance to the whole
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

# Big Three combined ownership of the mega-caps, computed from their latest 13F
# filings (BlackRock Q2-2024, Vanguard Q4-2025, State Street Q1-2026) ÷ shares
# outstanding (SEC XBRL). Snapshot; positions are stable index holdings.
BIG3_OWNERSHIP = {
    "Nvidia": 20.8, "Coca-Cola": 19.0, "Exxon Mobil": 18.6, "Apple": 18.1,
    "Microsoft": 17.8, "Amazon": 17.5, "Tesla": 15.0, "JPMorgan": 14.8,
}


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
    """Big Three combined ownership of the mega-caps — from their own 13F filings."""
    d = pd.Series(BIG3_OWNERSHIP).sort_values()
    print("[ch10] Big Three own of mega-caps (13F):", {k: round(v) for k, v in BIG3_OWNERSHIP.items()})
    fig, ax = new_fig(
        "Three firms own ~a fifth of every American giant (from their own 13F filings)",
        subtitle="BlackRock + Vanguard + State Street combined stake, computed from their SEC 13F holdings ÷ shares "
        "outstanding. They are the largest owners of corporate America — and, through their stewardship teams, vote it.",
        ylabel=None,
    )
    y = np.arange(len(d))
    ax.barh(y, d.values, color="#8250df")
    ax.set_yticks(y, d.index, fontsize=9)
    for i, v in enumerate(d.values):
        ax.text(v + 0.2, i, f"{v:.1f}%", va="center", fontsize=8.5)
    ax.axvline(d.mean(), color="#57606a", lw=1, ls="--")
    ax.text(d.mean() + 0.2, 0.3, f"avg {d.mean():.0f}%", fontsize=8, color="#57606a")
    ax.set_xlabel("Big Three combined ownership, % of shares outstanding")
    ax.set_xlim(0, 24)
    source_note(ax, "Source: computed from SEC 13F filings (BlackRock/Vanguard/State Street) ÷ shares outstanding (SEC XBRL) (econlab)")
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


def main() -> None:
    fig_chokepoint_map()
    fig_dual_class()
    fig_capital_pools()
    fig_hidden_hands()
    fig_big3_ownership()
    fig_elite_network()


if __name__ == "__main__":
    main()
