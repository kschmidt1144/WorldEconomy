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

## The apparatus (MCP)

Registered **user-level** as `econlab` (`claude mcp list` → ✔), so any Claude
session can query the warehouse: `econ_coverage` (orient first),
`econ_search`, `econ_get`, `econ_compare`, `econ_sql` (read-only DuckDB:
obs/catalog/entities/trade + view series), `econ_chart` (PNG → Read the
returned path). Server: `src/econlab/mcp_server.py` (thin tool wrappers over
testable `*_impl` functions); entry `econ-mcp`. Compile the report to one
self-contained HTML with `uv run econ compile` →
`report/world-economy-report.html`.

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
- **TIC foreign holders**: the classic `Publish/mfh.txt` (and its Documents/
  mirror) FROZE in Mar-2023 — the live monthly table is `slt_table5.txt`
  (tab-delimited). A currency test guards against silent staleness.
- WDI bulk zip ~292MB; main CSV renamed `WDIData.csv` → `WDICSV.csv` (both handled).
- JST `debtgdp` is a **fraction** (1.26 = 126%); JST R6 ends 2020.
- Bilateral trade (BACI) lives in warehouse table **`trade`**
  (year, exporter, importer, value_usd) — pair data doesn't fit obs.

## Status (2026-07-17)

Phases 0 ✅ 1 ✅ 2 ✅ — **15 sources (incl. FRED via `.env`), ~2,000 series,
~14.7M obs, year 1 CE → 2101; 55 passing tests; the full report written**:
chapters 0–6 in `report/` (pipeline → long arc → nations → money & markets →
wealth & people → structural forces → synthesis with live dashboard), 25
figures, every claim computed in-repo and pinned by a test.
Headline computed findings: convergence began ~2000; West's share peaked
1913; 2000s crisis breadth (72%) beat the 1930s; CAPE 41.4 = 99th pctile;
China #1 supplier to 96 countries; world pop peaks 10.29B in 2084.
**Phase 3 ✅** — MCP server registered user-level (✔ connected), 6 tools,
10-question acceptance passed (incl. cross-source: Apple revenue > Portugal
GDP; MEX overtook CHN as top US supplier), report compiled to
`report/world-economy-report.html` (4.5MB self-contained). 57 tests.
Backlog: COFER (reserve currencies), Forbes billionaires snapshot, optional
Kykli publish of the compiled report.
