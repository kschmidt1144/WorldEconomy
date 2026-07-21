"""Sovereign defaults — Bank of Canada–Bank of England database.

The report's Ch.5 default catalog was curated from Reinhart–Rogoff hand-counts.
This connector replaces it with a *computed* dataset: the BoC–BoE cross-country
database of government debt in default, an annual **stock** of defaulted debt
(USD millions) for 174 countries + a World aggregate, 1960–2023. Keyless, public
(BoC terms of use), refreshed each summer (bump the vintage).

We emit each country's defaulted-debt stock as `defaults/stock` (base USD) and
write a per-country summary side-table `sovereign_defaults` (episode count, first/
last default year, peak stock, income group). Because the panel starts in 1960 it
lists only post-1960 defaulters — Spain's famous serial defaults are pre-1960 and
absent, and the never-defaulters (US, Canada, Scandinavia, Switzerland, Australia,
Netherlands) simply never appear. That absence is the finding, not a gap.
"""

from __future__ import annotations

import glob

import pandas as pd

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "defaults"
TITLE = "Sovereign defaults (BoC–BoE database)"
VINTAGE = 2024
URL = f"https://www.bankofcanada.ca/valet/observations/group/DEBT_{VINTAGE}/csv"
FILENAME = f"boc_boe_debt_{VINTAGE}.csv"

# BoC names that don't match WDI Short/Table names (incl. same-country variants
# the 2024 vintage renamed in its final years, e.g. Gambia -> The Gambia in 2023-24)
_NAME_OVERRIDE = {
    "the gambia": "GMB", "gambia": "GMB",
    "ussr/russia": "RUS", "ussr/russian federation": "RUS",
    "turkey": "TUR", "egypt": "EGY", "iran": "IRN", "syria": "SYR", "yemen": "YEM",
    "vietnam": "VNM", "laos": "LAO", "venezuela": "VEN", "kyrgyzstan": "KGZ",
    "macedonia": "MKD", "micronesia": "FSM", "nauru": "NRU", "somalia": "SOM",
    "bahamas": "BHS", "bosnia & herzegovina": "BIH", "cook islands": "COK",
    "côte d’ivoire": "CIV", "côte d'ivoire": "CIV", "cote d’ivoire": "CIV", "cote d'ivoire": "CIV",
    "dem. rep. of congo (kinshasa)": "COD", "democratic republic of congo (kinshasa)": "COD",
    "rep. of congo (brazzaville)": "COG", "republic of congo (brazzaville)": "COG",
    "korea (north)": "PRK", "korea, democratic people's republic of (north)": "PRK",
    "st. kitts & nevis": "KNA", "trinidad & tobago": "TTO",
    "são tomé and príncipe": "STP", "sao tome and principe": "STP",
    "eswatini (swaziland)": "SWZ", "west bank & gaza": "PSE", "puerto rico": "PRI",
    "sint maarten": "SXM", "anguila": "AIA", "czechoslovakia": "CSK", "yugoslavia": "YUG",
    "netherlands antilles": "", "world": "WLD",
}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force, timeout=180)


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


def _read_panel() -> pd.DataFrame:
    path = RAW / SOURCE / FILENAME
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    hdr = next((i for i, ln in enumerate(lines) if ln.startswith('"k"') and "DEBT_COUNTRY" in ln), None)
    if hdr is None:
        raise ValueError("defaults: could not find the 'k,DEBT_COUNTRY' panel header")
    df = pd.read_csv(path, skiprows=hdr, dtype=str)
    df = df[["DEBT_COUNTRY", "DEBT_COUNTRY_GROUP", "DEBT_YEAR", f"DEBT_TOTAL_{VINTAGE}"]].copy()
    df.columns = ["country", "group", "year", "stock_musd"]
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["stock_musd"] = pd.to_numeric(df["stock_musd"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["country", "year"])
    df["year"] = df["year"].astype(int)
    return df


def _n_episodes(stock: pd.Series) -> int:
    """Number of contiguous nonzero default spells across the yearly stock."""
    nz = (stock.values > 0).astype(int)
    return int(((nz == 1) & (pd.Series(nz).shift(fill_value=0).values == 0)).sum())


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = _read_panel()
    name_map = _wdi_name_map()

    def to_iso3(name: str) -> str | None:
        key = name.strip().lower()
        if key in _NAME_OVERRIDE:
            return _NAME_OVERRIDE[key] or None
        return name_map.get(key)

    df["entity"] = df["country"].map(to_iso3)

    # canonical display name (collapse the year-boundary rename variants)
    _CANON = {"The Gambia": "Gambia", "USSR/Russian Federation": "USSR/Russia"}
    df["disp"] = df["country"].replace(_CANON)

    # --- obs: defaulted-debt stock per resolvable entity, base USD ---
    resolved = df[df["entity"].notna()].copy()
    obs = (resolved.groupby(["entity", "year"], as_index=False)["stock_musd"].sum())
    obs = obs[obs["stock_musd"] > 0].copy()
    obs["series_id"] = "defaults/stock"
    obs["value"] = obs["stock_musd"] * 1e6
    obs = obs[["series_id", "entity", "year", "value"]]

    # --- side-table: per-country default summary (all 174, by canonical name) ---
    rows = []
    for disp, g in df.groupby("disp"):
        if disp == "World":
            continue
        g = g.sort_values("year")
        nz = g[g["stock_musd"] > 0]
        if nz.empty:
            continue
        rows.append({
            "country": disp,
            "entity": g["entity"].dropna().iloc[0] if g["entity"].notna().any() else None,
            "group": g["group"].dropna().iloc[0] if g["group"].notna().any() else None,
            "n_episodes": _n_episodes(g.set_index("year")["stock_musd"]),
            "first_default_year": int(nz["year"].min()),
            "last_default_year": int(nz["year"].max()),
            "peak_stock_musd": float(nz["stock_musd"].max()),
            "peak_year": int(nz.loc[nz["stock_musd"].idxmax(), "year"]),
        })
    meta = pd.DataFrame(rows).sort_values("peak_stock_musd", ascending=False)
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    meta.to_parquet(out / "sovereign_defaults.parquet", index=False)

    series_list = [
        Series(
            series_id="defaults/stock",
            source=SOURCE,
            name="Government debt in default (stock)",
            unit="US$ (base units, from millions)",
            unit_type="nominal_usd",
            frequency="A",
            description=(
                "BoC–BoE database: outstanding stock of central-government debt in "
                "default per country and year, 1960–2023. Only post-1960 defaulters "
                "appear; never-defaulters (US, Canada, Scandinavia, Switzerland, "
                "Australia, Netherlands) are absent. Peak: Greece $312B (2012 PSI)."
            ),
            license="Bank of Canada terms of use (free, public)",
            url="https://www.bankofcanada.ca/rates/indicators/sovereign-default-database/",
        )
    ]
    return series_list, obs
