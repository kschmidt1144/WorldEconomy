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
- **Entity namespaces**: company entities are `$`-prefixed (`$AAPL`) — ticker
  `SUN` (Sunoco) once shadowed the former USSR. Instruments are bare slugs
  (`SPX`). `kind` = country|aggregate|historical|company|instrument|other;
  WDI aggregates (WLD, regions) are kind='aggregate' — exclude from country sums.
- **Bot-walled sources & their reroutes** (series ids stay provider-agnostic):
  IMF WEO bulk `.ashx` (Akamai) → DataMapper API (`imf/*`); Energy Institute
  direct CSV (403) → OWID GitHub mirror (`energy/*`); Stooq (JS wall) →
  yfinance (`markets/*`).
- **WID bulk codes are `<var><unit><age>`** (`sptincj992`), NOT the API's
  `sptinc992j` order. Shares are fractions, not percents.
- **EDGAR**: only frame-tagged facts (CY2023, CY2023Q1) are ingested; revenue
  tag choice (Revenues vs ASC-606 tag) is **per-frame** — Apple reports old
  years under one and new under the other; filer-error future FYs dropped.
- **Scale normalization**: IMF (billions), PWT (millions), UN WPP (thousands),
  BACI (thousand USD) are all normalized to base units at ingest — check
  `unit` text for provenance.
- **Shiller**: Yale mirror froze Sep 2023 — connector resolves the live file
  from shillerdata.com (protocol-relative `//img1.wsimg.com/...` link).
  Fractional months: `1871.1` = October, not January.
- **DuckDB `.arrow()` returns RecordBatchReader** (not Table) — use
  `.fetch_arrow_table()`.
- **FiscalData API**: endpoint is `v2/accounting/od/debt_outstanding` (no
  `_amt`); use `record_fiscal_year`; occasional transient RemoteDisconnected.
- WDI bulk zip ~292MB; main CSV renamed `WDIData.csv` → `WDICSV.csv` (both handled).
- JST `debtgdp` is a **fraction** (1.26 = 126%); JST R6 ends 2020.
- Bilateral trade (BACI) lives in warehouse table **`trade`**
  (year, exporter, importer, value_usd) — pair data doesn't fit obs.

## Status (2026-07-17)

Phase 0 ✅ + Phase 1 ✅ (minus FRED key) — **14 sources, 1,985 series, ~14.6M
obs, 6,478 companies, 857k bilateral trade pairs, year 1 CE → 2101** (UN
projections; IMF to 2031). 30 passing sanity tests. Sources: WDI, Maddison,
Shiller, JST, DFA, FiscalData, IMF DataMapper (WEO+GDD), PWT 11.0, UN WPP
2024, OWID-energy, yfinance markets, WID, EDGAR companyfacts, BACI HS92.
**FRED wired but needs Kevin's free API key** (env FRED_API_KEY or
.secrets/fred.key) — then `uv run econ refresh -s fred`.
Next: Phase 2 chapters (long arc → nations & macro → money & markets →
wealth & people → structural forces), then Phase 3 MCP apparatus. COFER
(reserve currencies) deferred to the dollar-dominance chapter.
