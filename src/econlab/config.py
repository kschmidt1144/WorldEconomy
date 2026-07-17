"""Repo paths. Everything derives from ROOT so a clean clone just works."""

from __future__ import annotations

import os
from pathlib import Path

# src/econlab/config.py -> parents[2] == repo root (package is installed editable)
ROOT = Path(os.environ.get("ECONLAB_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
RAW = DATA / "raw"          # immutable downloads, one dir per source, + _manifest.json
TIDY = DATA / "tidy"        # per-source obs.parquet + catalog.parquet
WAREHOUSE = DATA / "warehouse.duckdb"
REPORT = ROOT / "report"
FIGURES = REPORT / "figures"

OBS_COLUMNS = ["series_id", "entity", "year", "date", "value"]
