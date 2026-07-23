"""IMF lending arrangements — the 'Washington consensus' lever, measured.

The IMF Members' Financial Data pages (extarr1/extarr2.aspx) hide a complete
per-country ledger of lending commitments back to the 1950s: every arrangement
(SBA, EFF, ECF/ESAF/SAF, FCL, PLL, RSF, ...) and outright emergency loan
(RFI/RCF), with approval date, expiration, and amounts agreed/drawn/outstanding
in thousands of SDRs. fetch() resolves the member list from extarr1.aspx and
pulls each member's history as TSV (extarr2.aspx?...&tsvflag=Y) at a pinned
as-of date (VINTAGE-style, bump ASOF for a fresh cut). Members that never
borrowed return an HTML page instead of TSV — Germany, Switzerland, Canada,
the Nordics, Saudi Arabia never had one; the US (1963-64), UK (last 1976),
Japan (1962-64) and France all borrowed under Bretton Woods.

Emits `imflending/arrangements_new` (WLD count of new conditionality-bearing
arrangements approved per year — outright RFI/RCF loans and 'of which'
sub-facility rows excluded) and `imflending/under_program` (1 per country-year
with an arrangement active between approval and expiration), plus a side-table
`arrangements` with every row of the ledger.
"""

from __future__ import annotations

import glob
import re
import time

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "imflending"
TITLE = "IMF lending arrangements (extarr history)"
BASE = "https://www.imf.org/external/np/fin/tad"
EXTARR1 = f"{BASE}/extarr1.aspx"
ASOF = "2026-06-30"  # pinned as-of date (vintage); bump for a fresh cut

# extarr member names that don't resolve via the WDI Short/Table-name map
# (after the generic ', The' / ', Republic of' suffix strip below)
_NAME_OVERRIDE = {
    "korea": "KOR", "china": "CHN", "cote d'ivoire": "CIV",
    "congo, democratic republic of": "COD", "congo, republic of": "COG",
    "lao people's democratic republic": "LAO", "sao tome & principe": "STP",
    "türkiye": "TUR", "turkiye": "TUR", "turkey": "TUR",
    "egypt": "EGY", "iran": "IRN", "iran, islamic republic of": "IRN",
    "syrian arab republic": "SYR", "yemen": "YEM", "venezuela": "VEN",
    "vietnam": "VNM", "kyrgyz republic": "KGZ", "czech republic": "CZE",
    "eswatini, the kingdom of": "SWZ", "eswatini": "SWZ",
    "micronesia, federated states of": "FSM",
    "timor-leste, the democratic republic of": "TLS", "timor-leste": "TLS",
    "north macedonia": "MKD", "kosovo": "XKX", "bahamas": "BHS",
    "gambia": "GMB", "netherlands": "NLD", "st. kitts and nevis": "KNA",
    "st. lucia": "LCA", "st. vincent and the grenadines": "VCT",
    "cabo verde": "CPV", "russian federation": "RUS", "slovak republic": "SVK",
    "somalia": "SOM",
    "afghanistan, islamic republic of": "AFG", "afghanistan": "AFG",
}

# strip these trailing descriptors before the name lookup
_SUFFIXES = (
    ", the democratic republic of", ", federated states of",
    ", islamic republic of", ", the kingdom of", ", kingdom of",
    ", republic of", ", the",
)

# facility strings that are outright disbursements, NOT conditionality-bearing
# arrangements (emergency loans; no program reviews attached)
_OUTRIGHT = re.compile(
    r"rapid financing|rapid credit|emergency|trust fund loan", re.I)

_DATE = re.compile(r"^[A-Z][a-z]{2} \d{2}, \d{4}$")


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


