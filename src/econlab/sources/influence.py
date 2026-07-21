"""The revolving door & the marketplace of influence — where public power meets
private money, measured from three public disclosure regimes.

Chapter 9 flags "lobbying intensity, revolving-door careers" as real but
unquantified. This connector quantifies them from primary filings:

1. **Lobbying / the revolving door** — the Senate Lobbying Disclosure Act (LDA)
   API. Every registered lobbyist must disclose any prior government ("covered")
   position; the share who do is the literal revolving door. We also read what
   they lobby on (issue areas) and whom (which parts of government).
2. **Trading while governing** — the U.S. House Clerk's financial-disclosure
   bulk data. Members must file a Periodic Transaction Report (PTR) within
   45 days of a securities trade; the count of PTRs measures how much sitting
   lawmakers trade the markets they legislate.
3. **Money in** — the FEC's PAC financial summaries: how much money flows through
   political action committees in a cycle.

All three are free, public, primary-source U.S. government disclosures.
"""

from __future__ import annotations

import collections
import io
import json
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "influence"
TITLE = "Revolving door & marketplace of influence (lobbying, congressional trades, PACs)"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com"}

LDA = "https://lda.senate.gov/api/v1/filings/"
HOUSE = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs"
FEC = "https://www.fec.gov/files/bulk-downloads/2024/webk24.zip"

SAMPLE_YEAR = 2023           # deep-sample this year's quarterly reports for the rate
SAMPLE_PAGES = 16            # 16 * 25 = 400 filings — a robust proportion
COUNT_YEARS = [2008, 2012, 2016, 2020, 2023, 2024]
PTR_YEARS = list(range(2016, 2025))
ISSUE_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]   # all-quarter pull for the issue-area ranking
ISSUE_PAGES = 8                              # per quarter — ~800 filings, kills the Q2 skew

# the defense-influence loop: each prime's own federal lobbying spend (LDA client_name).
# RTX files under "RTX" (not the deprecated "Raytheon Technologies").
DEF_LOBBY_YEAR = 2023
DEFENSE_LOBBY_CLIENTS = {
    "Lockheed Martin": "Lockheed Martin", "RTX": "RTX", "Boeing": "Boeing Company",
    "General Dynamics": "General Dynamics", "Northrop Grumman": "Northrop Grumman",
}


def _slug(s: str) -> str:
    return s.lower().replace(" ", "")


def fetch(force: bool = False) -> None:
    # 1. lobbying — a deep sample of one year's Q2 reports (for the revolving-door
    #    rate + issue/entity mix), plus a cheap per-year filing count (for volume).
    for pg in range(1, SAMPLE_PAGES + 1):
        url = f"{LDA}?filing_year={SAMPLE_YEAR}&filing_type=Q2&page_size=25&page={pg}"
        try:
            download(SOURCE, url, f"lda_{SAMPLE_YEAR}_p{pg:02d}.json", force=force, headers=UA)
        except Exception:
            break  # ran past the last page
    for y in COUNT_YEARS:
        download(SOURCE, f"{LDA}?filing_year={y}&page_size=1", f"lda_count_{y}.json", force=force, headers=UA)

    # 2. congressional trading — the House Clerk annual disclosure index (XML in a zip)
    for y in PTR_YEARS:
        try:
            download(SOURCE, f"{HOUSE}/{y}FD.zip", f"{y}FD.zip", force=force, headers=UA)
        except Exception:
            continue

    # 3. money in — FEC PAC financial summaries for the 2024 cycle
    download(SOURCE, FEC, "webk24.zip", force=force, headers=UA)

    # 3b. issue-area ranking — all four quarters, so it isn't skewed by one quarter's filers
    for ft in ISSUE_QUARTERS:
        for pg in range(1, ISSUE_PAGES + 1):
            url = f"{LDA}?filing_year={SAMPLE_YEAR}&filing_type={ft}&page_size=25&page={pg}"
            try:
                download(SOURCE, url, f"issue_{ft}_p{pg:02d}.json", force=force, headers=UA)
            except Exception:
                break

    # 4. the defense loop — each prime's own lobbying spend (client_name filter)
    for prime, cq in DEFENSE_LOBBY_CLIENTS.items():
        for pg in range(1, 5):
            url = (f"{LDA}?filing_year={DEF_LOBBY_YEAR}&client_name={urllib.parse.quote(cq)}"
                   f"&page_size=25&page={pg}")
            try:
                download(SOURCE, url, f"deflob_{_slug(prime)}_p{pg}.json", force=force, headers=UA)
            except Exception:
                break  # past the last page for this client


