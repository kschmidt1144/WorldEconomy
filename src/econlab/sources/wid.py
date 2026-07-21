"""World Inequality Database — income & wealth distribution, some countries 1800s->.

From the ~1GB bulk zip we ingest the headline distributional variables
(pre-tax income shares, net personal wealth shares) for deciles + key groups,
plus average national income per adult. WID uses ISO2 codes -> mapped to ISO3
via the WDI country file; 'WO' (world) -> WLD; subnational codes skipped.
License: CC BY 4.0.
"""

from __future__ import annotations

import glob
import io
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "wid"
TITLE = "World Inequality Database"
ZIP_URL = "https://wid.world/bulk_download/wid_all_data.zip"
ZIP_NAME = "wid_all_data.zip"

# bulk-file codes are <var><unit><age> (e.g. sptinc + j + 992), unlike the
# API's <var><age><unit> convention — this cost a failed first parse
VARIABLES = {
    "sptincj992": ("Pre-tax national income share (equal-split adults)", "share of total (fraction)", "ratio"),
    "sdiincj992": ("Post-tax disposable income share (equal-split adults)", "share of total (fraction)", "ratio"),
    "shwealj992": ("Net personal wealth share (equal-split adults)", "share of total (fraction)", "ratio"),
    "anninci992": ("Average national income per adult", "constant local currency", "lcu"),
}

PERCENTILES = {
    "p0p10", "p10p20", "p20p30", "p30p40", "p40p50", "p50p60", "p60p70",
    "p70p80", "p80p90", "p90p100",
    "p0p50", "p50p90", "p99p100", "p99.9p100", "p0p100",
}


def fetch(force: bool = False) -> None:
    download(SOURCE, ZIP_URL, ZIP_NAME, force=force)


def _iso2_to_iso3() -> dict[str, str]:
    out = {"WO": "WLD"}
    for cand in glob.glob(str(RAW / "wdi" / "**" / "WDICountry.csv"), recursive=True):
        wc = pd.read_csv(cand, dtype=str)
        two = next((c for c in wc.columns if "2-alpha" in c.lower()), None)
        if two:
            for _, r in wc.iterrows():
                if pd.notna(r[two]) and pd.notna(r["Country Code"]):
                    out[str(r[two]).strip()] = str(r["Country Code"]).strip()
        break
    return out


def _pslug(p: str) -> str:
    return p.replace(".", "_")


def parse() -> tuple[list[Series], pd.DataFrame]:
    iso_map = _iso2_to_iso3()
    frames = []
    with zipfile.ZipFile(RAW / SOURCE / ZIP_NAME) as z:
        members = [
            m for m in z.namelist()
            if m.startswith("WID_data_") and m.endswith(".csv") and "-" not in m
        ]
        for i, member in enumerate(members):
            if i % 60 == 0:
                print(f"[wid] {i}/{len(members)} countries…")
            cc = member[len("WID_data_"):-len(".csv")]
            entity = iso_map.get(cc)
            if entity is None:
                continue
            with z.open(member) as f:
                df = pd.read_csv(
                    io.TextIOWrapper(f, encoding="utf-8"), sep=";",
                    usecols=["variable", "percentile", "year", "value"],
                    dtype={"variable": str, "percentile": str},
                )
            df = df[df["variable"].isin(VARIABLES) & df["percentile"].isin(PERCENTILES)]
            if df.empty:
                continue
            df = df.dropna(subset=["value"])
            df["entity"] = entity
            frames.append(df)

    if not frames:
        raise RuntimeError("wid: nothing parsed — zip layout changed?")
    long = pd.concat(frames, ignore_index=True)
    long["series_id"] = "wid/" + long["variable"] + "." + long["percentile"].map(_pslug)

    series_list = []
    for (var, pct), _ in long.groupby(["variable", "percentile"]):
        name, unit, ut = VARIABLES[var]
        series_list.append(
            Series(
                series_id=f"wid/{var}.{_pslug(pct)}",
                source=SOURCE,
                name=f"{name}, {pct}",
                unit=unit,
                unit_type=ut,
                frequency="A",
                description=(
                    f"WID variable {var} for percentile group {pct}. Shares are fractions "
                    f"of the national total; equal-split adults (j) / individuals (i)."
                ),
                license="CC BY 4.0",
                url="https://wid.world/",
            )
        )

    obs = long[["series_id", "entity", "year", "value"]].copy()
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
