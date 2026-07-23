"""OFAC SDN list — archived history via Wayback snapshots (2000-2024).

The live `sanctions` source snapshots today's SDN list; this connector recovers
its HISTORY: one pinned Wayback snapshot per year of the full list, parsed for
the total designation count and the per-target-country breakdown (reusing the
`sanctions` program->country map). Three format eras, all machine-readable:

- 2000-2003: `t11sdall.exe` — a self-extracting ZIP (plain zip central
  directory, `unzip`/zipfile-readable) holding `SDN.DEL`, the @-delimited
  12-field main file (`-0-` nulls).
- 2004-2017, 2019-2024: `sdn.csv` — the familiar 12-column CSV (hosts move:
  treas.gov `/offices/enforcement/ofac/sdn/delimit/` then treasury.gov
  `/ofac/downloads/`).
- 2018: `sdn.xml` (no sdn.csv capture that year; sdnlist.txt is unusable — the
  printed alphabetical list repeats each entry once per alias).

Unreachable, with evidence: 1994-1999 (the 1997 FAC page links every data file
to ftp.fedworld.gov, which the Wayback Machine never captured; treas.gov-hosted
full lists start Aug-2000) and 2025 (only the 14MB print-format sdnlist.pdf was
archived — no csv/xml/pip/del capture exists that year). 2026+ is the live
`sanctions` source; splice `sdnarchive/sdn_total` onto `sanctions/sdn_total`.

Wayback gotcha (same as ticarchive): rapid requests get throttled/403'd, so
fetch sleeps between downloads and SKIPS years already cached — re-run to fill
whatever a throttled partial run missed.
"""

from __future__ import annotations

import re
import time
import zipfile
from collections import Counter

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download
from .sanctions import _PROGRAM_COUNTRY

SOURCE = "sdnarchive"
TITLE = "OFAC SDN list — archived history (Wayback)"

_OFAC = "http://www.treas.gov/ofac/t11sdall.exe"
_EOTFFC = "http://www.treas.gov/offices/eotffc/ofac/sdn/t11sdall.exe"
_DELIMIT = "http://www.treas.gov/offices/enforcement/ofac/sdn/delimit/sdn.csv"
_DOWNLOADS = "https://www.treasury.gov/ofac/downloads/sdn.csv"
_XML = "https://www.treasury.gov/ofac/downloads/sdn.xml"

# one pinned snapshot per year: (year, wayback timestamp, original url, kind)
PINNED = [
    (2000, "20000815061445", _OFAC, "zip"),
    (2001, "20010808022202", _OFAC, "zip"),
    (2002, "20020207051217", _OFAC, "zip"),
    (2003, "20030806075050", _EOTFFC, "zip"),
    (2004, "20041209053135", _DELIMIT, "csv"),
    (2005, "20050105101952", _DELIMIT, "csv"),
    (2006, "20060105221224", _DELIMIT, "csv"),
    (2007, "20070109034336", _DELIMIT, "csv"),
    (2008, "20080109110958", _DELIMIT, "csv"),
    (2009, "20090610163607", _DELIMIT, "csv"),  # the Jan-2009 capture is truncated (26KB)
    (2010, "20100109095902", _DELIMIT, "csv"),
    (2011, "20110101074202", _DOWNLOADS, "csv"),
    (2012, "20120125202432", _DOWNLOADS, "csv"),
    (2013, "20130209233456", _DOWNLOADS, "csv"),
    (2014, "20140329211711", _DOWNLOADS, "csv"),
    (2015, "20150101113635", _DOWNLOADS, "csv"),
    (2016, "20160402160040", _DOWNLOADS, "csv"),
    (2017, "20170217023235", _DOWNLOADS, "csv"),
    (2018, "20180405024545", _XML, "xml"),
    (2019, "20190824102406", _DOWNLOADS, "csv"),
    (2020, "20200911155755", _DOWNLOADS, "csv"),
    (2021, "20210318003015", _DOWNLOADS, "csv"),
    (2022, "20221006052017", _DOWNLOADS, "csv"),  # Oct: shows the post-invasion Russia jump
    (2023, "20230127195053", _DOWNLOADS, "csv"),
    (2024, "20240117175959", _DOWNLOADS, "csv"),
]

