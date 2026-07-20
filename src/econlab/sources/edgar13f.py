"""SEC 13F institutional holdings — the Big Three index managers.

Every institutional manager with >$100M in US-listed equities files a Form 13F
each quarter, disclosing every position (issuer, CUSIP, shares, market value,
and — crucially — whether it holds *sole*, *shared*, or *no* voting authority).
We ingest the latest 13F-HR information table for the three index giants that
together vote a large slice of corporate America:

    BlackRock (CIK 2012383) · Vanguard (102909) · State Street (93751)

For each issuer we emit the Big Three's *combined* shares held, market value,
and sole-voting shares, plus each firm individually — keyed by "$" + primary
ticker so they join directly onto `edgar/shares_q` (shares outstanding). The
ownership *percentage* is then a warehouse-side computation (analysis layer),
never a hardcoded constant.

Issuer -> ticker is by normalized name against SEC's company_tickers.json (no
free CUSIP->ticker map exists); unmatched issuers and multi-class collisions
are dropped and counted. Values are in dollars (SEC switched 13F value from
thousands to dollars in 2023-Q1; we only take the latest filing). Public domain.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "edgar13f"
TITLE = "SEC 13F holdings — the Big Three index managers"

# SEC fair-access requires a User-Agent declaring a contact; override via env.
SEC_UA = os.environ.get(
    "ECONLAB_SEC_UA", "World Economy Lab (econlab) research; kschmidt1144@gmail.com"
)
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# key -> (CIK, display name). CIKs can change (BlackRock moved 1364742 -> 2012383
# in 2024); each filer's latest 13F-HR is discovered live from its submissions feed.
FILERS: dict[str, tuple[int, str]] = {
    "blk": (2012383, "BlackRock"),
    "van": (102909, "Vanguard"),
    "ssga": (93751, "State Street"),
}

_SUFFIXES = re.compile(
    r"\b(INC|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LP|LLC|HOLDINGS?|GROUP|GRP|"
    r"THE|CLASS|CL|COM|COMMON|STK|STOCK|SA|AG|NV|SE|SPON|ADR|ADS|TR|TRUST|"
    r"INTERNATIONAL|INTL|INDUSTRIES|IND|SYSTEMS|SYS)\b"
)


def _norm(name: str) -> str:
    """Normalize an issuer/company name for matching."""
    s = re.sub(r"[.,&/'\-()]", " ", str(name).upper())
    s = _SUFFIXES.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _headers() -> dict:
    return {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"}


def _latest_13f(cik: int) -> tuple[str, str]:
    """Return (accession_no_dashes, report_date) of the newest 13F-HR for a CIK.

    Discovery is done live (submissions feed is tiny) so new quarters are picked
    up without --force; the large info-table download is cached by its unique URL.
    """
    sub = requests.get(
        f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=_headers(), timeout=60
    ).json()
    rec = sub["filings"]["recent"]
    for i, form in enumerate(rec["form"]):
        if form in ("13F-HR", "13F-HR/A"):
            return rec["accessionNumber"][i].replace("-", ""), rec["reportDate"][i]
    raise RuntimeError(f"no 13F-HR in recent filings for CIK {cik}")


def fetch(force: bool = False) -> None:
    download(SOURCE, TICKERS_URL, "company_tickers.json", force=force, headers=_headers())
    meta = {}
    for key, (cik, name) in FILERS.items():
        accnd, report = _latest_13f(cik)
        time.sleep(0.2)
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnd}"
        idx = requests.get(f"{base}/index.json", headers=_headers(), timeout=60).json()
        doc = next(
            it["name"]
            for it in idx["directory"]["item"]
            if it["name"].lower().endswith(".xml") and "primary_doc" not in it["name"].lower()
        )
        download(SOURCE, f"{base}/{doc}", f"{key}_infotable.xml", force=force, headers=_headers())
        meta[key] = {"cik": cik, "name": name, "accession": accnd, "report_date": report}
        time.sleep(0.2)
    (RAW / SOURCE / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))


def _parse_infotable(path) -> pd.DataFrame:
    """One 13F information table XML -> rows of (cusip, issuer, shares, value, sole)."""
    root = ET.fromstring(path.read_text())
    ns = re.match(r"\{(.*)\}", root.tag).group(1)

    def g(el, *tags):
        for t in tags:
            el = el.find(f"{{{ns}}}{t}") if el is not None else None
        return el.text if el is not None else None

    rows = []
    for it in root.findall(f"{{{ns}}}infoTable"):
        # 13F reports shares (SH) and principal amounts (PRN, for debt); keep SH only
        if (g(it, "shrsOrPrnAmt", "sshPrnamtType") or "SH") != "SH":
            continue
        rows.append(
            (
                g(it, "cusip"),
                g(it, "nameOfIssuer"),
                float(g(it, "shrsOrPrnAmt", "sshPrnamt") or 0),
                float(g(it, "value") or 0),
                float(g(it, "votingAuthority", "Sole") or 0),
            )
        )
    return pd.DataFrame(rows, columns=["cusip", "issuer", "shares", "value", "sole"])


def _ticker_map() -> dict[str, str]:
    """normalized-name -> $ticker. company_tickers.json is size-ranked, so the
    first occurrence of a name is the primary common stock (before preferreds
    and share classes that share the same title, e.g. JPM before JPM-PC)."""
    data = json.loads((RAW / SOURCE / "company_tickers.json").read_text())
    seen: dict[str, str] = {}
    for row in data.values():
        norm = _norm(row.get("title", ""))
        if norm:
            tkr = f"${str(row['ticker']).upper()}"
            seen.setdefault(norm, tkr)
            seen.setdefault(norm.replace(" ", ""), tkr)  # despaced fallback (Exxon Mobil / ExxonMobil)
    return seen


def _lookup(name2tkr: dict[str, str], name: str) -> str | None:
    n = _norm(name)
    return name2tkr.get(n) or name2tkr.get(n.replace(" ", ""))


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    meta = json.loads((RAW / SOURCE / "meta.json").read_text())
    name2tkr = _ticker_map()

    # per-filer holdings, aggregated by CUSIP (a security can appear in several rows)
    per_filer = {}
    issuer_of: dict[str, str] = {}
    for key in FILERS:
        df = _parse_infotable(RAW / SOURCE / f"{key}_infotable.xml")
        agg = df.groupby("cusip", as_index=False).agg(
            shares=("shares", "sum"), value=("value", "sum"), sole=("sole", "sum"),
            issuer=("issuer", "first")
        )
        per_filer[key] = agg
        for _, r in agg.iterrows():
            issuer_of.setdefault(r["cusip"], r["issuer"])

    # union of all CUSIPs; combine across the three filers
    cusips = sorted({c for a in per_filer.values() for c in a["cusip"]})
    combined = pd.DataFrame({"cusip": cusips})
    for key in FILERS:
        m = per_filer[key].set_index("cusip")
        for col in ("shares", "value", "sole"):
            combined[f"{key}_{col}"] = combined["cusip"].map(m[col]).fillna(0.0)
    combined["issuer"] = combined["cusip"].map(issuer_of)
    combined["ticker"] = combined["issuer"].map(lambda n: _lookup(name2tkr, n))

    matched = combined.dropna(subset=["ticker"]).copy()
    issuer_by_tkr = matched.groupby("ticker")["issuer"].first()
    # collapse share-class CUSIPs that map to the same ticker
    grp = matched.groupby("ticker", as_index=False).sum(numeric_only=True)
    grp["big3_shares"] = grp[[f"{k}_shares" for k in FILERS]].sum(axis=1)
    grp["big3_value"] = grp[[f"{k}_value" for k in FILERS]].sum(axis=1)
    grp["big3_sole_vote_shares"] = grp[[f"{k}_sole" for k in FILERS]].sum(axis=1)

    n_rows = sum(len(a) for a in per_filer.values())
    print(
        f"[edgar13f] {len(cusips)} unique CUSIPs, {len(grp)} matched to tickers "
        f"({len(combined) - len(matched)} unmatched); ${grp['big3_value'].sum()/1e12:.2f}T combined"
    )

    report = max(m["report_date"] for m in meta.values())
    ryear = int(report[:4])
    rdate = pd.to_datetime(report).date()

    emit = {
        "big3_shares": grp["big3_shares"],
        "big3_value": grp["big3_value"],
        "big3_sole_vote_shares": grp["big3_sole_vote_shares"],
        "blk_shares": grp["blk_shares"],
        "van_shares": grp["van_shares"],
        "ssga_shares": grp["ssga_shares"],
    }
    frames = []
    for key, series in emit.items():
        frames.append(
            pd.DataFrame(
                {"series_id": f"edgar13f/{key}", "entity": grp["ticker"], "year": ryear,
                 "date": rdate, "value": series.astype(float)}
            )
        )
    obs = pd.concat(frames, ignore_index=True)
    obs = obs[obs["value"] > 0]

    _NAMES = {
        "big3_shares": "Big Three combined shares held",
        "big3_value": "Big Three combined market value held",
        "big3_sole_vote_shares": "Big Three shares with sole voting authority",
        "blk_shares": "BlackRock shares held",
        "van_shares": "Vanguard shares held",
        "ssga_shares": "State Street shares held",
    }
    series_list = [
        Series(
            series_id=f"edgar13f/{k}",
            source=SOURCE,
            name=name,
            unit=("US$" if k == "big3_value" else "shares"),
            unit_type=("nominal_usd" if k == "big3_value" else "count"),
            frequency="Q",
            description=(
                f"{name} from the latest Form 13F-HR information tables "
                f"(BlackRock/Vanguard/State Street). Entity = primary ticker; "
                f"join onto edgar/shares_q for ownership share. As-of {report}."
            ),
            license="Public domain (SEC)",
            url="https://www.sec.gov/divisions/investment/13ffaq",
        )
        for k, name in _NAMES.items()
    ]
    ent_df = pd.DataFrame(
        {"entity": grp["ticker"], "name": grp["ticker"].map(issuer_by_tkr), "kind": "company"}
    )
    return series_list, obs, ent_df
