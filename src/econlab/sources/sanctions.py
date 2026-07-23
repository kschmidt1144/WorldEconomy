"""Sanctions — the financial weapon, in two computed pillars.

Pillar 1: EUSANCT (Konstanz), 326 post-1949 sanction cases with per-sender
(EU / US / UN) imposition and end years, targets and outcomes. The files sit
behind expiring JWT-signed URLs, so fetch resolves the current links from the
project page each time (shiller pattern). Coverage is authoritative 1989-2015;
imposition years reach back to 1950.

Pillar 2: OFAC's live SDN list — every person/entity currently designated by
the US Treasury, by sanctions program. A current-state snapshot (year = fetch
year): the reach of the US financial weapon today.

The best historical DB (GSDB, 1,547 cases 1950-2023) is email-request-only and
therefore not reproducible via `econ refresh`; its headline arc is curated in
the chapter with an AI-panel cross-check instead.

Obs series (entity WLD unless noted): `sanctions/in_force.{US,EU,UN}` (cases in
force per year, capped at EUSANCT's 2015 horizon), `sanctions/targeted` (active
cases per target country-year, entity = target ISO3), `sanctions/sdn_total`,
and `sanctions/sdn_designations` (entity = target country for the geographic
programs). Side-tables: sanction_cases.parquet, sdn_programs.parquet.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download, download_first, get_text

SOURCE = "sanctions"
TITLE = "Sanctions (EUSANCT cases + OFAC SDN)"
EUSANCT_PAGE = "https://www.polver.uni-konstanz.de/gschneider/research/archive/eusanct/"
SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
CASE_FILE = "eusanct_case.xls"
SDN_FILE = "sdn.csv"
PANEL_END = 2015  # EUSANCT coverage horizon: open-ended cases counted through here

# EUSANCT target names that don't match WDI Short/Table names
_NAME_OVERRIDE = {
    "north korea": "PRK", "south korea": "KOR", "russia": "RUS", "ussr": "SUN",
    "soviet union": "SUN", "turkey": "TUR", "türkiye": "TUR", "egypt": "EGY",
    "iran": "IRN", "syria": "SYR", "yemen": "YEM", "venezuela": "VEN",
    "vietnam": "VNM", "laos": "LAO", "myanmar": "MMR", "burma": "MMR",
    "burma/myanmar": "MMR", "cambodia": "KHM", "kampuchea": "KHM",
    "democratic republic of congo": "COD", "democratic republic of the congo": "COD",
    "congo, dr": "COD", "dr congo": "COD", "congo-kinshasa": "COD",
    "congo": "COG", "congo-brazzaville": "COG", "republic of congo": "COG",
    "ivory coast": "CIV", "cote d'ivoire": "CIV", "côte d'ivoire": "CIV",
    "côte d’ivoire": "CIV", "yugoslavia": "YUG", "fr yugoslavia": "YUG",
    "yugoslavia (serbia and montenegro)": "YUG", "serbia and montenegro": "YUG",
    "serbia": "SRB", "bosnia": "BIH", "bosnia-herzegovina": "BIH",
    "bosnia and herzegovina": "BIH", "macedonia": "MKD", "north macedonia": "MKD",
    "czechoslovakia": "CSK", "east germany": "DDR", "gdr": "DDR",
    "german democratic republic": "DDR", "taiwan": "TWN", "gambia": "GMB",
    "the gambia": "GMB", "bahamas": "BHS", "kyrgyzstan": "KGZ", "moldova": "MDA",
    "slovakia": "SVK", "czech republic": "CZE", "czechia": "CZE",
    "eswatini": "SWZ", "swaziland": "SWZ", "south sudan": "SSD", "sudan": "SDN",
    "central african republic": "CAF", "guinea-bissau": "GNB",
    "equatorial guinea": "GNQ", "zimbabwe": "ZWE", "rhodesia": "ZWE",
    "southern rhodesia": "ZWE", "belarus": "BLR", "libya": "LBY",
    "south africa": "ZAF", "haiti": "HTI", "fiji": "FJI", "somalia": "SOM",
    "afghanistan": "AFG", "iraq": "IRQ", "cuba": "CUB", "nicaragua": "NIC",
    "guatemala": "GTM", "chile": "CHL", "argentina": "ARG", "brazil": "BRA",
    "indonesia": "IDN", "china": "CHN", "india": "IND", "pakistan": "PAK",
    "sri lanka": "LKA", "thailand": "THA", "poland": "POL",
}

# OFAC program prefixes -> target country (geographic programs only; thematic
# programs like SDGT/SDNTK/GLOMAG/NPWMD/CYBER stay in the side-table unmapped)
_PROGRAM_COUNTRY = [
    ("RUSSIA", "RUS"), ("UKRAINE", "RUS"), ("BELARUS", "BLR"), ("IRAN", "IRN"),
    ("DPRK", "PRK"), ("NORTH KOREA", "PRK"), ("CUBA", "CUB"), ("SYRIA", "SYR"),
    ("VENEZUELA", "VEN"), ("BURMA", "MMR"), ("MYANMAR", "MMR"), ("IRAQ", "IRQ"),
    ("LIBYA", "LBY"), ("SOMALIA", "SOM"), ("YEMEN", "YEM"), ("ZIMBABWE", "ZWE"),
    ("NICARAGUA", "NIC"), ("DARFUR", "SDN"), ("SUDAN", "SDN"),
    ("SOUTH SUDAN", "SSD"), ("DRCONGO", "COD"), ("CAR", "CAF"), ("MALI", "MLI"),
    ("HAITI", "HTI"), ("BALKANS", "SRB"), ("LEBANON", "LBN"),
    ("AFGHANISTAN", "AFG"), ("ETHIOPIA", "ETH"), ("HONG KONG", "CHN"),
]


def fetch(force: bool = False) -> None:
    # EUSANCT: signed URLs expire, resolve fresh from the page
    urls = []
    try:
        html = get_text(EUSANCT_PAGE)
        m = re.search(r'href="(/securedl/[^"]+EUSANCT_Dataset_Case-level\.xls)"', html)
        if m:
            urls.append("https://www.polver.uni-konstanz.de" + m.group(1))
    except Exception:
        pass
    if urls:
        download_first(SOURCE, urls, CASE_FILE, force=force)
    elif not (RAW / SOURCE / CASE_FILE).exists():
        raise RuntimeError("sanctions: could not resolve EUSANCT signed URL and no cached copy")
    download(SOURCE, SDN_URL, SDN_FILE, force=True)  # live list: always refresh


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


def _eusanct(name_map: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_excel(RAW / SOURCE / CASE_FILE)

    def to_iso3(name) -> str | None:
        key = str(name).strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key]
        return name_map.get(key)

    df["entity"] = df["targetstate_name"].map(to_iso3)

    spans = []  # (caseid, sender, start, end, entity)
    for _, r in df.iterrows():
        for sender in ("US", "EU", "UN"):
            if r.get(f"imposition{sender}") == 1 and pd.notna(r.get(f"imposition{sender}_year")):
                start = int(r[f"imposition{sender}_year"])
                end_raw = r.get(f"endyear{sender}")
                end = int(end_raw) if pd.notna(end_raw) else PANEL_END
                spans.append((r["caseid"], sender, start, min(end, PANEL_END), r["entity"]))
    span_df = pd.DataFrame(spans, columns=["caseid", "sender", "start", "end", "entity"])

    rows = []
    for sender, g in span_df.groupby("sender"):
        counts: dict[int, int] = {}
        for _, s in g.iterrows():
            for yr in range(s["start"], s["end"] + 1):
                counts[yr] = counts.get(yr, 0) + 1
        for yr, n in counts.items():
            rows.append((f"sanctions/in_force.{sender}", "WLD", yr, None, float(n)))

    # active cases per target country-year (any sender, dedup by case)
    tgt = span_df.dropna(subset=["entity"])
    counts2: dict[tuple[str, int], set] = {}
    for _, s in tgt.iterrows():
        for yr in range(s["start"], s["end"] + 1):
            counts2.setdefault((s["entity"], yr), set()).add(s["caseid"])
    for (ent, yr), cases in counts2.items():
        rows.append(("sanctions/targeted", ent, yr, None, float(len(cases))))

    # side-table: one row per case
    meta = []
    for _, r in df.iterrows():
        starts = [int(r[f"imposition{s}_year"]) for s in ("US", "EU", "UN")
                  if r.get(f"imposition{s}") == 1 and pd.notna(r.get(f"imposition{s}_year"))]
        if not starts:
            continue
        ends = [int(r[f"endyear{s}"]) for s in ("US", "EU", "UN") if pd.notna(r.get(f"endyear{s}"))]
        senders = "-".join(s for s in ("US", "EU", "UN") if r.get(f"imposition{s}") == 1)
        meta.append({
            "caseid": r["caseid"], "target": r["targetstate_name"], "entity": r["entity"],
            "senders": senders, "start": min(starts), "end": max(ends) if ends else None,
            "success": r.get("success"), "sanctions_success": r.get("sanctions_success"),
        })
    return pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]), pd.DataFrame(meta)


def _sdn() -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["ent_num", "name", "type", "program", "title", "call_sign",
            "vess_type", "tonnage", "grt", "vess_flag", "vess_owner", "remarks"]
    df = pd.read_csv(RAW / SOURCE / SDN_FILE, names=cols, dtype=str)
    year = datetime.now(timezone.utc).year
    programs = df["program"].fillna("").str.replace('"', "").str.strip()
    # entries can carry several programs separated by "] ["
    prog_counts: dict[str, int] = {}
    entity_entries: dict[str, set] = {}
    for ent_num, plist in zip(df["ent_num"], programs):
        parts = [p.strip(" []") for p in re.split(r"[;\]\[]+", plist) if p.strip(" []")]
        for p in parts:
            prog_counts[p] = prog_counts.get(p, 0) + 1
        mapped = {iso for prefix, iso in _PROGRAM_COUNTRY
                  for p in parts if p.upper().startswith(prefix) or prefix in p.upper()}
        for iso in mapped:
            entity_entries.setdefault(iso, set()).add(ent_num)

    rows = [("sanctions/sdn_total", "WLD", year, None, float(len(df)))]
    for iso, ents in entity_entries.items():
        rows.append(("sanctions/sdn_designations", iso, year, None, float(len(ents))))
    prog_df = (pd.DataFrame(sorted(prog_counts.items(), key=lambda kv: -kv[1]),
                            columns=["program", "entries"]))
    return pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"]), prog_df


def parse() -> tuple[list[Series], pd.DataFrame]:
    name_map = _wdi_name_map()
    eus_obs, cases = _eusanct(name_map)
    sdn_obs, progs = _sdn()

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    cases.to_parquet(out / "sanction_cases.parquet", index=False)
    progs.to_parquet(out / "sdn_programs.parquet", index=False)

    lic_eus = "EUSANCT (Weber & Schneider 2022), free download"
    series_list = [
        Series(series_id=f"sanctions/in_force.{s}", source=SOURCE,
               name=f"Sanction cases in force (sender: {s})",
               unit="cases", unit_type="count", frequency="A",
               description=(
                   f"EUSANCT case-level DB: number of sanction cases with {s} as an "
                   f"imposing sender in force per year; open-ended cases counted "
                   f"through the dataset horizon ({PANEL_END})."),
               license=lic_eus, url=EUSANCT_PAGE)
        for s in ("US", "EU", "UN")
    ] + [
        Series(series_id="sanctions/targeted", source=SOURCE,
               name="Active sanction cases against country",
               unit="cases", unit_type="count", frequency="A",
               description=("EUSANCT: distinct active sanction cases per target "
                            f"country-year (any of EU/US/UN senders), through {PANEL_END}."),
               license=lic_eus, url=EUSANCT_PAGE),
        Series(series_id="sanctions/sdn_total", source=SOURCE,
               name="OFAC SDN list: total designations",
               unit="entries", unit_type="count", frequency="A",
               description="Live OFAC SDN list: total designated persons/entities/vessels (snapshot at fetch year).",
               license="US Treasury (public domain)", url="https://ofac.treasury.gov/sanctions-list-service"),
        Series(series_id="sanctions/sdn_designations", source=SOURCE,
               name="OFAC SDN designations by target-country program",
               unit="entries", unit_type="count", frequency="A",
               description=("Live OFAC SDN list: designations under geographic programs, "
                            "mapped to the target country (thematic programs like SDGT "
                            "excluded; see sdn_programs side-table)."),
               license="US Treasury (public domain)", url="https://ofac.treasury.gov/sanctions-list-service"),
    ]

    obs = pd.concat([eus_obs, sdn_obs], ignore_index=True)
    if obs.empty:
        raise RuntimeError("sanctions: parsed 0 rows")
    return series_list, obs
