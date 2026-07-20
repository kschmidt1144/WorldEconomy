"""SEC Form N-PX proxy votes — how the Big Three actually vote what they own.

Since 2024 funds file their proxy-voting record as structured XML. Each vote is
one <proxyTable>: the issuer, the proposal, its source (ISSUER = management,
SHAREHOLDER = a shareholder proposal), how the fund voted, and — crucially — what
management recommended. So we can compute, from primary data, the number that
turns ~25% ownership into power: how often each manager sides with management,
and how rarely it backs a shareholder proposal.

The record is voluminous (BlackRock splits it into 100MB+ chunks across many
accessions), so we take one representative vote file per manager's flagship index
registrant and stream it. Public domain (SEC).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict

import pandas as pd
import requests

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "npx"
TITLE = "SEC Form N-PX — Big Three proxy votes"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com"}

# manager key -> (flagship index registrant CIK, display name, entity slug)
FILERS = {
    "blk": (1100663, "BlackRock", "blackrock"),    # iShares Trust
    "van": (36405, "Vanguard", "vanguard"),        # Vanguard Index Funds
    "ssga": (1064641, "State Street", "statestreet"),  # Select Sector SPDR Trust
}
_lt = lambda t: t.split("}")[-1]


def _latest_votefile(cik: int) -> tuple[str, str, str]:
    """(accession_no_dashes, filename, report_date) of a representative N-PX vote
    file: the largest ≤80MB chunk from the latest report period."""
    sub = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=UA, timeout=60).json()
    rec = sub["filings"]["recent"]
    npx = [(rec["accessionNumber"][i], rec["reportDate"][i]) for i, f in enumerate(rec["form"]) if f.startswith("N-PX")]
    latest_report = npx[0][1]
    cands = []
    for acc, rpt in npx:
        if rpt != latest_report:
            break
        accnd = acc.replace("-", "")
        ix = requests.get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnd}/index.json", headers=UA, timeout=40).json()
        for it in ix["directory"]["item"]:
            sz = int(it.get("size") or 0)
            if it["name"].lower().endswith(".xml") and "primary_doc" not in it["name"].lower() and sz > 1_000_000:
                cands.append((accnd, it["name"], sz, rpt))
    under = [c for c in cands if c[2] <= 80_000_000] or cands
    accnd, name, _sz, rpt = max(under, key=lambda c: c[2])
    return accnd, name, rpt


def fetch(force: bool = False) -> None:
    meta = {}
    for key, (cik, disp, slug) in FILERS.items():
        accnd, name, rpt = _latest_votefile(cik)
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnd}/{name}"
        download(SOURCE, url, f"{key}.xml", force=force, headers=UA)
        meta[key] = rpt
    import json
    (RAW / SOURCE / "meta.json").write_text(json.dumps(meta))


def _tally(path) -> dict:
    """Stream one N-PX vote file -> vote tallies (overall + by category)."""
    c = {"total": 0, "with_rec": 0, "with_mgmt": 0, "sh_total": 0, "sh_for": 0}
    cat = defaultdict(lambda: {"n": 0, "with_rec": 0, "with_mgmt": 0})
    with open(path, "rb") as f:
        for _ev, el in ET.iterparse(f, events=("end",)):
            if _lt(el.tag) != "proxyTable":
                continue
            g = {_lt(x.tag): x for x in el.iter()}
            source = (g["voteSource"].text if "voteSource" in g else "") or ""
            category = "OTHER"
            for x in el.iter():
                if _lt(x.tag) == "categoryType" and x.text:
                    category = x.text.strip()
                    break
            how = mgmt = None
            for vr in el.iter():
                if _lt(vr.tag) == "voteRecord":
                    kids = {_lt(k.tag): (k.text or "").strip() for k in vr}
                    how, mgmt = kids.get("howVoted"), kids.get("managementRecommendation")
                    break
            c["total"] += 1
            cat[category]["n"] += 1
            if mgmt in ("FOR", "AGAINST") and how:
                c["with_rec"] += 1
                cat[category]["with_rec"] += 1
                if how == mgmt:
                    c["with_mgmt"] += 1
                    cat[category]["with_mgmt"] += 1
            if source.upper() == "SHAREHOLDER":
                c["sh_total"] += 1
                if how == "FOR":
                    c["sh_for"] += 1
            el.clear()
    c["by_cat"] = {k: v for k, v in cat.items()}
    return c


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    import json
    meta = json.loads((RAW / SOURCE / "meta.json").read_text())
    obs_rows, cat_rows, ents = [], [], []
    for key, (cik, disp, slug) in FILERS.items():
        c = _tally(RAW / SOURCE / f"{key}.xml")
        mgmt_support = 100 * c["with_mgmt"] / c["with_rec"] if c["with_rec"] else float("nan")
        sh_support = 100 * c["sh_for"] / c["sh_total"] if c["sh_total"] else float("nan")
        print(f"[npx] {disp}: {c['total']:,} votes, {mgmt_support:.1f}% with management, "
              f"{sh_support:.1f}% of {c['sh_total']:,} shareholder proposals backed")
        obs_rows += [
            ("npx/mgmt_support", slug, mgmt_support),
            ("npx/votes", slug, float(c["total"])),
        ]
        ents.append((slug, f"{disp} (proxy votes)", "other"))
        for category, v in c["by_cat"].items():
            if v["with_rec"] >= 50:
                cat_rows.append((slug, disp, category, v["n"], 100 * v["with_mgmt"] / v["with_rec"]))

    year = int(str(list(meta.values())[0])[:4])
    obs = pd.DataFrame(
        [(sid, ent, year, val) for sid, ent, val in obs_rows],
        columns=["series_id", "entity", "year", "value"],
    ).dropna(subset=["value"])

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cat_rows, columns=["manager", "manager_name", "category", "n_votes", "mgmt_support_pct"]).to_parquet(
        out / "categories.parquet", index=False)

    _N = {"npx/mgmt_support": "Share of votes cast WITH management",
          "npx/votes": "Proxy votes in the sampled N-PX record"}
    series_list = [
        Series(series_id=sid, source=SOURCE, name=name,
               unit=("%" if sid != "npx/votes" else "votes"),
               unit_type=("percent" if sid != "npx/votes" else "count"), frequency="A",
               description="Computed from a representative Form N-PX vote file (latest proxy season) for each "
               "manager's flagship index registrant: iShares Trust, Vanguard Index Funds, Select Sector SPDR Trust.",
               license="Public domain (SEC)", url="https://www.sec.gov/cgi-bin/browse-edgar?type=N-PX")
        for sid, name in _N.items()
    ]
    ent_df = pd.DataFrame(ents, columns=["entity", "name", "kind"]).drop_duplicates("entity")
    return series_list, obs, ent_df