def _branch(pos: str) -> str:
    """Classify a lobbyist's disclosed prior government post by branch."""
    p = pos.lower()
    if any(k in p for k in ("rep.", "sen.", "representative", "senator", "congress",
                            "house", "senate", "legislative", "committee")):
        return "Congress (member or staff)"
    if any(k in p for k in ("dept", "department", "agency", "white house", "administration",
                            "commission", "ambassador", "secretary", "office", "council",
                            "executive", "treasury", "defense", "trade rep", "epa", "usda")):
        return "Executive branch / agency"
    return "Other / judicial"


def _parse_lobbying() -> tuple[pd.DataFrame, int, int, dict]:
    """From the cached sample: revolving-door counts, issue/entity/branch tallies."""
    covered = total = 0
    issues, ents, branches = collections.Counter(), collections.Counter(), collections.Counter()
    for p in sorted((RAW / SOURCE).glob(f"lda_{SAMPLE_YEAR}_p*.json")):
        d = json.loads(p.read_text())
        for r in d.get("results", []):
            for act in r.get("lobbying_activities", []):
                code = act.get("general_issue_code_display") or act.get("general_issue_code")
                for ge in act.get("government_entities", []):
                    ents[ge.get("name")] += 1
                for lob in act.get("lobbyists", []):
                    total += 1
                    cp = (lob.get("covered_position") or "").strip()
                    if cp:
                        covered += 1
                        branches[_branch(cp)] += 1
                if code:
                    issues[code] += 1
    rows = ([{"kind": "issue", "label": k, "count": v} for k, v in issues.most_common(8)]
            + [{"kind": "entity", "label": k, "count": v} for k, v in ents.most_common(6)]
            + [{"kind": "branch", "label": k, "count": v} for k, v in branches.most_common()])
    counts = {}
    for y in COUNT_YEARS:
        cp = RAW / SOURCE / f"lda_count_{y}.json"
        if cp.exists():
            counts[y] = int(json.loads(cp.read_text()).get("count", 0))
    return pd.DataFrame(rows), covered, total, counts


def _parse_ptr() -> pd.DataFrame:
    """Per-year congressional stock-trade reports (PTR filings) and their filers."""
    rows = []
    for y in PTR_YEARS:
        zp = RAW / SOURCE / f"{y}FD.zip"
        if not zp.exists():
            continue
        try:
            z = zipfile.ZipFile(zp)
            xmlf = [n for n in z.namelist() if n.endswith(".xml")][0]
            root = ET.fromstring(z.read(xmlf))
        except Exception:
            continue
        ptr = [m for m in root.findall("Member") if (m.findtext("FilingType") or "") == "P"]
        if len(ptr) < 20:      # older indexes are sparse/incomplete
            continue
        by_person = collections.Counter(
            f"{(m.findtext('Last') or '').strip()}, {(m.findtext('First') or '').strip()}" for m in ptr)
        for member, n in by_person.items():
            rows.append({"year": y, "member": member, "reports": n})
    return pd.DataFrame(rows)


def _parse_issues() -> pd.DataFrame:
    """All-quarter lobbying-issue-area ranking (share of lobbying-activity records)."""
    issues = collections.Counter()
    for p in sorted((RAW / SOURCE).glob("issue_Q*_p*.json")):
        for r in json.loads(p.read_text()).get("results", []):
            for act in r.get("lobbying_activities", []):
                c = act.get("general_issue_code_display") or act.get("general_issue_code")
                if c:
                    issues[c] += 1
    tot = sum(issues.values()) or 1
    return pd.DataFrame([{"issue": k, "count": v, "pct": 100 * v / tot}
                         for k, v in issues.most_common(14)])


def _parse_defense_lobby() -> pd.DataFrame:
    """Each defense prime's total federal lobbying spend (income to hired firms +
    in-house expenses) for DEF_LOBBY_YEAR."""
    rows = []
    for prime in DEFENSE_LOBBY_CLIENTS:
        tot = 0.0
        for p in sorted((RAW / SOURCE).glob(f"deflob_{_slug(prime)}_p*.json")):
            for r in json.loads(p.read_text()).get("results", []):
                for k in ("income", "expenses"):
                    v = r.get(k)
                    if v:
                        try:
                            tot += float(v)
                        except ValueError:
                            pass
        rows.append({"prime": prime, "year": DEF_LOBBY_YEAR, "lobbying": tot})
    return pd.DataFrame(rows)


