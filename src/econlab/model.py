"""Warehouse build + tidy-layer writer.

Tidy layer: data/tidy/<source>/{obs,catalog}.parquet with a fixed obs schema:
    series_id VARCHAR, entity VARCHAR, year INT32, date DATE (nullable), value DOUBLE

`year` is always populated (annual data lives here; pandas datetime can't hold
year 1 CE). `date` is populated for sub-annual series (all post-1677, so safe).

Warehouse: data/warehouse.duckdb rebuilt from the tidy layer — never the source
of truth; delete it freely.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .catalog import Series, catalog_df
from .config import OBS_COLUMNS, TIDY, WAREHOUSE

OBS_SCHEMA = pa.schema(
    [
        ("series_id", pa.string()),
        ("entity", pa.string()),
        ("year", pa.int32()),
        ("date", pa.date32()),
        ("value", pa.float64()),
    ]
)


def write_tidy(
    source: str,
    series_list: list[Series],
    obs: pd.DataFrame | pa.Table,
    entities: pd.DataFrame | None = None,
) -> tuple[int, int]:
    """Validate + write one source's tidy parquet pair. Returns (n_series, n_obs).

    Accepts a pandas DataFrame (typical) or a pyarrow Table (bulk sources like
    WDI where 10M+ rows shouldn't round-trip through pandas).

    `entities` (optional): source-provided entity metadata (entity, name, kind,
    …) — companies, market instruments — merged with priority by build_entities.
    """
    cat = catalog_df(series_list)

    if entities is not None:
        out = TIDY / source
        out.mkdir(parents=True, exist_ok=True)
        cols = ["entity", "name", "kind"]
        missing = [c for c in cols if c not in entities.columns]
        if missing:
            raise ValueError(f"{source}: entities frame missing {missing}")
        entities.drop_duplicates("entity").to_parquet(out / "entities.parquet", index=False)

    if isinstance(obs, pa.RecordBatchReader):
        obs = obs.read_all()
    if isinstance(obs, pa.Table):
        return _write_tidy_arrow(source, cat, obs)

    obs = obs.copy()
    if "date" not in obs.columns:
        obs["date"] = None
    missing = [c for c in OBS_COLUMNS if c not in obs.columns]
    if missing:
        raise ValueError(f"{source}: obs missing columns {missing}")
    obs = obs[OBS_COLUMNS]

    # every obs row must reference a cataloged series
    unknown = set(obs["series_id"].unique()) - set(cat["series_id"])
    if unknown:
        raise ValueError(f"{source}: obs references uncataloged series {sorted(unknown)[:5]}")

    obs = obs.dropna(subset=["value", "entity", "year"])
    obs["year"] = obs["year"].astype("int32")
    obs["value"] = obs["value"].astype("float64")

    # normalize date column to python date objects / None for arrow date32
    if pd.api.types.is_datetime64_any_dtype(obs["date"]):
        obs["date"] = obs["date"].dt.date
    obs["date"] = obs["date"].where(pd.notna(obs["date"]), None)

    out = TIDY / source
    out.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(obs, schema=OBS_SCHEMA, preserve_index=False)
    pq.write_table(table, out / "obs.parquet")
    cat.to_parquet(out / "catalog.parquet", index=False)
    return len(cat), len(obs)


def _write_tidy_arrow(source: str, cat: pd.DataFrame, table: pa.Table) -> tuple[int, int]:
    if "date" not in table.column_names:
        table = table.append_column("date", pa.nulls(len(table), pa.date32()))
    missing = [c for c in OBS_COLUMNS if c not in table.column_names]
    if missing:
        raise ValueError(f"{source}: obs missing columns {missing}")
    table = table.select(OBS_COLUMNS).cast(OBS_SCHEMA)

    keep = pc.and_(
        pc.and_(pc.is_valid(table["value"]), pc.is_valid(table["entity"])),
        pc.is_valid(table["year"]),
    )
    table = table.filter(keep)

    unknown = set(pc.unique(table["series_id"]).to_pylist()) - set(cat["series_id"])
    if unknown:
        raise ValueError(f"{source}: obs references uncataloged series {sorted(unknown)[:5]}")

    out = TIDY / source
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out / "obs.parquet")
    cat.to_parquet(out / "catalog.parquet", index=False)
    return len(cat), len(table)


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(WAREHOUSE), read_only=read_only)


def build_warehouse() -> Path:
    """Rebuild warehouse.duckdb from the tidy layer."""
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    obs_glob = str(TIDY / "*" / "obs.parquet")
    cat_glob = str(TIDY / "*" / "catalog.parquet")

    con.execute(f"CREATE OR REPLACE TABLE obs AS SELECT * FROM read_parquet('{obs_glob}')")
    con.execute(f"CREATE OR REPLACE TABLE catalog AS SELECT * FROM read_parquet('{cat_glob}')")

    entities_pq = TIDY / "entities.parquet"
    if entities_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE entities AS SELECT * FROM read_parquet('{entities_pq}')"
        )

    # bilateral trade lives in its own table — pair data doesn't fit obs
    trade_pq = TIDY / "baci" / "trade.parquet"
    if trade_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE trade AS SELECT * FROM read_parquet('{trade_pq}')"
        )

    # person-level billionaires snapshot (rank, name, worth_usd, country, source)
    people_pq = TIDY / "billionaires" / "people.parquet"
    if people_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE billionaires AS SELECT * FROM read_parquet('{people_pq}')"
        )

    # ten dynasties: peak-scale notes (rank, family, era, basis, pct_home_gdp…)
    peaks_pq = TIDY / "dynasties" / "peaks.parquet"
    if peaks_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE dynasty_peaks AS SELECT * FROM read_parquet('{peaks_pq}')"
        )

    # deep-time survivors (documented continuity spans across/around Rome's fall)
    surv_pq = TIDY / "dynasties" / "survivors.parquet"
    if surv_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE deep_survivors AS SELECT * FROM read_parquet('{surv_pq}')"
        )

    # royal lines of Europe (realm, house, start, end, fate)
    royal_pq = TIDY / "dynasties" / "royal_lines.parquet"
    if royal_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE royal_lines AS SELECT * FROM read_parquet('{royal_pq}')"
        )

    # Land Report 100 (rank, name, acres, edition)
    lo_pq = TIDY / "usland" / "landowners.parquet"
    if lo_pq.exists():
        con.execute(
            f"CREATE OR REPLACE TABLE landowners AS SELECT * FROM read_parquet('{lo_pq}')"
        )

    # integrity: no orphan series
    orphans = con.execute(
        "SELECT count(DISTINCT o.series_id) FROM obs o LEFT JOIN catalog c USING (series_id) "
        "WHERE c.series_id IS NULL"
    ).fetchone()[0]
    if orphans:
        raise RuntimeError(f"warehouse integrity: {orphans} obs series missing from catalog")

    con.execute(
        """
        CREATE OR REPLACE VIEW series AS
        SELECT o.series_id, o.entity, o.year, o.date, o.value,
               c.source, c.name, c.unit, c.unit_type, c.frequency, c.per_capita
        FROM obs o JOIN catalog c USING (series_id)
        """
    )
    con.close()
    return WAREHOUSE


def month_end(year: int, month: int) -> _dt.date:
    """Last day of month — canonical date for monthly observations."""
    if month == 12:
        return _dt.date(year, 12, 31)
    return _dt.date(year, month + 1, 1) - _dt.timedelta(days=1)
