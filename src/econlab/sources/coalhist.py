"""Long-run coal production — Rutledge (Caltech) regional workbook, 1800-2009.

The chapter-11 era scoreboard asserts Britain produced "~45%" of world coal in
1870 — a curated number the AI panel contested (range 34-55%). The existing
`energy` source starts in 1900, so this connector reaches back with David
Rutledge's supplementary workbook for "Estimating Long-Term World Coal
Production with Logit and Probit Transforms" (Int. J. of Coal Geology 85, 2011):
annual production in **metric tonnes** (native Mt, no energy-unit conversion)
for 14 world regions + a world total, compiled from IGC 1913 / World Power
Conference / DECC / EIA / BP. Result: UK 1870 = 115 Mt, world 1870 = 223 Mt —
the computed share is ~52%, and the US passes the UK in 1899 (229.6 vs 224 Mt).

Emits `coalhist/production` for the sheets that map 1:1 to a country
(GBR/USA/AUS/CHN/CAN — the US sheet already sums PA-anthracite + Eastern +
Western; "Australia" includes New Zealand, ~1% of the total) plus WLD. The
multi-country regions (France+Belgium, Europe-rest, Russia/FSU+Mongolia+PRK,
Africa, South Asia, Latin America, Japan+South Korea) and the three US
sub-regions go to the `regions` side table — they are real data but have no
honest ISO3.

Gotchas that cost real inspection: the World sheet stores **cumulative** 'q Gt'
(annual = first difference); its pre-1829 tail is a curve-fit artifact (~0.1
Mt/yr world in 1800 — absurd) and 1829 re-anchors with a +900 Mt jump, so the
world series starts 1830. Alternatives probed and rejected: OWID's Shift-Project
CSV is TWh with heterogeneous per-country energy contents (no single
tonnes-per-TWh factor — Germany's lignite breaks it); BEIS "Coal since 1853"
pre-1913 rows are decade *averages* mislabeled as years in OWID's copy; the BoE
millennium workbook has only a coal output *index* (A4), no tonnage.
"""

from __future__ import annotations

import glob
import io
import re
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download_first, get_text

SOURCE = "coalhist"
TITLE = "Long-run coal production (Rutledge, 1800-2009)"
PAGE = "http://rutledge.caltech.edu/"
DIRECT = "http://www.its.caltech.edu/~rutledge/DavidRutledgeCoalGeology.zip"
# pinned Wayback copy (original bytes via id_) in case Caltech retires the page
WAYBACK = ("https://web.archive.org/web/20250122172540id_/"
           "http://www.its.caltech.edu/~rutledge/DavidRutledgeCoalGeology.zip")
FILENAME = "DavidRutledgeCoalGeology.zip"

# Sheets that ARE a single country (Rutledge 'Definitions' sheet):
# 'United States' = PA anthracite + Eastern + Western sum; 'Australia' region
# includes New Zealand (~1% of production); 'Canada' adds only Greenland
# *reserves* (no production). Everything else is a multi-country region.
COUNTRY_SHEETS = ["United Kingdom", "United States", "Australia", "China", "Canada"]

# All annual-production region sheets -> side table (label 'p Mt' at col 4)
REGION_SHEETS = [
    "United Kingdom", "Pennsylvania anthracite", "France and Belgium",
    "Japan and South Korea", "Australia", "China", "Africa", "Europe",
    "Russia", "Western United States", "Eastern United States", "Canada",
    "South Asia", "Latin America", "United States",
]

# sheet names that don't resolve through the WDI Short/Table-name map
_NAME_OVERRIDE: dict[str, str] = {
    "united states": "USA",  # WDI short name is 'United States' — kept as backstop
}

WORLD_START = 1830  # pre-1829 world cumulative is fit junk; 1829 is a splice jump


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


def fetch(force: bool = False) -> None:
    urls: list[str] = []
    try:  # resolve the current zip link from the page (sipri pattern)
        html = get_text(PAGE)
        m = re.search(r'href="(https?://[^"]*rutledge[^"]*\.zip)"', html, re.I)
        if m:
            urls.append(m.group(1))
    except Exception:
        pass
    for u in (DIRECT, WAYBACK):
        if u not in urls:
            urls.append(u)
    download_first(SOURCE, urls, FILENAME, force=force)


