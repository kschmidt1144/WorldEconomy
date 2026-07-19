# CLAUDE.md — WorldEconomy (World Economy Lab)

Data warehouse + analysis library for understanding the world economy from
**primary data** — the twin deliverables are a chaptered report (`report/`)
where every claim is computed in-repo, and an **MCP apparatus** (Phase 3) so
any Claude session can query the warehouse. Methods + live inventory + chapter map: `report/00-the-lab.md`.

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

**AI cross-checking panel** (`src/econlab/panel/`): poll several LLMs with the
same question and score their agreement — extends the "verify everything" ethos
from data to models (model *divergence* flags a contested finding). Verbs:
`econ panel "<q>"` (numeric-consensus score if answers are numbers, else text
similarity), `econ crosscheck "<claim>"` (agree/disagree/uncertain tally),
`econ panel-models` (what's configured); MCP tools `econ_panel` / `econ_crosscheck`.
Providers via REST (no SDKs), keys from `.env` graceful-skip like FRED — see
`.env.example`. Free routes: `GITHUB_TOKEN` (GPT), `GROQ_API_KEY` (Llama/DeepSeek/
Qwen), `GOOGLE_API_KEY` (Gemini free tier), `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`;
paid: `ANTHROPIC_API_KEY`, `XAI_API_KEY`. Models overridable via `PANEL_<NAME>_MODEL`.
Runs logged to `data/panel/runs.jsonl` (gitignored).

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

## Status (2026-07-19d)

Phases 0–3 ✅ plus question-driven chapters and a Wave 1–3 depth pass. **28 sources, 2,925 series, ~14.9M obs, year 1 CE → 2101; 109 passing tests;
11 chapters, 63 figures; report compiles to one self-contained HTML.**

**Depth pass (2026-07-19):** the thinnest chapters (2, 3, 5) rebuilt question-driven, and 6/4/1/8 deepened. New sources: **cofer** (IMF reserve currencies via SDMX 2.1) and **pinksheet** (World Bank commodity prices). New marquee figures: wealth-composition engine, billionaire anatomy, extreme-poverty collapse (Ch5); crash catalog, 3-century rates, yield-curve alarm (Ch3); convergence ladder, global imbalances, reserve currencies (Ch2); bank/finance concentration (Ch6); sovereign-default ledger (Ch4); growth-takeoff diffusion (Ch1); commodity supercycles (Ch8).

**Chapter order (post-reorg 2026-07-19)** — 00 the-lab (methods+inventory) ·
01 long-arc · 02 nations · 03 money-markets · 04 debt-ledger · 05
wealth-people · 06 balance-sheets-of-power · 07 who-owns-the-land · 08
structural-forces · **09 what-things-cost** · 10 dynasties · 11 synthesis
(capstone, live dashboard). **2026-07-19c: inserted Ch09 cost-of-living**
(BLS/FRED CPI item detail + new `bls` source; the goods-vs-services price
divergence, staples-vs-wages, housing by state, inflation-inequality by
income; **F2 wages-by-quartile** — CPS usual-weekly-earnings percentiles,
real wage by quartile vs real care prices: median +10%/top-decile +25% real
2000→24 but NO quartile kept up with childcare +29%/college +46%/hospital
+89%) — dynasties/synthesis shifted 09/10→10/11 (cycle-free descending).
Figure files, analysis modules (`analysis/chNN_*.py`), and test names all
share the chapter number — if you renumber chapters, rename all three
together (the 2026-07-19 reorg did exactly this; see that commit for the
cycle-safe recipe).

Headline computed findings: convergence began ~2000; West's share peaked
1913; CAPE 41.4 = 99th pctile; China #1 supplier to 96 countries; world pop
peaks 10.29B in 2084; US households pay ~$600B/yr interest, bottom-40% at
~2× the effective rate of the top decile; foreign holders own $9.1T of
Treasuries; Rothschild peak ≈ 0.27% of world GDP (1882) vs Musk ~2.4× that
today; ten of twelve European crowns destroyed 1795–1946, five reign on.
Backlog: COFER reserve currencies, 13F institutional stakes, optional Kykli
publish.


**Ch6 expanded 2026-07-19d** (Kevin: evolution of financial institutions — banks, umbrella/holding cos, hedge funds, brokerages — 'from the beginning'). Restructured into **Part I evolution / Part II power**. New FRED series (USNUM bank count 1984-2020, QBPBSNUMINST, BKFTTLA641N failures, Flow-of-Funds asset levels 1945→) + curated tables in ch06_power.py (BANK_COUNT_ANCHORS pre-1984, CB_COUNT/CB_FOUNDINGS central-bank diffusion, NEW_TITANS/HEDGE_FUND_AUM, FINANCE_MILESTONES Glass-Steagall→GLB→2008). 4 new figures: central-bank diffusion (1→182), the great bank consolidation (30k unit banks 1921 → ~4.3k, + S&L/GFC failure waves), the great shift banks→funds (mutual funds 1%→77% of GDP, now rival banks), the new titans (BlackRock $11.5T; HF $39bn→$4.5tn). 3 new tests. Fixed stale Ch6 footer (was 'Chapter 4' → Ch7).