def _member_keys() -> list[tuple[str, str]]:
    """(memberkey, display name) pairs from the cached extarr1 select."""
    html = (RAW / SOURCE / "extarr1.html").read_text(errors="replace")
    m = re.search(r'<select[^>]*name="memberkey1"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        raise RuntimeError("imflending: no memberkey1 select on extarr1.aspx")
    opts = re.findall(r'<option[^>]*value="(\d+)"[^>]*>\s*([^<]*?)\s*</option>', m.group(1))
    return [(k, re.sub(r"\s+", " ", v)) for k, v in opts]


def fetch(force: bool = False) -> None:
    download(SOURCE, EXTARR1, "extarr1.html", force=force)
    for key, name in _member_keys():
        fn = f"hist_{int(key):04d}.tsv"
        url = f"{BASE}/extarr2.aspx?date1key={ASOF}&memberkey1={key}&tsvflag=Y"
        cached = (RAW / SOURCE / fn).exists() and not force
        for attempt in range(3):
            try:
                download(SOURCE, url, fn, force=force, timeout=120)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[imflending] {name} (key {key}) skipped: {e}")
                time.sleep(2.0)
        if not cached:
            time.sleep(0.25)  # be polite: ~190 requests against imf.org


def _to_iso3(display: str, name_map: dict[str, str]) -> str | None:
    key = display.strip().lower()
    if key in _NAME_OVERRIDE:
        return _NAME_OVERRIDE[key] or None
    if key in name_map:
        return name_map[key]
    for suf in _SUFFIXES:
        if key.endswith(suf):
            stem = key[: -len(suf)].strip()
            if stem in _NAME_OVERRIDE:
                return _NAME_OVERRIDE[stem] or None
            if stem in name_map:
                return name_map[stem]
    return None


def _num(s: str) -> float | None:
    s = s.strip().replace(",", "")
    if not s or s in {"-", "--", "n.a."}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_one(text: str) -> tuple[str, list[dict]] | None:
    """One member TSV -> (display name, arrangement rows). None if not a TSV
    (members with no borrowing history get an HTML page instead)."""
    head = text.lstrip()[:200].lower()
    if head.startswith("<!doctype") or head.startswith("<html"):
        return None
    lines = text.splitlines()
    title = next((ln for ln in lines if ln.strip()), "")
    country = title.split(": History of Lending", 1)[0].strip()
    if not country:
        return None
    rows = []
    for ln in lines:
        f = ln.split("\t")
        if len(f) < 6 or not _DATE.match(f[1].strip()):
            continue
        facility = re.sub(r"<[^>]+>", "", f[0])       # stray <sup>1/</sup> tags
        facility = re.sub(r"\s*\d+/\s*$", "", facility)  # trailing footnote tokens
        facility = re.sub(r"\s+", " ", facility).strip()
        sub = facility.lower().startswith("of which")
        rows.append({
            "type": re.sub(r"(?i)^of which\s+", "", facility),
            "sub_row": sub,
            "approved": pd.to_datetime(f[1].strip(), format="%b %d, %Y"),
            "expired": (pd.to_datetime(f[2].strip(), format="%b %d, %Y")
                        if _DATE.match(f[2].strip()) else pd.NaT),
            "agreed_thsdr": _num(f[3]),
            "drawn_thsdr": _num(f[4]),
            "outstanding_thsdr": _num(f[5]),
        })
    return country, rows


def parse() -> tuple[list[Series], pd.DataFrame]:
    name_map = _wdi_name_map()
    records, unmapped = [], set()
    for p in sorted((RAW / SOURCE).glob("hist_*.tsv")):
        got = _parse_one(p.read_text(errors="replace"))
        if got is None:
            continue  # member never borrowed — HTML page, not TSV
        country, rows = got
        iso = _to_iso3(country, name_map)
        if iso is None:
            unmapped.add(country)
            continue
        for r in rows:
            r["country"], r["entity"] = country, iso
            records.append(r)
    if unmapped:
        print(f"[imflending] unmapped country names (skipped): {sorted(unmapped)}")
    if not records:
        raise RuntimeError("imflending: parsed 0 arrangements — page layout changed?")

    arr = pd.DataFrame(records)
    arr["outright"] = arr["type"].str.contains(_OUTRIGHT)
    arr["amount_agreed_sdr"] = arr["agreed_thsdr"] * 1e3    # thousands -> base SDR
    arr["amount_drawn_sdr"] = arr["drawn_thsdr"] * 1e3

    # --- side-table: the full ledger ('of which' sub-facility rows are slices
    # of a parent arrangement — flagged, not dropped, but excluded from obs) ---
    side = arr[["country", "entity", "type", "sub_row", "outright",
                "approved", "expired", "amount_agreed_sdr", "amount_drawn_sdr"]].copy()
    side = side.sort_values(["entity", "approved"]).reset_index(drop=True)
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    side.to_parquet(out / "arrangements.parquet", index=False)

    # conditionality-bearing arrangements only, one row each
    main = arr[~arr["sub_row"] & ~arr["outright"]].copy()

    rows = []
    # imflending/arrangements_new — WLD count of approvals per year
    new_by_year = main.groupby(main["approved"].dt.year).size()
    for yr, n in new_by_year.items():
        rows.append(("imflending/arrangements_new", "WLD", int(yr), None, float(n)))

    # imflending/under_program — 1 per country-year with an active arrangement,
    # clipped at the vintage year (scheduled future expirations aren't history)
    asof_year = int(ASOF[:4])
    seen: set[tuple[str, int]] = set()
    for _, r in main.iterrows():
        y0 = int(r["approved"].year)
        y1 = int(r["expired"].year) if pd.notna(r["expired"]) else y0
        for yr in range(y0, min(max(y0, y1), asof_year) + 1):
            seen.add((r["entity"], yr))
    for ent, yr in sorted(seen):
        rows.append(("imflending/under_program", ent, yr, None, 1.0))

    series_list = [
        Series(
            series_id="imflending/arrangements_new", source=SOURCE,
            name="IMF arrangements approved (world, per year)",
            unit="arrangements approved", unit_type="count", frequency="A",
            description=(
                "Count of new IMF lending arrangements approved per year, from the "
                "per-member History of Lending Commitments (extarr2.aspx), 1952-. "
                "Conditionality-bearing arrangements only (SBA/EFF/ECF/ESAF/SAF/FCL/"
                "PLL/RSF...); outright RFI/RCF emergency loans and 'of which' "
                "sub-facility rows excluded. Entity WLD."
            ),
            license="IMF (public financial data)", url=EXTARR1,
        ),
        Series(
            series_id="imflending/under_program", source=SOURCE,
            name="Country under an IMF arrangement (indicator)",
            unit="1 = arrangement active in year", unit_type="count", frequency="A",
            description=(
                "1 for each country-year in which an IMF conditionality-bearing "
                "arrangement was active (approval year through expiration year "
                "inclusive; cancelled arrangements carry their actual end date). "
                "Sum over entities = countries under IMF programs that year; the "
                "'Washington consensus' lever, computed. Never-borrowers (Germany, "
                "Switzerland, Canada, the Nordics, Saudi Arabia) never appear — but "
                "the US (1963-64), UK (1956-77) and Japan (1962-64) do, from the "
                "Bretton Woods era."
            ),
            license="IMF (public financial data)", url=EXTARR1,
        ),
    ]
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
