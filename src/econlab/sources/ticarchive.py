"""TIC major-foreign-holders — archived by-country history (2002-2023).

The classic fixed-width `mfh.txt` froze in early 2023 (the live `tic` source now
reads the tab-delimited `slt_table5`). Its deep by-country history — who owned the
US federal debt, and how the custody veil grew — survives only in the Wayback
Machine. This connector fetches a pinned snapshot per year (immutable once cached),
parses the most-recent month from each, and emits an annual holdings series that
splices onto the live `tic` table. Public domain (US Treasury); snapshots via the
Internet Archive.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download
from ..model import month_end

SOURCE = "ticarchive"
TITLE = "TIC foreign holders — archived by-country history"

_H1 = "https://www.ustreas.gov/tic/mfh.txt"
_H2 = "https://www.treasury.gov/resource-center/data-chart-center/tic/Documents/mfh.txt"
_H3 = "https://www.treasury.gov/ticdata/Publish/mfh.txt"
_H4 = "https://ticdata.treasury.gov/Publish/mfh.txt"

# one pinned Wayback snapshot per year, 2002-2023 (timestamp, original host url)
PINNED = [
    ("20020814062540", _H1), ("20030427083135", _H1), ("20041011113715", _H1),
    ("20051214184321", _H1), ("20060925151213", _H1), ("20071011065514", _H1),
    ("20081011001520", _H1), ("20090924085153", _H1),
    ("20101209040807", _H2), ("20111208045939", _H2), ("20120813143329", _H2),
    ("20131005000021", _H2),
    ("20141008044124", _H3),
    ("20151201092742", _H4), ("20161202014347", _H4), ("20171205204912", _H4),
    ("20181203225122", _H4), ("20191201195741", _H4), ("20200903003736", _H4),
    ("20211204144024", _H4), ("20221205205317", _H4), ("20231204204922", _H4),
]

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# target holders -> (ISO3/pseudo, is_custodial). Custody centers mask beneficial owners.
HOLDERS = {
    "china, mainland": ("CHN", False), "mainland china": ("CHN", False),
    "china  mainland": ("CHN", False), "china mainland": ("CHN", False),
    "japan": ("JPN", False), "united kingdom": ("GBR", True),
    "belgium": ("BEL", True), "luxembourg": ("LUX", True), "ireland": ("IRL", True),
    "switzerland": ("CHE", True), "cayman islands": ("CYM", True),
    "carib bkg ctrs": ("CARIB", True), "caribbean banking centers": ("CARIB", True),
    "hong kong": ("HKG", False), "taiwan": ("TWN", False), "grand total": ("WLD", False),
}


def fetch(force: bool = False) -> None:
    for ts, url in PINNED:
        wb = f"https://web.archive.org/web/{ts}id_/{url}"
        for attempt in range(3):  # Wayback throttles rapid requests
            try:
                download(SOURCE, wb, f"mfh_{ts}.txt", force=force, timeout=60)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[ticarchive] snapshot {ts} skipped: {e}")


def _norm(name: str) -> str:
    name = re.sub(r"\s+\d+/", "", name)      # strip footnote tokens like '2/', '4/'
    return re.sub(r"\s+", " ", name).strip().lower()


def _header_date(lines: list[str], ci: int):
    """The most-recent (month, year) = first column. The month and year live on the
    'Country' line and the line above it — but their ORDER flips across vintages
    (pre-2008 puts years above / months on the Country line; later files reverse it),
    so read whichever line carries which."""
    def months(s: str) -> list[str]:
        return [m for m in re.findall(r"[A-Z][a-z]{2}", s) if m in MONTHS]
    def years(s: str) -> list[str]:
        return re.findall(r"\b(?:19|20)\d\d\b", s)
    a, b = lines[ci], lines[ci - 1] if ci else ""
    mon = months(a) or months(b)
    yr = years(a) or years(b)
    if not mon or not yr:
        return None
    return month_end(int(yr[0]), MONTHS[mon[0]])


def _parse_one(text: str) -> list[tuple]:
    lines = text.splitlines()
    ci = next((i for i, ln in enumerate(lines)
               if ln.strip().lower().startswith("country")), None)
    if ci is None or ci == 0:
        return []
    date = _header_date(lines, ci)
    if date is None:
        return []
    out = []
    for ln in lines[ci + 1:]:
        m = re.match(r"^(\S.*?)\s{2,}(-?\d[\d,]*\.?\d*)", ln)
        if not m:
            continue
        key = _norm(m.group(1))
        if key in HOLDERS:
            iso, cust = HOLDERS[key]
            val = float(m.group(2).replace(",", ""))
            out.append((iso, cust, date, val))
        if key == "grand total":
            break
    return out


def parse() -> tuple[list[Series], pd.DataFrame]:
    rows = []
    for ts, _ in PINNED:
        p = RAW / SOURCE / f"mfh_{ts}.txt"
        if not p.exists():
            continue
        text = p.read_text(errors="replace")
        for iso, cust, date, val in _parse_one(text):
            rows.append((iso, cust, date, val))
    if not rows:
        raise RuntimeError("ticarchive: no snapshots parsed (Wayback fetch failed?)")

    df = pd.DataFrame(rows, columns=["entity", "custodial", "date", "value"])
    df["year"] = df["date"].map(lambda d: d.year)
    # one observation per holder-year (latest month already chosen per snapshot)
    df = df.sort_values("date").drop_duplicates(subset=["entity", "year"], keep="last")
    df["series_id"] = "ticarchive/holdings"
    df["value"] = df["value"] * 1e9  # $bn -> base USD

    series_list = [
        Series(
            series_id="ticarchive/holdings",
            source=SOURCE,
            name="US Treasury securities held by foreign holders (archived history)",
            unit="US$ (normalized from billions)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "Major Foreign Holders of Treasury securities, by jurisdiction, "
                "annual 2002-2023, from archived Treasury mfh.txt (Wayback). WLD = "
                "grand total; CARIB = Caribbean Banking Centers (pre-2011, before "
                "Cayman broke out separately). Custody centers (BEL/LUX/IRL/CYM/CARIB/"
                "CHE/GBR) mask beneficial owners. Splices onto the live `tic` table."
            ),
            license="Public domain (US Treasury); snapshots via the Internet Archive",
            url="https://ticdata.treasury.gov/Publish/mfh.txt",
        )
    ]
    return series_list, df[["series_id", "entity", "year", "date", "value"]]