# retired/renamed program tags absent from the live list's map (sanctions.py):
# FRY S&M / FRYK / FRYM (Federal Republic of Yugoslavia), Bosnian-Serb SRBH,
# pre-2008 NKOREA, TALIBAN, UNITA (Angola), Charles-Taylor-era LIBERIA,
# COTED (Cote d'Ivoire), abbreviated ZIMB, BURUNDI, and the HK-EO13936 tag.
_EXTRA_PROGRAM_COUNTRY = [
    ("FRY", "YUG"), ("MILOSEVIC", "YUG"), ("SRBH", "BIH"),
    ("NKOREA", "PRK"), ("TALIBAN", "AFG"), ("UNITA", "AGO"),
    ("LIBERIA", "LBR"), ("COTED", "CIV"), ("ZIMB", "ZWE"),
    ("BURUNDI", "BDI"), ("HK-", "CHN"),
]

# longest prefix first so SOUTH SUDAN beats SUDAN, ZIMBABWE beats ZIMB, etc.
_MERGED = sorted(_PROGRAM_COUNTRY + _EXTRA_PROGRAM_COUNTRY,
                 key=lambda kv: -len(kv[0]))

_CSV_COLS = ["ent_num", "name", "type", "program", "title", "call_sign",
             "vess_type", "tonnage", "grt", "vess_flag", "vess_owner", "remarks"]


def _filename(year: int, kind: str) -> str:
    return f"sdn_{year}.{kind}"


def fetch(force: bool = False) -> None:
    for year, ts, url, kind in PINNED:
        dest = RAW / SOURCE / _filename(year, kind)
        if dest.exists() and not force:
            continue  # resume-friendly: cached years cost no request (throttle budget)
        wb = f"https://web.archive.org/web/{ts}id_/{url}"
        for attempt in range(3):
            try:
                download(SOURCE, wb, _filename(year, kind), force=force, timeout=180)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[sdnarchive] {year} snapshot skipped: {e}")
                else:
                    time.sleep(10)
        time.sleep(6)  # Wayback throttles/403s rapid fetches


def _map_program(p: str) -> str | None:
    """Program tag -> target ISO3 (geographic programs only, thematic -> None)."""
    p = p.upper().strip()
    for prefix, iso in _MERGED:
        if p.startswith(prefix) or f" {prefix}" in p:
            return iso
    return None


def _tally(pairs: list[tuple[str, list[str]]]) -> tuple[int, dict[str, int], Counter]:
    """(ent_num, program tags) pairs -> (total, entries per ISO3, entries per tag)."""
    by_iso: dict[str, set] = {}
    progs: Counter = Counter()
    for ent, tags in pairs:
        for t in set(tags):
            progs[t] += 1
        for iso in {m for t in tags if (m := _map_program(t))}:
            by_iso.setdefault(iso, set()).add(ent)
    return len(pairs), {k: len(v) for k, v in by_iso.items()}, progs


def _split_tags(field: str) -> list[str]:
    # multi-program fields look like 'SDT] [FTO] [SDGT'
    return [t.strip(' []"') for t in re.split(r"[;\]\[]+", field) if t.strip(' []"')]


def _parse_zip(path) -> list[tuple[str, list[str]]]:
    with zipfile.ZipFile(path) as z:
        member = next(n for n in z.namelist() if n.upper().endswith("SDN.DEL"))
        text = z.read(member).decode("latin-1")
    pairs = []
    for rec in re.split(r"[\r\n]+", text):
        parts = rec.split("@")
        if len(parts) < 4 or not parts[0].strip().isdigit():
            continue
        pairs.append((parts[0].strip(), _split_tags(parts[3].strip().strip('"'))))
    return pairs

