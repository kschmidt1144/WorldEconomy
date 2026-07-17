"""Refresh orchestration: fetch -> parse -> tidy parquet -> entities -> warehouse."""

from __future__ import annotations

import time
import traceback

from .entities import build_entities
from .model import build_warehouse, write_tidy
from .sources import SOURCE_NAMES, get_source


def refresh(
    sources: list[str] | None = None,
    *,
    force: bool = False,
    build: bool = True,
) -> dict[str, tuple[int, int] | str]:
    """Refresh given sources (default all). Returns per-source (n_series, n_obs) or error text."""
    names = sources or SOURCE_NAMES
    results: dict[str, tuple[int, int] | str] = {}
    for name in names:
        mod = get_source(name)
        t0 = time.time()
        try:
            mod.fetch(force=force)
            result = mod.parse()
            if len(result) == 3:  # optional third element: entity metadata frame
                series_list, obs, ents = result
            else:
                series_list, obs = result
                ents = None
            n_series, n_obs = write_tidy(name, series_list, obs, entities=ents)
            results[name] = (n_series, n_obs)
            print(f"[{name}] ok: {n_series} series, {n_obs:,} obs ({time.time() - t0:.1f}s)")
        except Exception as e:
            results[name] = f"ERROR: {e}"
            print(f"[{name}] FAILED after {time.time() - t0:.1f}s: {e}")
            traceback.print_exc()
    if build:
        build_entities()
        path = build_warehouse()
        print(f"warehouse rebuilt: {path}")
    return results
