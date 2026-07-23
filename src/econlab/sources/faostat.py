"""FAOSTAT staple-grain export quantities — the food lever, measured.

Country-year export tonnage for the four staple grains (wheat, maize, rice,
soybeans), 1961-2024, from the FAOSTAT Crops & Livestock trade domain (TCL).
Makes food-lever exporter concentration computable: US maize dominance in the
1970s (~64% of world exports in 1975), Russia passing the US as #1 wheat
exporter mid-2010s (2016: RUS 25.3Mt > USA 24.0Mt), India at ~40% of rice.

The FAOSTAT REST API (faostatservices.fao.org) went auth-only in 2025/26
(every endpoint 401s "Missing Authorization Header"; the old fenixservices
host 521s), so we take the bulk normalized zip (~278MB, wdi-precedent size)
and stream-filter to Export Quantity (element 5910, unit t) x 4 items.

Gotchas handled: FAO area codes are NOT ISO3 (name-mapped via WDI + overrides);
'China' (351) is an aggregate of mainland+TWN+HKG+MAC — we keep 'China,
mainland' (41) as CHN and drop 351; regional/income aggregates (codes >=5000
plus the sub-5000 'excluding intra-trade' pseudo-areas) are dropped except
World -> WLD; historical states map to SUN/CSK/YUG, and single-successor
renames splice cleanly with zero year overlap (Sudan (former)->SDN thru 2011,
Ethiopia PDR->ETH thru 1992, Serbia and Montenegro->SRB 1992-2005,
Belgium-Luxembourg->BEL thru 1999). Rice uses FAO's derived total item 30
'Rice, paddy (rice milled equivalent)' (F0030) — the USDA-comparable milled
basis — not the paddy/husked/milled/broken product-weight splits.
"""

from __future__ import annotations

import glob
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "faostat"
TITLE = "FAOSTAT staple-grain export quantities"
URL = "https://bulks-faostat.fao.org/production/Trade_CropsLivestock_E_All_Data_(Normalized).zip"
FILENAME = "Trade_CropsLivestock_E_All_Data_Normalized.zip"
MEMBER = "Trade_CropsLivestock_E_All_Data_(Normalized).csv"
PAGE = "https://www.fao.org/faostat/en/#data/TCL"

EXPORT_QTY = 5910  # element 'Export quantity', unit t (5907-5909 are head-count variants)

# FAO item code -> crop key (item 30 = derived rice total, milled equivalent)
ITEMS = {15: "wheat", 56: "maize", 30: "rice", 236: "soybeans"}
CROP_NAMES = {"wheat": "Wheat", "maize": "Maize (corn)", "rice": "Rice (milled equivalent)",
              "soybeans": "Soya beans"}

# sub-5000 area codes that are aggregates, not countries: China (351),
# China excl-intra (265), EU(12/15/25/27-variants) excl-intra (261/266/268/269)
DROP_AREAS = {351, 265, 261, 266, 268, 269}

# former states whose rows must lose to the successor's on any (entity, year) collision
FORMER_AREAS = {15, 51, 62, 186, 206, 228, 248}  # B-Lux, CSK, ETH PDR, S&M, Sudan(f), USSR, YUG SFR

# FAO names (lowercased, ';' normalized to ',') that miss the WDI Short/Table map
_NAME_OVERRIDE = {
    "world": "WLD",
    "united states of america": "USA", "russian federation": "RUS", "ussr": "SUN",
    "china, mainland": "CHN", "china, hong kong sar": "HKG",
    "china, macao sar": "MAC", "china, taiwan province of": "TWN",
    "republic of korea": "KOR", "democratic people's republic of korea": "PRK",
    "democratic people’s republic of korea": "PRK",
    "viet nam": "VNM", "lao people's democratic republic": "LAO",
    "lao people’s democratic republic": "LAO",
    "iran (islamic republic of)": "IRN", "syrian arab republic": "SYR",
    "venezuela (bolivarian republic of)": "VEN",
    "bolivia (plurinational state of)": "BOL",
    "united republic of tanzania": "TZA", "republic of moldova": "MDA",
    "united kingdom of great britain and northern ireland": "GBR",
    "netherlands (kingdom of the)": "NLD",
    "türkiye": "TUR", "turkey": "TUR",
    "côte d'ivoire": "CIV", "côte d’ivoire": "CIV",
    "czechia": "CZE", "czech republic": "CZE", "slovakia": "SVK",
    "czechoslovakia": "CSK", "yugoslav sfr": "YUG",
    "serbia and montenegro": "SRB",   # 1992-2005, splices onto SRB (from 2006)
    "sudan (former)": "SDN",          # thru 2011, splices onto SDN (from 2012)
    "ethiopia pdr": "ETH",            # thru 1992, splices onto ETH (from 1998)
    "belgium-luxembourg": "BEL",      # thru 1999, splices onto BEL (from 2000)
    "egypt": "EGY", "yemen": "YEM", "gambia": "GMB", "bahamas": "BHS",
    "kyrgyzstan": "KGZ", "myanmar": "MMR", "north macedonia": "MKD",
    "palestine": "PSE", "cabo verde": "CPV", "timor-leste": "TLS",
    "eswatini": "SWZ", "brunei darussalam": "BRN",
    "somalia": "SOM", "nauru": "NRU",
    "micronesia (federated states of)": "FSM",
    "saint kitts and nevis": "KNA", "saint lucia": "LCA",
    "saint vincent and the grenadines": "VCT", "sao tome and principe": "STP",
    "democratic republic of the congo": "COD", "congo": "COG",
    "réunion": "REU", "reunion": "REU", "french guiana": "GUF",
    "guadeloupe": "GLP", "martinique": "MTQ", "french polynesia": "PYF",
    "new caledonia": "NCL", "cook islands": "COK", "niue": "NIU",
    "faroe islands": "FRO",
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, timeout=900)


