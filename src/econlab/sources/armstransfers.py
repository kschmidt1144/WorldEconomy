"""SIPRI Arms Transfers Database — who arms whom, in TIV.

The other half of SIPRI: the `sipri` connector covers military *spending*; this
one covers the arms *trade* — transfers of major conventional weapons by
supplier and recipient, 1950→, measured in SIPRI trend-indicator values (TIV).
TIV is a military-capability *volume* index (production-cost-based weights per
weapon system), NOT dollars — never mix it with trade or milex series.

The legacy `armstrade.sipri.org/armstrade/html/export_values.php` form endpoint
is dead (redirects to the database landing page, then 404). The new
armstransfers.sipri.org SPA talks to `atbackend.sipri.org`, whose *public*
(`/api/p`) routes answer without auth: POST `/trades/import-export-csv-str/`
with a filter payload returns the full supplier-year or recipient-year TIV
table as a CSV string in JSON. `orderbyseller` in the filter list flips the
table from recipients (imports) to suppliers (exports); DeliveryType=delivered,
Status=0 reproduce the published tables. Values come rounded to whole TIV
millions ('0' = a real 0–0.5 delivery; empty = none identified).

Non-state armed groups ('*') and international organisations ('**' — NATO, UN,
EU, AU, OSCE) are deliberately skipped; the world totals row lands on WLD.
"""

from __future__ import annotations

import csv
import glob
import io
import json
import time

import pandas as pd
import requests

from ..catalog import Series
from ..config import RAW
from ..fetch import USER_AGENT, get_text, save_bytes

SOURCE = "armstransfers"
TITLE = "SIPRI arms transfers (TIV by supplier/recipient)"
API = "https://atbackend.sipri.org/api/p/trades"
PAGE = "https://www.sipri.org/databases/armstransfers"
START_YEAR = 1950
FALLBACK_MAX_YEAR = 2025

# view -> (filename, extra pseudo-filter rows)
VIEWS = {
    "tiv_exports": ("tiv_exports.json", True),   # orderbyseller -> supplier rows
    "tiv_imports": ("tiv_imports.json", False),  # default -> recipient rows
}

# SIPRI names that don't match WDI Short/Table names. "" = deliberate skip
# (defunct half-states and non-ISO territories; '*'-suffixed rows are filtered
# before this map even runs).
_NAME_OVERRIDE = {
    "soviet union": "SUN", "russia": "RUS", "east germany (gdr)": "DDR",
    "czechoslovakia": "CSK", "yugoslavia": "YUG",
    "turkiye": "TUR", "türkiye": "TUR", "turkey": "TUR",
    "north korea": "PRK", "south korea": "KOR",
    "viet nam": "VNM", "vietnam": "VNM", "south vietnam": "",
    "yemen": "YEM", "north yemen": "YEM",
    "yemen arab republic (north yemen)": "YEM", "south yemen": "",
    "cote d'ivoire": "CIV", "cote d’ivoire": "CIV",
    "côte d'ivoire": "CIV", "côte d’ivoire": "CIV",
    "dr congo": "COD", "congo": "COG",
    "bosnia-herzegovina": "BIH", "north macedonia": "MKD",
    "czechia": "CZE", "slovakia": "SVK", "kyrgyzstan": "KGZ",
    "brunei": "BRN", "bahamas": "BHS", "gambia": "GMB", "laos": "LAO",
    "syria": "SYR", "iran": "IRN", "egypt": "EGY", "venezuela": "VEN",
    "somalia": "SOM",
    "myanmar": "MMR", "taiwan": "TWN", "kosovo": "XKX", "palestine": "PSE",
    "saint vincent": "VCT", "saint kitts and nevis": "KNA",
    "saint lucia": "LCA", "eswatini": "SWZ", "timor-leste": "TLS",
    "cabo verde": "CPV", "micronesia": "FSM",
    # non-ISO territories / secessionist states — no warehouse entity
    "northern cyprus": "", "western sahara": "", "katanga": "", "biafra": "",
    "unknown supplier(s)": "", "unknown recipient(s)": "",
    # world totals rows
    "total world export": "WLD", "total world import": "WLD",
}


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


def _filters(y0: int, y1: int, by_seller: bool) -> dict:
    """Reproduce the SPA's filter payload for the published delivered-TIV table."""
    f = [{"field": "Year range 1", "oldField": "", "condition": "contains",
          "value1": str(y0), "value2": str(y1), "listData": []}]
    if by_seller:
        f.append({"field": "orderbyseller", "oldField": "", "condition": "",
                  "value1": "", "value2": "", "listData": []})
    f.append({"field": "DeliveryType", "oldField": "", "condition": "",
              "value1": "delivered", "value2": "", "listData": []})
    f.append({"field": "Status", "oldField": "", "condition": "",
              "value1": "0", "value2": "", "listData": []})
    return {"filters": f, "logic": "AND"}


def _max_year() -> int:
    try:
        return int(get_text(f"{API}/getMaxYear").strip())
    except Exception:
        return FALLBACK_MAX_YEAR


