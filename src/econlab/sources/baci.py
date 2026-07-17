"""CEPII BACI — bilateral goods trade, HS92, 1995 -> latest.

The ~2.5GB zip holds one product-level CSV per year (~10M rows each). At
ingest we aggregate to bilateral totals (exporter, importer, year, USD) into a
dedicated `trade` warehouse table — pair data doesn't fit the obs model — and
derive per-country obs series (total exports/imports). The raw zip stays for
future product-level analysis. Values are published in thousand USD.
License: free with citation (CEPII / Etalab).
"""

from __future__ import annotations

import io
import re
import zipfile

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..catalog import Series
from ..config import RAW, TIDY
from ..fetch import download

SOURCE = "baci"
TITLE = "CEPII BACI bilateral trade (HS92)"
ZIP_URL = "https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS92_V202601.zip"
ZIP_NAME = "BACI_HS92_V202601.zip"


def fetch(force: bool = False) -> None:
    download(SOURCE, ZIP_URL, ZIP_NAME, force=force)


def _country_map(z: zipfile.ZipFile) -> dict[int, str]:
    member = next(m for m in z.namelist() if "country_codes" in m.lower())
    with z.open(member) as f:
        cc = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"))
    code_col = next(c for c in cc.columns if "code" in c.lower() and "iso" not in c.lower())
    iso3_col = next(c for c in cc.columns if "iso" in c.lower() and "3" in c)
    out = {}
    for _, r in cc.iterrows():
        try:
            out[int(r[code_col])] = str(r[iso3_col]).strip().upper()
        except (ValueError, TypeError):
            continue
    return {k: v for k, v in out.items() if len(v) == 3 and v.isalpha()}


def parse() -> tuple[list[Series], pd.DataFrame]:
    zpath = RAW / SOURCE / ZIP_NAME
    tmp_dir = RAW / SOURCE / "_tmp"
    tmp_dir.mkdir(exist_ok=True)

    con = duckdb.connect()
    pieces = []
    with zipfile.ZipFile(zpath) as z:
        cmap = _country_map(z)
        year_members = sorted(
            m for m in z.namelist() if re.search(r"BACI_HS92_Y\d{4}", m) and m.endswith(".csv")
        )
        for member in year_members:
            year = int(re.search(r"Y(\d{4})", member).group(1))
            target = tmp_dir / "current.csv"
            with z.open(member) as src, open(target, "wb") as dst:
                while chunk := src.read(1 << 22):
                    dst.write(chunk)
            agg = con.execute(
                f"""
                SELECT CAST(t AS INT) AS year, CAST(i AS INT) AS exporter_code,
                       CAST(j AS INT) AS importer_code, sum(CAST(v AS DOUBLE)) * 1000 AS value_usd
                FROM read_csv('{target}', header=true)
                GROUP BY 1, 2, 3
                """
            ).df()
            target.unlink()
            pieces.append(agg)
            print(f"[baci] {year}: {len(agg):,} bilateral pairs")
    tmp_dir.rmdir()

    trade = pd.concat(pieces, ignore_index=True)
    trade["exporter"] = trade["exporter_code"].map(cmap)
    trade["importer"] = trade["importer_code"].map(cmap)
    trade = trade.dropna(subset=["exporter", "importer"])
    trade = trade[["year", "exporter", "importer", "value_usd"]]

    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(trade, preserve_index=False), out / "trade.parquet")

    exports = trade.groupby(["exporter", "year"], as_index=False)["value_usd"].sum()
    imports = trade.groupby(["importer", "year"], as_index=False)["value_usd"].sum()

    series_list = [
        Series(
            series_id="baci/exports_total",
            source=SOURCE,
            name="Total goods exports (BACI bilateral sum)",
            unit="current US$",
            unit_type="nominal_usd",
            frequency="A",
            description="Sum of bilateral goods-export flows over all partners (BACI HS92, FOB).",
            license="Free with citation (CEPII)",
            url="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
        ),
        Series(
            series_id="baci/imports_total",
            source=SOURCE,
            name="Total goods imports (BACI bilateral sum)",
            unit="current US$",
            unit_type="nominal_usd",
            frequency="A",
            description="Sum of bilateral goods-import flows over all partners (BACI HS92).",
            license="Free with citation (CEPII)",
            url="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
        ),
    ]
    ex = pd.DataFrame(
        {"series_id": "baci/exports_total", "entity": exports["exporter"],
         "year": exports["year"], "value": exports["value_usd"]}
    )
    im = pd.DataFrame(
        {"series_id": "baci/imports_total", "entity": imports["importer"],
         "year": imports["year"], "value": imports["value_usd"]}
    )
    obs = pd.concat([ex, im], ignore_index=True)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
