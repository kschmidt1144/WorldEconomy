"""SIPRI Military Expenditure Database — the military lever, measured.

The canonical cross-country record of military spending, 1949-2025. The xlsx
filename is version-stamped (SIPRI-Milex-data-1949-2025_v1.2.xlsx), so fetch
resolves the current link from the database page (same pattern as shiller) with
the last-known URL as a fallback.

Emits per-country constant-(2024)-US$ spending (`sipri/milex_constusd`, base
units from millions) and share of GDP (`sipri/milex_gdp`, percent — the sheet
stores fractions, we x100), plus the World total from the Regional-totals sheet
(entity WLD; SIPRI says a meaningful world total starts 1988, the USSR gap).
Region/subregion label rows fall out naturally: they don't resolve to ISO3.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download_first, get_text

SOURCE = "sipri"
TITLE = "SIPRI military expenditure"
PAGE = "https://www.sipri.org/databases/milex"
FALLBACK = "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx"
FILENAME = "sipri_milex.xlsx"

# SIPRI names that don't match WDI Short/Table names
_NAME_OVERRIDE = {
    "united states of america": "USA", "russia": "RUS", "ussr": "SUN",
    "türkiye": "TUR", "turkey": "TUR", "korea, north": "PRK", "korea, south": "KOR",
    "german democratic republic": "DDR", "germany, west": "DEU", "germany": "DEU",
    "yemen, north": "YEM", "yemen": "YEM", "czechoslovakia": "CSK",
    "yugoslavia": "YUG", "cape verde": "CPV", "côte d'ivoire": "CIV",
    "côte d’ivoire": "CIV", "ivory coast": "CIV", "congo, dr": "COD",
    "congo, republic": "COG", "congo, dem. rep.": "COD", "congo, rep.": "COG",
    "kosovo": "XKX", "taiwan": "TWN", "brunei": "BRN", "laos": "LAO",
    "timor leste": "TLS", "east timor": "TLS", "trinidad & tobago": "TTO",
    "trinidad and tobago": "TTO", "bosnia-herzegovina": "BIH",
    "bosnia and herzegovina": "BIH", "macedonia, north": "MKD",
    "north macedonia": "MKD", "egypt": "EGY", "iran": "IRN", "syria": "SYR",
    "venezuela": "VEN", "vietnam": "VNM", "viet nam": "VNM",
    "kyrgyzstan": "KGZ", "kyrgyz republic": "KGZ", "slovakia": "SVK",
    "czechia": "CZE", "czech republic": "CZE", "gambia, the": "GMB",
    "gambia": "GMB", "bahamas, the": "BHS", "bahamas": "BHS",
    "eswatini": "SWZ", "swaziland": "SWZ", "south sudan": "SSD",
    "central african rep.": "CAF", "central african republic": "CAF",
    "dominican rep.": "DOM", "dominican republic": "DOM", "el salvador": "SLV",
    "guinea-bissau": "GNB", "equatorial guinea": "GNQ", "sao tome & principe": "STP",
    "são tomé and príncipe": "STP", "st. lucia": "LCA", "saint lucia": "LCA",
    "belize": "BLZ", "myanmar": "MMR", "burma": "MMR", "cambodia": "KHM",
    "south vietnam": "", "united arab emirates": "ARE", "oman": "OMN",
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


def fetch(force: bool = False) -> None:
    urls = []
    try:
        html = get_text(PAGE)
        m = re.search(r'href="(?:https?:)?(//www\.sipri\.org/sites/default/files/[^"]*Milex[^"]*\.xlsx)"', html)
        if m:
            urls.append("https:" + m.group(1))
    except Exception:
        pass
    urls.append(FALLBACK)
    download_first(SOURCE, urls, FILENAME, force=force)


def _find_header(raw: pd.DataFrame, key: str) -> int:
    for i in range(min(20, len(raw))):
        if str(raw.iloc[i, 0]).strip() == key:
            return i
    raise ValueError(f"sipri: no '{key}' header row found")


def _melt_sheet(path, sheet: str, name_map: dict[str, str]) -> tuple[pd.DataFrame, set[str]]:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = _find_header(raw, "Country")
    df = pd.read_excel(path, sheet_name=sheet, header=hdr)
    year_cols = [c for c in df.columns if isinstance(c, (int, float)) and 1900 < c < 2100]

    def to_iso3(name) -> str | None:
        key = str(name).strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    df = df.dropna(subset=["Country"])
    df["entity"] = df["Country"].map(to_iso3)
    unmapped = {
        str(n) for n, e in zip(df["Country"], df["entity"]) if e is None
    }
    df = df[df["entity"].notna()]
    long = df.melt(id_vars=["entity"], value_vars=year_cols,
                   var_name="year", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    long["year"] = long["year"].astype(int)
    return long[["entity", "year", "value"]], unmapped


def _world(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Regional totals", header=None)
    hdr = _find_header(raw, "Region")
    df = pd.read_excel(path, sheet_name="Regional totals", header=hdr)
    w = df[df["Region"].astype(str).str.strip() == "World"]
    year_cols = [c for c in df.columns if isinstance(c, (int, float)) and 1900 < c < 2100]
    long = w.melt(id_vars=["Region"], value_vars=year_cols, var_name="year", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    long["year"] = long["year"].astype(int)
    long["entity"] = "WLD"
    return long[["entity", "year", "value"]]


def parse() -> tuple[list[Series], pd.DataFrame]:
    path = RAW / SOURCE / FILENAME
    name_map = _wdi_name_map()

    const, un1 = _melt_sheet(path, "Constant (2024) US$", name_map)
    share, un2 = _melt_sheet(path, "Share of GDP", name_map)
    unmapped = {
        n for n in (un1 | un2)
        # region/subregion label rows are expected to be unmapped
        if n.lower() not in {
            "africa", "north africa", "sub-saharan africa", "americas",
            "central america and the caribbean", "north america", "south america",
            "asia & oceania", "central asia", "east asia", "oceania", "south asia",
            "south east asia", "europe", "central europe", "eastern europe",
            "western europe", "middle east",
        }
    }
    if unmapped:
        print(f"[sipri] unmapped country names (skipped): {sorted(unmapped)}")

    rows = []
    for _, r in const.iterrows():
        rows.append(("sipri/milex_constusd", r["entity"], r["year"], None, r["value"] * 1e6))
    for _, r in _world(path).iterrows():
        rows.append(("sipri/milex_constusd", r["entity"], r["year"], None, r["value"] * 1e9))
    for _, r in share.iterrows():
        rows.append(("sipri/milex_gdp", r["entity"], r["year"], None, r["value"] * 100.0))

    series_list = [
        Series(
            series_id="sipri/milex_constusd", source=SOURCE,
            name="Military expenditure (constant 2024 US$)",
            unit="2024 US$ (base units; countries from millions, World from billions)",
            unit_type="real_usd", frequency="A",
            description=(
                "SIPRI Military Expenditure Database: military spending per country "
                "1949-2025 in constant (2024) US$; World total (entity WLD) from the "
                "Regional-totals sheet, meaningful from 1988 (USSR data gap before)."
            ),
            license="SIPRI (free re-use with attribution)", url=PAGE,
        ),
        Series(
            series_id="sipri/milex_gdp", source=SOURCE,
            name="Military expenditure (% of GDP)",
            unit="% of GDP", unit_type="percent", frequency="A",
            description=(
                "SIPRI Military Expenditure Database: military spending as a share of "
                "GDP, 1949-2025 (source sheet stores fractions; scaled to 0-100)."
            ),
            license="SIPRI (free re-use with attribution)", url=PAGE,
        ),
    ]

    if not rows:
        raise RuntimeError("sipri: parsed 0 rows — sheet layout may have changed")
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