def _parse_fec() -> tuple[float, int]:
    """Total PAC receipts and PAC count for the 2024 cycle (FEC webk summary)."""
    zp = RAW / SOURCE / "webk24.zip"
    if not zp.exists():
        return 0.0, 0
    z = zipfile.ZipFile(zp)
    lines = z.read("webk24.txt").decode(errors="replace").splitlines()
    total = 0.0
    n = 0
    for ln in lines:
        f = ln.split("|")
        if len(f) < 6:
            continue
        n += 1
        try:
            total += float(f[5])   # TTL_RECEIPTS
        except ValueError:
            pass
    return total, n


def parse() -> tuple[list[Series], pd.DataFrame]:
    activity, covered, total_lob, counts = _parse_lobbying()
    ptr = _parse_ptr()
    pac_receipts, pac_n = _parse_fec()
    deflob = _parse_defense_lobby()
    issues = _parse_issues()

    rev_share = 100.0 * covered / total_lob if total_lob else 0.0

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    activity.to_parquet(out / "lobby_activity.parquet", index=False)
    ptr.to_parquet(out / "congress_traders.parquet", index=False)
    deflob.to_parquet(out / "defense_lobbying.parquet", index=False)
    issues.to_parquet(out / "lobby_issues.parquet", index=False)

    ptr_by_year = ptr.groupby("year").agg(reports=("reports", "sum"),
                                          members=("member", "nunique")).reset_index()

    print(f"[influence] revolving door: {covered}/{total_lob} lobbyist records = "
          f"{rev_share:.1f}% former officials ({SAMPLE_YEAR} sample); "
          f"congress PTRs {ptr_by_year['reports'].sum() if len(ptr_by_year) else 0} over "
          f"{len(ptr_by_year)} yrs; FEC {pac_n:,} PACs, ${pac_receipts/1e9:.1f}B receipts; "
          f"defense primes lobbying ${deflob['lobbying'].sum()/1e6:.0f}M ({DEF_LOBBY_YEAR})")

    frames = [
        pd.DataFrame({"series_id": "influence/lobby_filings", "entity": "USA",
                      "year": list(counts), "value": [float(v) for v in counts.values()]}),
        pd.DataFrame({"series_id": "influence/revolving_share", "entity": "USA",
                      "year": [SAMPLE_YEAR], "value": [rev_share]}),
    ]
    if len(ptr_by_year):
        frames += [
            pd.DataFrame({"series_id": "influence/congress_ptr", "entity": "USA",
                          "year": ptr_by_year["year"], "value": ptr_by_year["reports"].astype(float)}),
            pd.DataFrame({"series_id": "influence/congress_ptr_members", "entity": "USA",
                          "year": ptr_by_year["year"], "value": ptr_by_year["members"].astype(float)}),
        ]
    if pac_n:
        frames += [
            pd.DataFrame({"series_id": "influence/pac_receipts", "entity": "USA",
                          "year": [2024], "value": [pac_receipts]}),
            pd.DataFrame({"series_id": "influence/pac_count", "entity": "USA",
                          "year": [2024], "value": [float(pac_n)]}),
        ]
    obs = pd.concat(frames, ignore_index=True)

    def S(sid, name, unit, ut, desc):
        return Series(series_id=sid, source=SOURCE, name=name, unit=unit, unit_type=ut,
                      frequency="A", description=desc, license="US government (public domain)",
                      url="lda.senate.gov / disclosures-clerk.house.gov / fec.gov")

    series_list = [
        S("influence/lobby_filings", "Federal lobbying filings (per year)", "filings", "count",
          "Senate LDA lobbying disclosure filings lodged per year."),
        S("influence/revolving_share", "Lobbyists who are former government officials (%)", "%", "percent",
          "Share of sampled lobbyist-activity records disclosing a prior 'covered' government position."),
        S("influence/congress_ptr", "US House stock-trade reports (PTRs) per year", "reports", "count",
          "House Periodic Transaction Reports (a filing per securities-trade disclosure) per year."),
        S("influence/congress_ptr_members", "US House members filing stock trades per year", "members", "count",
          "Distinct House members filing at least one PTR in the year."),
        S("influence/pac_receipts", "Total PAC receipts, 2024 cycle (USD)", "USD", "nominal_usd",
          "Sum of total receipts across all federal PACs, 2023-24 cycle (FEC webk)."),
        S("influence/pac_count", "Number of federal PACs (2024 cycle)", "committees", "count",
          "Count of federal political action committees filing financial summaries, 2024 cycle."),
    ]
    return series_list, obs