def _parse_csv(path) -> list[tuple[str, list[str]]]:
    df = pd.read_csv(path, names=_CSV_COLS, dtype=str)
    programs = df["program"].fillna("").str.replace('"', "").str.strip()
    return [(str(e), _split_tags(p)) for e, p in zip(df["ent_num"], programs)]


def _parse_xml(path) -> list[tuple[str, list[str]]]:
    xml = path.read_text(encoding="latin-1")
    pairs = []
    for i, block in enumerate(re.findall(r"<sdnEntry>(.*?)</sdnEntry>", xml, re.S)):
        uid = re.search(r"<uid>(\d+)</uid>", block)
        tags = re.findall(r"<program>([^<]+)</program>", block)
        pairs.append((uid.group(1) if uid else f"x{i}", [t.strip() for t in tags]))
    return pairs


_PARSERS = {"zip": _parse_zip, "csv": _parse_csv, "xml": _parse_xml}


def parse() -> tuple[list[Series], pd.DataFrame]:
    rows, prog_rows, missing = [], [], []
    for year, _, _, kind in PINNED:
        path = RAW / SOURCE / _filename(year, kind)
        if not path.exists():
            missing.append(year)
            continue
        try:
            pairs = _PARSERS[kind](path)
        except Exception as e:
            print(f"[sdnarchive] {year}: unparseable snapshot skipped ({e})")
            continue
        if len(pairs) < 1000:  # every 2000-2024 list holds >2,700 entries
            print(f"[sdnarchive] {year}: only {len(pairs)} records (truncated capture?) — skipped")
            continue
        total, by_iso, progs = _tally(pairs)
        rows.append(("sdnarchive/sdn_total", "WLD", year, None, float(total)))
        for iso, n in by_iso.items():
            rows.append(("sdnarchive/sdn_designations", iso, year, None, float(n)))
        for tag, n in progs.items():
            prog_rows.append({"year": year, "program": tag, "entries": n})
    if missing:
        print(f"[sdnarchive] years not cached (re-run refresh to fill): {missing}")
    if not rows:
        raise RuntimeError("sdnarchive: parsed 0 rows (Wayback fetch failed?)")

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    (pd.DataFrame(prog_rows).sort_values(["year", "entries"], ascending=[True, False])
       .to_parquet(out / "sdn_programs_by_year.parquet", index=False))

    lic = "Public domain (US Treasury); snapshots via the Internet Archive"
    url = "https://ofac.treasury.gov/sanctions-list-service"
    series_list = [
        Series(
            series_id="sdnarchive/sdn_total", source=SOURCE,
            name="OFAC SDN list: total designations (archived history)",
            unit="entries", unit_type="count", frequency="A",
            description=(
                "Total designated persons/entities/vessels on the OFAC SDN list, one "
                "pinned Wayback snapshot per year 2000-2024 (t11sdall.exe 2000-03, "
                "delimited sdn.csv 2004-17/2019-24, sdn.xml 2018). 1994-99 lists "
                "lived on ftp.fedworld.gov (never archived); 2025 has only a print "
                "PDF capture. Splices onto the live sanctions/sdn_total."),
            license=lic, url=url),
        Series(
            series_id="sdnarchive/sdn_designations", source=SOURCE,
            name="OFAC SDN designations by target-country program (archived history)",
            unit="entries", unit_type="count", frequency="A",
            description=(
                "SDN entries under geographic sanctions programs mapped to the target "
                "country (sanctions.py program map + retired tags: FRY/FRYK->YUG, "
                "SRBH->BIH, NKOREA->PRK, TALIBAN->AFG, UNITA->AGO, LIBERIA, COTED, "
                "ZIMB, BURUNDI). Thematic programs (SDGT/SDNT/NPWMD/...) excluded — "
                "see the sdn_programs_by_year side-table. Annual 2000-2024."),
            license=lic, url=url),
    ]
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