def _find_label(df: pd.DataFrame, label: str) -> tuple[int, int]:
    for i in range(min(30, len(df))):
        for j in range(df.shape[1]):
            if str(df.iloc[i, j]).strip() == label:
                return i, j
    raise ValueError(f"coalhist: no {label!r} column found")


def _sheet_series(xl: pd.ExcelFile, sheet: str, label: str) -> pd.DataFrame:
    """Extract (year, value) where `label` heads the value column and the year
    column sits immediately to its left (the workbook's uniform layout)."""
    df = pd.read_excel(xl, sheet_name=sheet, header=None)
    _, j = _find_label(df, label)
    out = pd.DataFrame({
        "year": pd.to_numeric(df[j - 1], errors="coerce"),
        "value": pd.to_numeric(df[j], errors="coerce"),
    }).dropna()
    out = out[out["year"].between(1700, 2100)]
    out["year"] = out["year"].astype(int)
    return out.sort_values("year").reset_index(drop=True)


def parse() -> tuple[list[Series], pd.DataFrame]:
    with zipfile.ZipFile(RAW / SOURCE / FILENAME) as z:
        member = next(n for n in z.namelist() if n.lower().endswith((".xlsm", ".xlsx")))
        xl = pd.ExcelFile(io.BytesIO(z.read(member)), engine="openpyxl")

    # --- regional panel (annual production, Mt) ---
    regions: dict[str, pd.DataFrame] = {
        sheet: _sheet_series(xl, sheet, "p Mt") for sheet in REGION_SHEETS
    }

    # --- world: first-difference the cumulative 'q Gt' column ---
    wq = _sheet_series(xl, "World coal", "q Gt")
    if not wq["year"].diff().dropna().eq(1).all():
        raise ValueError("coalhist: World coal year column is not consecutive")
    wq["mt"] = wq["value"].diff() * 1000.0  # Gt cumulative -> Mt annual
    world = wq[wq["year"] >= WORLD_START][["year", "mt"]].dropna()

    # --- obs: single-country sheets + WLD ---
    name_map = _wdi_name_map()

    def to_iso3(name: str) -> str | None:
        key = name.strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    rows, unmapped = [], []
    for sheet in COUNTRY_SHEETS:
        iso = to_iso3(sheet)
        if iso is None:
            unmapped.append(sheet)
            continue
        for _, r in regions[sheet].iterrows():
            rows.append(("coalhist/production", iso, int(r["year"]), None,
                         float(r["value"]) * 1e6))
    for _, r in world.iterrows():
        rows.append(("coalhist/production", "WLD", int(r["year"]), None,
                     float(r["mt"]) * 1e6))
    if unmapped:
        print(f"[coalhist] unmapped country names (skipped): {sorted(unmapped)}")

    # --- side table: the full regional panel incl. multi-country regions ---
    side = pd.concat(
        [df.assign(region=name).rename(columns={"value": "mt"})[["region", "year", "mt"]]
         for name, df in regions.items()]
        + [world.assign(region="World")[["region", "year", "mt"]]],
        ignore_index=True,
    )
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    side.to_parquet(out / "regions.parquet", index=False)

    series_list = [
        Series(
            series_id="coalhist/production",
            source=SOURCE,
            name="Coal production (long-run, Rutledge)",
            unit="tonnes (base units, from Mt)",
            unit_type="physical",
            frequency="A",
            description=(
                "Annual coal production in metric tonnes from David Rutledge's "
                "long-run regional workbook (IJCG 85, 2011; IGC 1913 / World Power "
                "Conference / DECC / EIA / BP compilations). GBR 1830-2009, USA "
                "1800-2009 (PA anthracite + Eastern + Western), AUS 1829-2009 "
                "(region includes New Zealand, ~1%), CHN 1896-2009, CAN 1858-2009; "
                "WLD 1830-2009 = first difference of the cumulative 'q Gt' series "
                "(pre-1830 dropped: curve-fit tail + 1829 splice). Computes the "
                "era-scoreboard claim: UK share of world coal 1870 = 115/223 Mt "
                "= ~52%; US passes UK in 1899. Multi-country regions (France+"
                "Belgium, rest-of-Europe, Russia/FSU, Africa, South Asia, Latin "
                "America, Japan+S.Korea, US sub-regions) live in the coalhist/"
                "regions side table."
            ),
            license="Academic supplementary data (Rutledge 2011), free download",
            url=PAGE,
        )
    ]

    if not rows:
        raise RuntimeError("coalhist: parsed 0 rows — workbook layout may have changed")
    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
