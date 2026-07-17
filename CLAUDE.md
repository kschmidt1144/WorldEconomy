# CLAUDE.md — WorldEconomy (World Economy Lab)

Data warehouse + analysis library for understanding the world economy from
**primary data** — the twin deliverables are a chaptered report (`report/`)
where every claim is computed in-repo, and an **MCP apparatus** (Phase 3) so
any Claude session can query the warehouse. Full plan/phasing:
`report/00-pipeline.md` (roadmap section).

## Commands (uv-managed, Python 3.12)

```bash
uv sync                          # install
uv run econ refresh              # fetch all sources -> tidy parquet -> rebuild warehouse
uv run econ refresh -s wdi       # one source (--force to re-download)
uv run econ coverage             # what's in the warehouse
uv run econ search "gdp per capita"
uv run econ get maddison/gdppc -e USA -e CHN --start 1900
uv run econ sql "SELECT ..."     # tables: obs, catalog, entities; view: series
uv run econ figures              # regenerate report figures
uv run pytest                    # sanity suite: benchmark values must reproduce
```

## Architecture

- `data/raw/<source>/` immutable downloads + `_manifest.json` (url, sha256) —
  **gitignored, fully reproducible** via `econ refresh`.
- `data/tidy/<source>/{obs,catalog}.parquet` → `data/warehouse.duckdb`
  (rebuilt artifact — delete freely).
- Obs schema: `(series_id, entity, year, date?, value)`. `year` always set
  (pandas datetime can't hold year 1 CE — that's why `year` exists); `date`
  only for sub-annual series. Series ids namespaced: `wdi/NY.GDP.MKTP.CD`.
- `src/econlab/sources/<name>.py` — connector contract: `SOURCE`, `TITLE`,
  `fetch(force)`, `parse() -> (list[Series], obs df | pyarrow Table)`.
- `catalog.unit_type` is load-bearing (nominal_usd/real_usd/ppp_usd/lcu/index/
  percent/ratio/count) — never mix unit types in one computation.

## ⚠️ Gotchas (each cost real debugging)

- **Maddison carries USSR/Czechoslovakia/Yugoslavia IN PARALLEL with successor
  states** — naive world sums double-count. Always aggregate via
  `analysis/maddison_world.py:successor_partition()`. Pre-1950 the panel
  misses colonial economies (bottom-up world sums are lower bounds).
- **Shiller**: Yale mirror froze Sep 2023 — connector resolves the live file
  from shillerdata.com (protocol-relative `//img1.wsimg.com/...` link).
- **Fractional months in Shiller dates**: `1871.1` = October, not January.
- **DuckDB `.arrow()` returns RecordBatchReader** (not Table) — use
  `.fetch_arrow_table()`.
- **FiscalData API**: endpoint is `v2/accounting/od/debt_outstanding` (no
  `_amt`); use `record_fiscal_year`; occasional transient RemoteDisconnected.
- WDI bulk zip ~292MB; main CSV renamed `WDIData.csv` → `WDICSV.csv` (both handled).
- JST `debtgdp` is a **fraction** (1.26 = 126%); JST R6 ends 2020.
- Entities: `kind` = country|aggregate|historical|other. WDI aggregates (WLD,
  regions, income groups) have kind='aggregate' — exclude from country sums.

## Status (2026-07-17)

Phase 0 ✅ — 6 sources (WDI, Maddison, Shiller, JST, DFA, FiscalData), 1,690
series / 9.2M obs / year 1→2026, 18 passing sanity tests, 4 figures + chapter 0.
Next: Phase 1 breadth (FRED — **needs free API key from Kevin**, IMF, EDGAR,
WID, PWT, UN WPP, BACI, Energy Institute, Stooq).
