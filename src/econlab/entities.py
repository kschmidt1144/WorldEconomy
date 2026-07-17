"""Entity concordance: one row per entity code appearing anywhere in obs.

kind: country | aggregate | historical | other (instruments, percentile groups…)
Metadata (region, income group) comes from WDI's country file when present.
Historical states carry a successor pointer so long-run splices are explicit.
"""

from __future__ import annotations

import glob

import duckdb
import pandas as pd

from .config import RAW, TIDY

# Maddison/JST codes for states that no longer exist -> (name, successor ISO3)
HISTORICAL = {
    "SUN": ("Former USSR", "RUS"),
    "CSK": ("Czechoslovakia", "CZE"),
    "YUG": ("Former Yugoslavia", "SRB"),
    "DDR": ("East Germany", "DEU"),
    "OTTO": ("Ottoman Empire", "TUR"),
}

# WDI "country" codes that are actually aggregates keep Region empty in WDICountry.csv;
# WLD is the one we lean on constantly.
KNOWN_AGGREGATES = {"WLD": "World"}


def build_entities() -> pd.DataFrame:
    obs_files = glob.glob(str(TIDY / "*" / "obs.parquet"))
    if not obs_files:
        raise RuntimeError("no tidy obs yet; run source refresh first")
    con = duckdb.connect()
    seen = con.execute(
        f"SELECT DISTINCT entity FROM read_parquet({obs_files!r})"
    ).df()["entity"]

    # WDI metadata if available
    meta = {}
    wdi_country = None
    for cand in ("WDICountry.csv", "WDICountry.CSV"):
        matches = glob.glob(str(RAW / "wdi" / "**" / cand), recursive=True)
        if matches:
            wdi_country = matches[0]
            break
    if wdi_country:
        wc = pd.read_csv(wdi_country, dtype=str)
        code_col = "Country Code"
        name_col = "Short Name" if "Short Name" in wc.columns else "Table Name"
        for _, r in wc.iterrows():
            meta[r[code_col]] = {
                "name": r.get(name_col),
                "region": r.get("Region") if pd.notna(r.get("Region")) else None,
                "income_group": r.get("Income Group") if pd.notna(r.get("Income Group")) else None,
            }

    rows = []
    for code in sorted(seen.dropna().unique()):
        m = meta.get(code)
        if code in HISTORICAL:
            name, successor = HISTORICAL[code]
            rows.append((code, name, None, None, "historical", successor))
        elif m:
            # WDI aggregates (World, EU, income groups…) have no Region
            kind = "country" if m["region"] else "aggregate"
            rows.append((code, m["name"], m["region"], m["income_group"], kind, None))
        elif code in KNOWN_AGGREGATES:
            rows.append((code, KNOWN_AGGREGATES[code], None, None, "aggregate", None))
        elif len(code) == 3 and code.isalpha() and code.isupper():
            rows.append((code, code, None, None, "country", None))
        else:
            rows.append((code, code, None, None, "other", None))

    df = pd.DataFrame(
        rows, columns=["entity", "name", "region", "income_group", "kind", "successor"]
    )
    df.to_parquet(TIDY / "entities.parquet", index=False)
    return df
