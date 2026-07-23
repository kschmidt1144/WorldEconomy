"""BIS Entity List — the export-control lever, counted over time.

The US Commerce Department's Entity List (15 CFR 744, Supplement No. 4) is the
sharpest export-control instrument the US has: a listed entity needs a license
(usually presumption of denial) for any item subject to the EAR. This connector
counts listings per country per year from the **eCFR point-in-time API**, whose
regulation history begins 2017-01-03 — one July-1 snapshot per year, 2017 to
the present. That window covers the era that matters: Huawei + affiliates
(May 2019), SMIC (Dec 2020), and the post-invasion Russia wave (2022+).

Counting rules: one table row = one listing; an entity listed under several
countries counts once per country listing; the footnote block (TFOOT) is not an
entity. Country headings are ALL-CAPS cells in column 0 — some vintages misalign
a row and put the *entity* text in column 0 (e.g. HiSilicon, 2020), detected by
lowercase letters and counted under the current country. HONG KONG is a separate
heading through the 2020 snapshot and merged under CHINA from 2021 (BIS's Dec-2020
Hong Kong policy change) — the CHN jump in 2021 is partly that merge. Occupied-
region headings (CRIMEA REGION OF UKRAINE, ...) map to no ISO3; their rows count
only in the WLD total. Raw per-heading counts (incl. those labels) go to the
side-table `entitylist_countries`.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import date as _date
from pathlib import Path

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "entitylist"
TITLE = "BIS Entity List (export-control designations)"
START_YEAR = 2017  # eCFR point-in-time history begins 2017-01-03
API = ("https://www.ecfr.gov/api/versioner/v1/full/{d}/title-15.xml"
       "?part=744&appendix=Supplement%20No.%204%20to%20Part%20744")
PAGE = "https://www.ecfr.gov/current/title-15/subtitle-B/chapter-VII/subchapter-C/part-744"

# Entity-List country headings that don't resolve via the WDI Short/Table names
# (keys lowercase; "" = deliberately unmapped, counts only in the WLD total)
_NAME_OVERRIDE = {
    "china, people's republic of": "CHN", "hong kong": "HKG", "taiwan": "TWN",
    "russia": "RUS", "burma": "MMR", "south korea": "KOR", "laos": "LAO",
    "north macedonia": "MKD", "turkey": "TUR", "egypt": "EGY", "iran": "IRN",
    "syria": "SYR", "venezuela": "VEN", "vietnam": "VNM", "kyrgyzstan": "KGZ",
    "slovakia": "SVK", "bahamas": "BHS", "gambia": "GMB", "yemen": "YEM",
    "crimea region of ukraine": "",
    "donetsk region of ukraine": "", "luhansk region of ukraine": "",
    "so-called donetsk people's republic": "",
    "so-called luhansk people's republic": "",
}


def _wdi_name_map() -> dict[str, str]:
    import glob

    out: dict[str, str] = {}
    for cand in glob.glob(str(RAW / "wdi" / "**" / "WDICountry.csv"), recursive=True):
        wc = pd.read_csv(cand, dtype=str)
        for _, r in wc.iterrows():
            for col in ("Short Name", "Table Name"):
                v = r.get(col)
                if pd.notna(v) and pd.notna(r["Country Code"]):
                    out[str(v).strip().lower()] = str(r["Country Code"]).strip()
        break
    return out


def _snapshot_years() -> list[int]:
    today = _date.today()
    return [y for y in range(START_YEAR, today.year + 1) if _date(y, 7, 1) <= today]


def fetch(force: bool = False) -> None:
    for y in _snapshot_years():
        url = API.format(d=f"{y}-07-01")
        try:
            download(SOURCE, url, f"supp4_{y}.xml", force=force, timeout=180)
            time.sleep(0.3)  # polite to the eCFR API when actually downloading
        except Exception as e:
            print(f"[entitylist] {y} snapshot skipped: {e}")


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def _count_one(xml: str) -> Counter:
    """Per-country-heading listing counts for one snapshot's Supplement No. 4 XML.

    One 5-cell table row = one listing. Column 0 carries the ALL-CAPS country
    heading on that country's first row, blank after. Vintage quirks handled:
    pre-2024 GPO markup has no TBODY (plain TR/TD, header row uses TH); TFOOT
    (2024+) holds footnote definitions, not entities; a few rows misalign the
    entity text into column 0 (lowercase letters ⇒ entity, not a heading) and
    can carry 4 or 6 cells instead of 5.
    """
    xml = re.sub(r"<TFOOT>.*?</TFOOT>", "", xml, flags=re.S)
    m = re.search(r"<TABLE[^>]*>(.*?)</TABLE>", xml, re.S)
    if not m:
        raise ValueError("entitylist: no TABLE found in Supplement No. 4 XML")
    counts: Counter = Counter()
    country: str | None = None
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", m.group(1), re.S):
        cells = [_strip_tags(c) for c in re.findall(r"<TD[^>]*>(.*?)</TD>", tr, re.S)]
        if len(cells) < 4:  # header row (TH-only) or stray footnote row
            continue
        c0 = cells[0]
        if c0 and not re.search(r"[a-z]", c0):  # ALL-CAPS ⇒ country heading
            country = c0
            if cells[1]:  # heading row carries the country's first entity
                counts[country] += 1
        elif c0:  # misaligned row: entity text landed in the country column
            counts[country] += 1
        elif cells[1]:
            counts[country] += 1
    return counts


def parse() -> tuple[list[Series], pd.DataFrame]:
    name_map = _wdi_name_map()

    def to_iso3(label: str) -> str | None:
        key = label.strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    rows, side, unmapped = [], [], set()
    for path in sorted((RAW / SOURCE).glob("supp4_*.xml")):
        year = int(re.search(r"supp4_(\d{4})\.xml", path.name).group(1))
        counts = _count_one(path.read_text(encoding="utf-8"))
        for label, n in counts.items():
            iso = to_iso3(label)
            side.append({"year": year, "country_label": label, "entity": iso, "n": n})
            if iso:
                rows.append(("entitylist/entities", iso, year, None, float(n)))
            elif label.strip().lower() not in _NAME_OVERRIDE:
                unmapped.add(label)
        rows.append(("entitylist/entities", "WLD", year, None, float(sum(counts.values()))))

    if unmapped:
        print(f"[entitylist] unmapped country headings (WLD-only): {sorted(unmapped)}")
    if not rows:
        raise RuntimeError("entitylist: parsed 0 rows — run fetch() / check eCFR XML layout")

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(side).sort_values(["year", "n"], ascending=[True, False]).to_parquet(
        out / "entitylist_countries.parquet", index=False)

    series_list = [
        Series(
            series_id="entitylist/entities",
            source=SOURCE,
            name="BIS Entity List entries (export-control designations)",
            unit="entities listed (count, snapshot as of July 1)",
            unit_type="count",
            frequency="A",
            description=(
                "Number of entries on the US Commerce BIS Entity List (15 CFR 744 "
                "Supplement No. 4) per country, one July-1 snapshot per year from the "
                "eCFR point-in-time API (history begins 2017). One table row = one "
                "listing; an entity listed under several countries counts once per "
                "country. WLD = all rows, including occupied-region headings (Crimea) "
                "that map to no ISO3. HONG KONG (HKG) is a separate heading through "
                "2020 and merged under CHINA from the 2021 snapshot on — part of the "
                "2021 CHN jump. Landmarks: Huawei+affiliates May 2019, SMIC Dec 2020, "
                "Russia wave 2022+. Raw per-heading counts in side-table "
                "`entitylist_countries`."
            ),
            license="Public domain (US federal regulation, via eCFR API)",
            url=PAGE,
        )
    ]
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
