"""FOMC monetary-policy votes & dissents — parsed from the Fed's own statements.

Every FOMC policy statement since 2000 ends with the roll call: "Voting for the
monetary policy action were …" and, when someone breaks ranks, "Voting against
this action …, who preferred …". We fetch each statement (dates discovered from
the Fed's FOMC calendars) and parse the vote, so the report can ask — from
primary text — how the twelve most powerful people in markets actually decide:
how often the chair is opposed, and by whom. Public domain (Federal Reserve).
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import requests

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "fomc"
TITLE = "FOMC monetary-policy votes & dissents"
BASE = "https://www.federalreserve.gov"
UA = {"User-Agent": "World Economy Lab (econlab) research; kschmidt1144@gmail.com"}
START_YEAR = 2000
STMT_RE = re.compile(r"/newsevents/pressreleases/monetary(\d{8})a\.htm")


def _statement_dates() -> list[str]:
    """FOMC statement dates (YYYYMMDD): recent from the calendars page, older
    from each year's historical page."""
    dates: set[str] = set()
    urls = [f"{BASE}/monetarypolicy/fomccalendars.htm"]
    urls += [f"{BASE}/monetarypolicy/fomchistorical{y}.htm" for y in range(START_YEAR, dt.date.today().year)]
    for u in urls:
        try:
            dates.update(STMT_RE.findall(requests.get(u, headers=UA, timeout=60).text))
        except Exception:
            continue
    return sorted(d for d in dates if int(d[:4]) >= START_YEAR)


def fetch(force: bool = False) -> None:
    for d in _statement_dates():
        try:
            download(SOURCE, f"{BASE}/newsevents/pressreleases/monetary{d}a.htm",
                     f"{d}.htm", force=force, headers=UA)
        except Exception:
            continue  # a listed date without a policy statement (rare)


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _parse_statement(html: str) -> tuple[int, list[str]]:
    """Return (n_voters, [dissenter surnames]) for one statement."""
    t = _plain(html)
    voters = 0
    mf = re.search(r"Voting for the monetary policy action (?:were|was) (.*?)\.\s", t)
    if mf:
        voters = sum(1 for s in re.split(r";", mf.group(1)) if re.search(r"[A-Z][a-z]+\s+[A-Z]", s))
    dissenters: list[str] = []
    # stop at "who preferred"/"because"; a bare period-space only ends the clause
    # when NOT a middle initial (negative lookbehind for a capital, so "L. George" holds)
    ma = re.search(
        r"Voting against (?:the|this) action (?:were|was)[:]?\s*(.*?)"
        r"(?:\bwho\b|\bbecause\b|\bin order\b|(?<![A-Z])\.\s)", t)
    if ma:
        for part in re.split(r",| and ", ma.group(1)):
            toks = [x for x in re.findall(r"[A-Z][A-Za-z.'’-]+", part) if not x.endswith(".")]
            if toks and toks[-1] not in ("Chair", "Vice", "President", "Governor"):
                dissenters.append(toks[-1])
    return voters, dissenters


def parse() -> tuple[list[Series], pd.DataFrame]:
    rows = []  # (date, year, n_voters, n_dissents)
    diss = []  # (date, year, member) one row per dissenting vote
    for p in sorted((RAW / SOURCE).glob("*.htm")):
        d = p.stem
        if not (len(d) == 8 and d.isdigit()):
            continue
        year = int(d[:4])
        date = dt.date(year, int(d[4:6]), int(d[6:8]))
        voters, dissenters = _parse_statement(p.read_text(errors="ignore"))
        rows.append((date, year, voters, len(dissenters)))
        for m in dissenters:
            diss.append((date, year, m))

    meetings = pd.DataFrame(rows, columns=["date", "year", "n_voters", "n_dissents"])
    diss_df = pd.DataFrame(diss, columns=["date", "year", "member"])

    # side table: one row per dissenting vote (who broke ranks, when)
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    diss_df.to_parquet(out / "dissents.parquet", index=False)

    by_year = meetings.groupby("year").agg(
        meetings=("date", "count"), dissents=("n_dissents", "sum")
    ).reset_index()
    print(f"[fomc] {len(meetings)} statements {meetings.year.min()}–{meetings.year.max()}; "
          f"{int(meetings.n_dissents.sum())} dissenting votes; top dissenter: "
          f"{diss_df.member.value_counts().index[0]} ({diss_df.member.value_counts().iloc[0]})")

    obs = pd.concat([
        pd.DataFrame({"series_id": "fomc/dissents", "entity": "USA",
                      "year": by_year["year"], "value": by_year["dissents"].astype(float)}),
        pd.DataFrame({"series_id": "fomc/meetings", "entity": "USA",
                      "year": by_year["year"], "value": by_year["meetings"].astype(float)}),
    ], ignore_index=True)

    series_list = [
        Series(series_id="fomc/dissents", source=SOURCE, name="FOMC dissenting votes (per year)",
               unit="votes", unit_type="count", frequency="A",
               description="Dissenting votes on the FOMC monetary-policy action, parsed from "
               "the Fed's policy statements. The dissents never overturn the action.",
               license="Public domain (Federal Reserve)",
               url=f"{BASE}/monetarypolicy/fomccalendars.htm"),
        Series(series_id="fomc/meetings", source=SOURCE, name="FOMC policy statements (per year)",
               unit="meetings", unit_type="count", frequency="A",
               description="Number of FOMC policy statements issued per year.",
               license="Public domain (Federal Reserve)",
               url=f"{BASE}/monetarypolicy/fomccalendars.htm"),
    ]
    return series_list, obs
