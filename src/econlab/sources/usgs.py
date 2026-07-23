"""USGS Mineral Commodity Summaries — critical-minerals world production.

The chokepoint claims of the chip/battery era (China rare earths, DRC cobalt,
the lithium duopoly, China's gallium lock) computed from the USGS's own MCS
data releases on ScienceBase. Five editions are stitched (MCS2022-MCS2026),
each carrying two production years, giving a 2020-2025 concentration snapshot
— this is a *snapshot source*, not a long-history panel.

Formats differ per edition and all are handled here:
- MCS2026: one combined long CSV (cp1252! em dashes), world sections carry
  2024 + 2025est per country.
- MCS2025: one wide CSV inside World_Data_Release_MCS_2025.zip
  (PROD_2023 / "PROD_EST_ 2024" — note the space; commodity "Gemanium" sic).
- MCS2024: the parent's world.zip 404s on ScienceBase — per-commodity child
  items each carry mcs2024-<slug>_world.csv instead (resolved live via the
  catalog API). Country names there glue footnote markers on ("Japane",
  "Other countries4") — stripped before the ISO3 map.
- MCS2023 / MCS2022: world.zip of per-commodity wide CSVs
  (Prod_t_2021 / Prod_t_est_2022; 2022 capitalizes "Est").

Vintage precedence: editions are ingested oldest→newest and later editions
overwrite the same (series, country, year) — a year first published as an
estimate is replaced by the next edition's revised figure.

Mining vs refining is kept distinct: `usgs/mine_prod.*` is MINE production
(China ~70% of rare-earth mining — refining is higher still, ~85-90%, and not
in the MCS world tables); `usgs/refinery_prod.*` covers copper (refined),
gallium (low-purity primary) and germanium (primary+secondary refinery),
where China's shares are far above its mine shares. All values normalized to
metric tons (kt ×1000, kg ×0.001). Latest-edition reserves go to the
`reserves` side-table. Public domain (USGS).
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download, get_json

SOURCE = "usgs"
TITLE = "USGS Mineral Commodity Summaries (critical minerals)"
MCS_URL = "https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries"

_SB_ITEM = "https://www.sciencebase.gov/catalog/item/{id}"
_SB_KIDS = "https://www.sciencebase.gov/catalog/items"

# pinned ScienceBase item ids (parents of each edition's data release)
ITEMS = {
    "mcs2026": "696a75d5d4be0228872d3bf8",
    "mcs2025": "677eaf95d34e760b392c4970",
    "mcs2024": "65a6e45fd34e5af967a46749",  # world.zip 404s -> use children
    "mcs2023": "63b5f411d34e92aad3caa57f",
    "mcs2022": "6197ccbed34eb622f692ee1c",
}

# per-commodity file slug (USGS's 5-char truncation) -> commodity key
SLUG_COMMODITY = {
    "raree": "rare_earths", "lithi": "lithium", "cobal": "cobalt",
    "graph": "graphite", "nicke": "nickel", "coppe": "copper",
    "tungs": "tungsten", "plati": "pgm",  # pgm routed by Type text
    "galli": "gallium", "germa": "germanium",
}

# MCS2024 child-item title token -> slug
MCS2024_TITLES = {
    "RARE EARTHS": "raree", "LITHIUM": "lithi", "COBALT": "cobal",
    "GRAPHITE (NATURAL)": "graph", "NICKEL": "nicke", "COPPER": "coppe",
    "TUNGSTEN": "tungs", "PLATINUM": "plati", "GALLIUM": "galli",
    "GERMANIUM": "germa",
}

# MCS2025 wide-file COMMODITY (stripped) -> slug ("Gemanium" is USGS's typo)
MCS2025_COMMODITY = {
    "Rare earths": "raree", "Lithium": "lithi", "Cobalt": "cobal",
    "Graphite": "graph", "Nickel": "nicke", "Copper": "coppe",
    "Tungsten": "tungs", "Platinum-Group metals": "plati",
    "Gallium": "galli", "Gemanium": "germa",
}

# MCS2026 long-file Commodity -> slug (Germanium has no world table in 2026;
# "Platinum-Group Metals" carries only the combined PGM reserves)
MCS2026_COMMODITY = {
    "Rare Earths": "raree", "Lithium": "lithi", "Cobalt": "cobal",
    "Graphite (Natural)": "graph", "Nickel": "nicke", "Copper": "coppe",
    "Tungsten": "tungs", "Platinum": "plati", "Palladium": "plati",
    "Platinum-Group Metals": "plati", "Gallium": "galli",
}

# (commodity, kind) pairs that become series
EMIT = {
    ("rare_earths", "mine"), ("lithium", "mine"), ("cobalt", "mine"),
    ("graphite", "mine"), ("nickel", "mine"), ("copper", "mine"),
    ("tungsten", "mine"), ("platinum", "mine"), ("palladium", "mine"),
    ("copper", "refinery"), ("gallium", "refinery"), ("germanium", "refinery"),
}

# MCS names that don't match WDI Short/Table names ('' = deliberately skipped)
_NAME_OVERRIDE = {
    "burma": "MMR", "korea, north": "PRK", "north korea": "PRK",
    "korea, republic of": "KOR", "korea, south": "KOR",
    "congo (kinshasa)": "COD", "congo (brazzaville)": "COG",
    "russia": "RUS", "turkey": "TUR", "türkiye": "TUR",
    "vietnam": "VNM", "laos": "LAO", "iran": "IRN", "egypt": "EGY",
    "syria": "SYR", "venezuela": "VEN", "bolivia": "BOL",
    "czechia": "CZE", "czech republic": "CZE", "slovakia": "SVK",
    "ivory coast": "CIV", "côte d'ivoire": "CIV", "côte d’ivoire": "CIV",
    "kyrgyzstan": "KGZ", "new caledonia": "NCL", "tanzania": "TZA",
    "new caledonia (overseas territory of france)": "NCL",
    "world total": "WLD", "world total (rounded)": "WLD",
    "world production": "WLD", "world production (rounded)": "WLD",
    # USGS publishes the world total NET of withheld US production for some
    # commodities (lithium among the targets) — every edition does the same,
    # so WLD stays internally consistent (sum of published countries + other)
    "world total (rounded), excluding u.s. production": "WLD",
    "world total (rounded), excluding united states": "WLD",
    "other countries": "", "other countries (rounded)": "",
    "united states and canada": "",
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


def _item_files(item_id: str) -> list[dict]:
    j = get_json(_SB_ITEM.format(id=item_id), params={"format": "json", "fields": "files"})
    return j.get("files", []) or []


def _file_url(files: list[dict], token: str) -> str | None:
    for f in files:
        if token.lower() in str(f.get("name", "")).lower():
            return f.get("url")
    return None


def fetch(force: bool = False) -> None:
    # MCS2026: one combined long CSV on the parent item
    try:
        url = _file_url(_item_files(ITEMS["mcs2026"]), "Commodities_Data.csv")
        download(SOURCE, url, "mcs2026_commodities.csv", force=force, timeout=300)
    except Exception as e:
        print(f"[usgs] MCS2026 combined CSV failed: {e}")

    # MCS2025: World zip on the parent item
    try:
        url = _file_url(_item_files(ITEMS["mcs2025"]), "World_Data_Release")
        download(SOURCE, url, "mcs2025_world.zip", force=force, timeout=300)
    except Exception as e:
        print(f"[usgs] MCS2025 world zip failed: {e}")

    # MCS2023 / MCS2022: world.zip on the parent items
    for ed in ("mcs2023", "mcs2022"):
        try:
            url = _file_url(_item_files(ITEMS[ed]), "world.zip")
            download(SOURCE, url, f"{ed}_world.zip", force=force, timeout=300)
        except Exception as e:
            print(f"[usgs] {ed} world zip failed: {e}")

    # MCS2024: parent's world.zip is a dead link on ScienceBase — pull the
    # per-commodity children's mcs2024-<slug>_world.csv instead
    try:
        j = get_json(_SB_KIDS, params={
            "parentId": ITEMS["mcs2024"], "format": "json",
            "max": "200", "fields": "title,files",
        })
        for it in j.get("items", []):
            title = str(it.get("title", "")).upper()
            slug = next((s for tok, s in MCS2024_TITLES.items() if f"- {tok} " in title), None)
            if slug is None:
                continue
            wf = next((f for f in (it.get("files", []) or [])
                       if "_world.csv" in str(f.get("name", "")).lower()), None)
            if wf is None:
                print(f"[usgs] MCS2024 {slug}: no _world.csv on child item")
                continue
            if not wf.get("size"):  # germanium's world CSV is 0 bytes upstream
                print(f"[usgs] MCS2024 {slug}: world CSV is empty on ScienceBase, skipped")
                continue
            url = wf.get("url")
            try:
                download(SOURCE, url, f"mcs2024-{slug}_world.csv", force=force, timeout=120)
            except Exception as e:
                print(f"[usgs] MCS2024 {slug} download failed: {e}")
    except Exception as e:
        print(f"[usgs] MCS2024 children listing failed: {e}")


# ---------------------------------------------------------------- parsing

_UNIT_FACTOR = {"t": 1.0, "kt": 1000.0, "kg": 0.001}


def _unit_factor_from_text(unit_text: str) -> float | None:
    t = str(unit_text).strip().lower()
    if "thousand metric tons" in t:
        return 1000.0
    if "million metric tons" in t:
        return 1e6
    if "metric tons" in t:
        return 1.0
    if "kilogram" in t:
        return 0.001
    return None


def _clean_name(name: str) -> str:
    s = str(name).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\d+$", "", s).strip()          # glued footnote digits: 'Other countries4'
    return s.rstrip(".")


def _num(v) -> float | None:
    s = str(v).replace("\xa0", " ").strip()
    if not s or s in {"W", "NA", "XX", "--"}:
        return None
    s = s.replace(",", "").replace(" ", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return float(s)
    return None


def _classify(slug: str, type_text: str) -> tuple[str, str] | None:
    """Type/detail text -> (commodity, kind) or None to skip."""
    t = str(type_text).lower()
    if "capacity" in t or "reserve" in t:
        return None
    if slug == "plati":
        com = "palladium" if "palladium" in t else "platinum" if "platinum" in t else None
        if com is None or "mine production" not in t:
            return None
        return (com, "mine")
    com = SLUG_COMMODITY[slug]
    if "refinery production" in t or "primary production" in t:
        return (com, "refinery")
    if "mine production" in t or t.strip() == "production":
        return (com, "mine")
    return None


_PROD_COL = re.compile(r"^prod(?:_(kt|kg|t))?(?:_est)?_(\d{4})$")


def _parse_wide(df: pd.DataFrame, slug: str, unit_text: str | None,
                sink: dict, to_iso3, unmapped: set) -> None:
    """One per-commodity wide CSV (MCS2022-24 layouts, or an MCS2025 slice)."""
    prod_cols: list[tuple[str, float, int]] = []   # (col, factor, year)
    for c in df.columns:
        norm = str(c).strip().lower().replace(" ", "")
        m = _PROD_COL.match(norm)
        if not m:
            continue
        unit_tok, year = m.group(1), int(m.group(2))
        factor = _UNIT_FACTOR.get(unit_tok) if unit_tok else (
            _unit_factor_from_text(unit_text) if unit_text else None)
        if factor is None:
            continue
        prod_cols.append((c, factor, year))
    if not prod_cols:
        return
    for _, r in df.iterrows():
        if pd.isna(r.get("Country")) and pd.isna(r.get("COUNTRY")):
            continue
        country = r.get("Country", r.get("COUNTRY"))
        typ = r.get("Type", r.get("TYPE"))
        ck = _classify(slug, typ if pd.notna(typ) else "")
        if ck is None or ck not in EMIT:
            continue
        com, kind = ck
        iso = to_iso3(country)
        if iso is None:
            unmapped.add(_clean_name(country))
            continue
        if iso == "":
            continue
        sid = f"usgs/{'mine_prod' if kind == 'mine' else 'refinery_prod'}.{com}"
        for col, factor, year in prod_cols:
            val = _num(r[col])
            if val is not None:
                sink[(sid, iso, year)] = val * factor


def _read_zip_members(path, pattern: str):
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            m = re.search(pattern, name)
            if m:
                yield m.group(1), pd.read_csv(
                    io.BytesIO(zf.read(name)), dtype=str,
                    encoding="utf-8-sig", encoding_errors="replace")


def parse() -> tuple[list[Series], pd.DataFrame]:
    name_map = _wdi_name_map()
    unmapped: set[str] = set()

    def to_iso3(name) -> str | None:
        key = _clean_name(name).lower()
        for cand in (key, key[:-1] if key.endswith("e") else None):  # 'Japane' = footnote glue
            if cand is None:
                continue
            if cand in _NAME_OVERRIDE:
                return _NAME_OVERRIDE[cand]
            if cand in name_map:
                return name_map[cand]
        return None

    sink: dict[tuple[str, str, int], float] = {}

    # --- MCS2022 / MCS2023: world.zip of per-commodity wide CSVs ---
    for ed in ("mcs2022", "mcs2023"):
        path = RAW / SOURCE / f"{ed}_world.zip"
        if not path.exists():
            print(f"[usgs] missing {path.name}, skipping edition")
            continue
        for slug, df in _read_zip_members(path, rf"{ed}-(\w+)_world\.csv$"):
            if slug in SLUG_COMMODITY:
                _parse_wide(df, slug, None, sink, to_iso3, unmapped)

    # --- MCS2024: loose per-commodity CSVs from the child items ---
    for slug in SLUG_COMMODITY:
        p = RAW / SOURCE / f"mcs2024-{slug}_world.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
        _parse_wide(df, slug, None, sink, to_iso3, unmapped)

    # --- MCS2025: one wide CSV covering every commodity ---
    p25 = RAW / SOURCE / "mcs2025_world.zip"
    if p25.exists():
        for _, df in _read_zip_members(p25, r"(MCS2025_World_Data)\.csv$"):
            df["_slug"] = df["COMMODITY"].astype(str).str.strip().map(MCS2025_COMMODITY)
            for slug, sub in df[df["_slug"].notna()].groupby("_slug"):
                unit_text = sub["UNIT_MEAS"].dropna().iloc[0] if sub["UNIT_MEAS"].notna().any() else ""
                _parse_wide(sub, slug, unit_text, sink, to_iso3, unmapped)
    else:
        print("[usgs] missing mcs2025_world.zip, skipping edition")

    # --- MCS2026: combined long CSV (cp1252), world sections only ---
    p26 = RAW / SOURCE / "mcs2026_commodities.csv"
    reserves_rows: list[dict] = []
    if p26.exists():
        df = pd.read_csv(p26, dtype=str, encoding="cp1252")
        df = df[df["Section"].astype(str).str.contains("World", na=False)].copy()
        df["_slug"] = df["Commodity"].map(MCS2026_COMMODITY)
        df = df[df["_slug"].notna()]
        w = df[df["Statistics"] == "Production"].copy()
        # rounded rows first so exact figures overwrite them for the same key
        w["_rounded"] = w["Statistics_detail"].astype(str).str.contains("rounded", case=False)
        for _, r in pd.concat([w[w["_rounded"]], w[~w["_rounded"]]]).iterrows():
            ck = _classify(r["_slug"], r["Statistics_detail"])
            if ck is None or ck not in EMIT:
                continue
            com, kind = ck
            iso = to_iso3(r["Country"])
            if iso is None:
                unmapped.add(_clean_name(r["Country"]))
                continue
            if iso == "":
                continue
            factor = _unit_factor_from_text(r["Unit"])
            val = _num(r["Value"])
            if factor is None or val is None:
                continue
            sid = f"usgs/{'mine_prod' if kind == 'mine' else 'refinery_prod'}.{com}"
            sink[(sid, iso, int(r["Year"]))] = val * factor

        # latest-edition reserves -> side-table
        rsv = df[df["Statistics"] == "Reserves"]
        for _, r in rsv.iterrows():
            slug = r["_slug"]
            det = str(r["Statistics_detail"]).lower()
            if slug == "plati":
                com = ("palladium" if "palladium" in det
                       else "pgm" if "pgm" in det or "group" in det else "platinum")
            else:
                com = SLUG_COMMODITY[slug]
            iso = to_iso3(r["Country"])
            factor = _unit_factor_from_text(r["Unit"])
            val = _num(r["Value"])
            if iso in (None, "") or factor is None or val is None:
                continue
            reserves_rows.append({
                "commodity": com, "country": _clean_name(r["Country"]),
                "entity": iso, "reserves_t": val * factor,
                "detail": str(r["Statistics_detail"]).strip(),
                "as_of_year": int(r["Year"]), "edition": "MCS2026",
            })
    else:
        print("[usgs] missing mcs2026_commodities.csv, skipping edition")

    if unmapped:
        print(f"[usgs] unmapped country names (skipped): {sorted(unmapped)}")

    if reserves_rows:
        out = TIDY / SOURCE
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(reserves_rows).to_parquet(out / "reserves.parquet", index=False)

    rows = [(sid, ent, yr, None, val) for (sid, ent, yr), val in sink.items()]
    if not rows:
        raise RuntimeError("usgs: parsed 0 rows — ScienceBase layout may have changed")

    _MINE_META = {
        "rare_earths": ("Rare earths", "REO-equivalent content",
                        "China holds ~70% of MINE production (2024: 270kt of 380kt world) — "
                        "refining/separation is more concentrated still (~85-90% China) and is "
                        "NOT in the MCS world tables; keep the mining-vs-refining distinction."),
        "lithium": ("Lithium", "lithium content",
                    "Australia + Chile dominate mining; most refining happens in China."),
        "cobalt": ("Cobalt", "cobalt content",
                   "Congo (Kinshasa) supplies ~70-75% of world mine production."),
        "graphite": ("Natural graphite", "gross weight",
                     "China ~75-80% of natural-graphite mining (battery anode feedstock)."),
        "nickel": ("Nickel", "nickel content",
                   "Indonesia's share roughly doubled 2020-2025 to ~60%."),
        "copper": ("Copper", "recoverable copper content",
                   "Chile/Peru/DRC lead mining; see usgs/refinery_prod.copper for the "
                   "refining stage, where China is ~45%."),
        "tungsten": ("Tungsten", "tungsten content",
                     "China ~80% of world mine production."),
        "platinum": ("Platinum", "platinum content",
                     "South Africa ~70% of world mine production."),
        "palladium": ("Palladium", "palladium content",
                      "Russia + South Africa together ~75-80% of mine production."),
    }
    _REF_META = {
        "copper": ("Copper (refined)", "refinery output",
                   "Refined copper production by country — China ~45% vs its ~8% mine share."),
        "gallium": ("Gallium (low-purity primary)", "primary production",
                    "A byproduct of alumina refining, no mines: China ~98% of world primary "
                    "production — the basis of its 2023 export controls."),
        "germanium": ("Germanium (refinery)", "primary + secondary refinery production",
                      "Sparse: USGS withholds most country figures (W/NA); China + world "
                      "totals only in some years. Byproduct of zinc refining and coal ash."),
    }
    series_list: list[Series] = []
    for com, (disp, content, extra) in _MINE_META.items():
        series_list.append(Series(
            series_id=f"usgs/mine_prod.{com}", source=SOURCE,
            name=f"{disp} — world mine production",
            unit=f"metric tons ({content}; normalized from t/kt/kg)",
            unit_type="physical", frequency="A",
            description=(
                f"USGS Mineral Commodity Summaries: {disp.lower()} MINE production per "
                f"country, 2020-2025 (five editions MCS2022-MCS2026 stitched; later "
                f"edition revises earlier estimates; latest year is an estimate). "
                f"Entity WLD = USGS world total (rounded); minor producers pooled in "
                f"'Other countries' are excluded. Concentration snapshot, not a long "
                f"history. {extra}"),
            license="Public domain (USGS)", url=MCS_URL,
        ))
    for com, (disp, content, extra) in _REF_META.items():
        series_list.append(Series(
            series_id=f"usgs/refinery_prod.{com}", source=SOURCE,
            name=f"{disp} — world refinery production",
            unit=f"metric tons ({content}; normalized from t/kt/kg)",
            unit_type="physical", frequency="A",
            description=(
                f"USGS Mineral Commodity Summaries: {disp.lower()} REFINERY-stage "
                f"production per country, 2020-2025 (MCS2022-MCS2026 stitched, later "
                f"editions revise earlier estimates). Entity WLD = USGS world total. "
                f"{extra}"),
            license="Public domain (USGS)", url=MCS_URL,
        ))

    return series_list, pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])
