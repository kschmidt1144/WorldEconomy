"""BIS Debt Service Ratios — the cross-country comparator for debt burdens.

Interest + amortization relative to income, quarterly, ~17 economies, using
one common methodology (18-yr maturity assumption) — the only way to compare
household debt burdens across countries apples-to-apples. Sectors: households
(H), non-financial corporates (N), total private (P). Free (BIS terms).
"""

from __future__ import annotations

import glob
import io
import zipfile

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download

SOURCE = "bis"
TITLE = "BIS debt service ratios"
ZIP_URL = "https://data.bis.org/static/bulk/WS_DSR_csv_flat.zip"
ZIP_NAME = "WS_DSR_csv_flat.zip"

SECTORS = {
    "H": ("dsr_households", "Household debt service ratio"),
    "N": ("dsr_corporates", "Non-financial corporate debt service ratio"),
    "P": ("dsr_private", "Private non-financial sector debt service ratio"),
}


def fetch(force: bool = False) -> None:
    download(SOURCE, ZIP_URL, ZIP_NAME, force=force,
             headers={"User-Agent": "Mozilla/5.0"})


def _iso2_to_iso3() -> dict[str, str]:
    out = {}
    for cand in glob.glob(str(RAW / "wdi" / "**" / "WDICountry.csv"), recursive=True):
        wc = pd.read_csv(cand, dtype=str)
        two = next((c for c in wc.columns if "2-alpha" in c.lower()), None)
        if two:
            for _, r in wc.iterrows():
                if pd.notna(r[two]) and pd.notna(r["Country Code"]):
                    out[str(r[two]).strip()] = str(r["Country Code"]).strip()
        break
    out.setdefault("TW", "TWN")
    return out


def parse() -> tuple[list[Series], pd.DataFrame]:
    with zipfile.ZipFile(RAW / SOURCE / ZIP_NAME) as z:
        member = next(m for m in z.namelist() if m.lower().endswith(".csv"))
        with z.open(member) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8-sig"), dtype=str)

    # SDMX flat format: headers are "CODE:Human label", cells often "US:United States"
    def col(code: str) -> str | None:
        return next((c for c in df.columns if c.split(":")[0].strip().upper() == code), None)

    area, sector = col("BORROWERS_CTY") or col("REF_AREA"), col("DSR_BORROWERS")
    period, value = col("TIME_PERIOD"), col("OBS_VALUE")
    if not all([area, sector, period, value]):
        raise ValueError(f"bis: unexpected columns {list(df.columns)[:10]}")

    code = lambda s: s.astype(str).str.split(":").str[0].str.strip()  # noqa: E731
    iso = _iso2_to_iso3()
    df = df[code(df[sector]).isin(SECTORS)]
    df[sector] = code(df[sector])
    df["entity"] = code(df[area]).map(iso)
    df = df.dropna(subset=["entity", value])

    m = df[period].str.extract(r"(\d{4})-Q(\d)")
    df["year"] = pd.to_numeric(m[0], errors="coerce")
    df["q"] = pd.to_numeric(m[1], errors="coerce")
    df = df.dropna(subset=["year", "q"])
    from ..model import month_end

    df["date"] = [month_end(int(y), int(q) * 3) for y, q in zip(df["year"], df["q"])]
    df["value"] = pd.to_numeric(df[value], errors="coerce")
    df = df.dropna(subset=["value"])
    df["series_id"] = "bis/" + df[sector].map({k: v[0] for k, v in SECTORS.items()})

    series_list = [
        Series(
            series_id=f"bis/{slug}",
            source=SOURCE,
            name=name,
            unit="% of income (interest + amortization)",
            unit_type="percent",
            frequency="Q",
            description=(
                f"BIS {name.lower()}: debt service (interest + amortization) as % of "
                "sector income, common 18-yr-maturity methodology — cross-country comparable."
            ),
            license="BIS terms (free with attribution)",
            url="https://data.bis.org/topics/DSR",
        )
        for slug, name in SECTORS.values()
    ]
    obs = df[["series_id", "entity", "year", "date", "value"]].copy()
    obs["year"] = obs["year"].astype(int)
    return series_list, obs