def fetch(force: bool = False) -> None:
    if not force and all((RAW / SOURCE / fn).exists() for fn, _ in VIEWS.values()):
        return
    y1 = _max_year()
    for view, (fn, by_seller) in VIEWS.items():
        dest = RAW / SOURCE / fn
        if dest.exists() and not force:
            continue
        r = requests.post(
            f"{API}/import-export-csv-str/",
            json=_filters(START_YEAR, y1, by_seller),
            headers={"User-Agent": USER_AGENT},
            timeout=300,
        )
        r.raise_for_status()
        payload = r.json()
        if len(payload.get("result", "").split("\n")) <= 12:
            raise RuntimeError(f"armstransfers: {view} came back empty — API filter shape changed?")
        save_bytes(SOURCE, fn, json.dumps(payload).encode(),
                   f"{API}/import-export-csv-str/#{view}-{START_YEAR}-{y1}")
        time.sleep(1.0)  # polite: two heavy queries


def _parse_table(fn: str) -> tuple[pd.DataFrame, set[str]]:
    """One CSV-in-JSON table -> long (name, year, value) + set of unmapped names."""
    text = json.loads((RAW / SOURCE / fn).read_text())["result"]
    lines = text.split("\n")
    hi = next((i for i, ln in enumerate(lines)
               if ln.startswith(("Exports by,", "Recipient,", "Imports by,"))), None)
    if hi is None:
        raise RuntimeError(f"armstransfers: no header row in {fn} — layout changed?")
    hdr = next(csv.reader(io.StringIO(lines[hi])))
    year_cols = [(j, int(c)) for j, c in enumerate(hdr)
                 if c.strip().isdigit() and 1900 < int(c) < 2100]

    rows, names = [], []
    for ln in lines[hi + 1:]:
        if not ln.strip():
            continue
        row = next(csv.reader(io.StringIO(ln)))
        name = row[0].strip()
        if name.endswith("*"):        # armed groups (*) and intl orgs (**)
            continue
        names.append(name)
        for j, yr in year_cols:
            if j < len(row):
                v = row[j].strip()    # '0 ' (trailing space) = 0-0.5 TIVm delivery
                if v != "":
                    rows.append((name, yr, float(v)))
    return pd.DataFrame(rows, columns=["name", "year", "value"]), set(names)


def parse() -> tuple[list[Series], pd.DataFrame]:
    name_map = _wdi_name_map()

    def to_iso3(name: str) -> str | None:
        key = name.strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    frames, unmapped = [], set()
    for view, (fn, _) in VIEWS.items():
        df, names = _parse_table(fn)
        df["entity"] = df["name"].map(to_iso3)
        unmapped |= {n for n in names if to_iso3(n) is None
                     and n.strip().lower() not in _NAME_OVERRIDE}
        df = df[df["entity"].notna()]
        # sum name variants that land on one entity (North Yemen + YAR -> YEM)
        df = df.groupby(["entity", "year"], as_index=False)["value"].sum()
        df["series_id"] = f"{SOURCE}/{view}"
        frames.append(df[["series_id", "entity", "year", "value"]])
    if unmapped:
        print(f"[armstransfers] unmapped names (skipped): {sorted(unmapped)}")

    obs = pd.concat(frames, ignore_index=True)
    obs["date"] = None
    obs = obs[["series_id", "entity", "year", "date", "value"]]

    common = dict(
        source=SOURCE, unit="SIPRI TIV, millions", unit_type="index",
        frequency="A", per_capita=False,
        license="SIPRI Arms Transfers Database © SIPRI (free re-use with attribution)",
        url=PAGE,
    )
    series_list = [
        Series(
            series_id=f"{SOURCE}/tiv_exports",
            name="Arms exports (SIPRI trend-indicator value)",
            description=(
                "Volume of major conventional weapons DELIVERED by each supplier "
                "per year, 1950-, in millions of SIPRI trend-indicator values. "
                "TIV weights each weapon system by production cost as a proxy for "
                "military capability — a volume index of arms flows, NOT dollars "
                "or sale prices. Entity WLD = SIPRI world total; SUN/RUS, CSK, "
                "YUG, DDR split as in the source. Fetched from the public "
                "atbackend.sipri.org API behind armstransfers.sipri.org."
            ),
            **common,
        ),
        Series(
            series_id=f"{SOURCE}/tiv_imports",
            name="Arms imports (SIPRI trend-indicator value)",
            description=(
                "Volume of major conventional weapons RECEIVED by each recipient "
                "per year, 1950-, in millions of SIPRI trend-indicator values "
                "(military-capability volume index, NOT dollars). Non-state armed "
                "groups and international organisations in the SIPRI table are "
                "excluded; entity WLD = SIPRI world total."
            ),
            **common,
        ),
    ]

    if obs.empty:
        raise RuntimeError("armstransfers: parsed 0 rows — API response shape changed?")
    return series_list, obs
