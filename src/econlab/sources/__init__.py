"""Source connector registry.

Contract per module: SOURCE (str), TITLE (str),
fetch(force: bool = False) -> None, parse() -> (list[Series], obs DataFrame).
obs columns: series_id, entity, year, [date], value.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

SOURCE_NAMES = [
    # light, keyless
    "maddison",
    "shiller",
    "jst",
    "dfa",
    "fiscaldata",
    "imf",
    "pwt",
    "unwpp",
    "energy",
    "markets",
    "billionaires",
    "tic",
    "bis",
    "census",
    # key-gated
    "fred",
    # heavy bulk
    "wdi",
    "wid",
    "edgar",
    "baci",
]


def get_source(name: str) -> ModuleType:
    if name not in SOURCE_NAMES:
        raise KeyError(f"unknown source {name!r}; known: {SOURCE_NAMES}")
    return import_module(f"econlab.sources.{name}")


def all_sources() -> dict[str, ModuleType]:
    return {n: get_source(n) for n in SOURCE_NAMES}