def _wdi_name_map() -> dict[str, str]:
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


def _load_filtered() -> pd.DataFrame:
    """Stream the 2.4GB normalized CSV out of the zip, keeping only the
    4 items x Export Quantity (~45k of ~40M rows)."""
    zf = zipfile.ZipFile(RAW / SOURCE / FILENAME)
    chunks = []
    with zf.open(MEMBER) as f:
        for ch in pd.read_csv(
            f, chunksize=2_000_000, encoding="utf-8",
            usecols=["Area Code", "Area", "Item Code", "Element Code", "Year", "Unit", "Value"],
            dtype={"Area Code": "int32", "Item Code": "int32",
                   "Element Code": "int32", "Year": "int32"},
        ):
            m = ch[(ch["Element Code"] == EXPORT_QTY) & (ch["Item Code"].isin(ITEMS))]
            if len(m):
                chunks.append(m)
    if not chunks:
        raise RuntimeError("faostat: no Export Quantity rows found — bulk layout changed?")
    return pd.concat(chunks, ignore_index=True)


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = _load_filtered()

    bad_units = set(df["Unit"].unique()) - {"t", "tonnes"}
    if bad_units:
        raise RuntimeError(f"faostat: unexpected units {bad_units} for Export Quantity")

    # areas: drop aggregates (>=5000 except World, China-351, excl-intra pseudo-areas)
    df = df[~df["Area Code"].isin(DROP_AREAS)]
    df = df[(df["Area Code"] < 5000) | (df["Area Code"] == 5000)]
    df = df[~df["Area"].str.contains("excluding intra-trade", case=False, na=False)]

    name_map = _wdi_name_map()

    def to_iso3(name: str) -> str | None:
        key = str(name).replace(";", ",").strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    area_names = df[["Area Code", "Area"]].drop_duplicates()
    iso = {r["Area Code"]: to_iso3(r["Area"]) for _, r in area_names.iterrows()}
    unmapped = sorted({str(r["Area"]) for _, r in area_names.iterrows()
                       if iso.get(r["Area Code"]) is None and r["Area Code"] != 5000})
    if unmapped:
        print(f"[faostat] unmapped area names (skipped): {unmapped}")

    df["entity"] = df["Area Code"].map(lambda c: "WLD" if c == 5000 else iso.get(c))
    df = df[df["entity"].notna()].copy()

    df["value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["crop"] = df["Item Code"].map(ITEMS)
    df["series_id"] = "faostat/export_qty." + df["crop"]

    # successor splice guard: on any (series, entity, year) collision the
    # modern area's row wins over the former state's (zero overlap in the
    # 2025-12 vintage; this protects against future vintages introducing one)
    df["is_former"] = df["Area Code"].isin(FORMER_AREAS)
    df = (df.sort_values("is_former", ascending=False)
            .drop_duplicates(subset=["series_id", "entity", "Year"], keep="last"))

    obs = df.rename(columns={"Year": "year"})[["series_id", "entity", "year", "value"]].copy()
    obs["date"] = None
    obs = obs[["series_id", "entity", "year", "date", "value"]].sort_values(
        ["series_id", "entity", "year"]).reset_index(drop=True)

    series_list = [
        Series(
            series_id=f"faostat/export_qty.{crop}",
            source=SOURCE,
            name=f"Exports: {CROP_NAMES[crop]} (quantity)",
            unit="tonnes",
            unit_type="physical",
            frequency="A",
            description=(
                f"FAOSTAT TCL Export Quantity (element 5910) for {CROP_NAMES[crop]} "
                f"(item {code}), country-year tonnes 1961-2024 from the bulk "
                "normalized zip. Entity WLD = FAO World aggregate; regional/income "
                "aggregates dropped; 'China, mainland' kept as CHN (aggregate China "
                "351 dropped; TWN/HKG/MAC separate). Historical: USSR->SUN, "
                "Czechoslovakia->CSK, Yugoslav SFR->YUG; Sudan (former)->SDN, "
                "Ethiopia PDR->ETH, Serbia and Montenegro->SRB, Belgium-Luxembourg"
                "->BEL splice with zero year overlap."
                + (" Rice = FAO derived total item 30, milled-equivalent basis "
                   "(USDA-comparable), not product-weight forms." if crop == "rice" else "")
            ),
            license="CC BY 4.0 (FAO open data policy)",
            url=PAGE,
        )
        for code, crop in ITEMS.items()
    ]

    if not len(obs):
        raise RuntimeError("faostat: parsed 0 rows")
    return series_list, obs
