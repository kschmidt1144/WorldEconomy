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
returned path), and `econ_notes` / `econ_note_add` (the user's margin notes from
the tablet reader — see `webreader/` below). Server: `src/econlab/mcp_server.py`
(thin tool wrappers over testable `*_impl` functions); entry `econ-mcp`. Compile
the report to one self-contained HTML with `uv run econ compile` →
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
  (tab-delimited). A currency test guards against silent staleness. The
  **by-country deep history** (2002–2021) lives in `ticarchive`, which fetches
  one pinned Wayback `mfh.txt` snapshot/yr — two format gotchas: **pre-2008 files
  put the year row ABOVE and months ON the `Country` line (later files reverse
  it)**, and **Wayback throttles rapid fetches** (it 403/refuses after ~15
  requests — cached snapshots persist, so just `refresh -s ticarchive` again to
  fill the rest; 2022–23 snapshots are pinned but may need a retry).
- **BoC–BoE sovereign defaults** (`defaults`): the 2024 vintage renames some
  countries in its final year rows (Gambia→The Gambia); normalize before the
  name→ISO3 map or a country's series splits. Never-defaulters (US/Canada/Japan/
  Nordics/Swiss/Dutch/Australia) are simply ABSENT — the panel starts 1960.
- **Census ASPP** (`aspp`): item RZ01 (`ITEM_VALUE`) is in **dollars** here (not
  the usual Census $thousands) — state sums reproduce the published ~$6.5T total.
- WDI bulk zip ~292MB; main CSV renamed `WDIData.csv` → `WDICSV.csv` (both handled).
- JST `debtgdp` is a **fraction** (1.26 = 126%); JST R6 ends 2020.
- Bilateral trade (BACI) lives in warehouse table **`trade`**
  (year, exporter, importer, value_usd) — pair data doesn't fit obs.
- **SEC (edgar, edgar13f) needs a fair-access User-Agent with a contact email**
  or every request 403s ("Request Rate Threshold Exceeded"); `edgar13f` sets one
  (env `ECONLAB_SEC_UA`). **BlackRock moved its 13F filer CIK 1364742 → 2012383**
  (2024) — CIKs can change, so `edgar13f` discovers each filer's latest 13F-HR
  live. 13F values are dollars since 2023-Q1 (thousands before). `edgar13f/*`
  series (big3_shares/value + per-manager, keyed by `$ticker`) join onto
  `edgar/shares_q` for ownership %; issuer→ticker is by normalized name (no free
  CUSIP map) with a despaced fallback (Exxon Mobil ↔ ExxonMobil).

## Status (2026-07-19e)

Phases 0–3 ✅ plus a large question-driven expansion. **~41 sources, ~15M obs,
year 1 CE → 2101; 166 passing tests; 13 chapters, 127 figures; report compiles
to one self-contained HTML** (`uv run econ compile`).

**Chapter order — the four-movement arc (reorg 2026-07-19e).** Figure files,
analysis modules (`analysis/chNN_*.py`), and test names all share the chapter
number, so any renumber renames all three together — the 2026-07-19e reorg used
a cycle-safe permutation script (`scratchpad/reorg_chapters.py`; footers +
Lab chapter-map + cross-refs fixed after). The arc:

- **I · Macro** — 00 the-lab · 01 long-arc · 02 nations · 03 money-markets ·
  04 structural-forces
- **II · Distribution (who has what)** — 05 debt-ledger · 06 wealth-people ·
  07 who-owns-the-land · 08 what-things-cost
- **III · Power (who controls)** — 09 balance-sheets-of-power · 10 chokepoints
- **IV · Close** — 11 dynasties · 12 synthesis (capstone: reads the report down
  the time axis *and* across the concentration spine, + live dashboard)

**Recent work:** depth pass on thin chapters (2/3/5, +cofer/pinksheet sources);
**08 what-things-cost** (cost of living — goods-vs-services, staples-vs-wages,
housing by state, inflation-inequality, wages-by-quartile vs care: median +10%/
top-decile +25% real 2000→24 but no quartile kept up with childcare +29%/college
+46%/hospital +89%; +`bls` source); **09 balance-sheets-of-power** Part I
evolution (central-bank diffusion 1→182, bank consolidation 30k→~4k, banks→funds
shift, new titans BlackRock $11.5T) / Part II power + who-decides; **10
chokepoints** — the concentration spine (F1 map · F2 dual-class · F3 capital
pools · F4 hidden hands + real 13F ownership · F5 elite network · F6 conferences
· F7 the FOMC: one meeting moves S&P 1.3×/2yr 1.5×/VIX 1.4×); **AI cross-check
panel** (`src/econlab/panel/`, `econ panel|crosscheck`, MCP tools) polls several
LLMs and scores agreement. Synthesis re-written 2026-07-19e.

Backlog: N-PX per-company voting records; computed board-interlock network from
Form 4; optional Kykli publish.

## `webreader/` — tablet reader + margin notes (Kykli PWA)

A Vue 3 + TS + Pinia + vite-plugin-pwa app to read the report and take notes on a
tablet, offline. `npm run sync` (auto before dev/build) copies `report/*.md` +
`report/figures/` into `webreader/public/report/` — **re-run after `econ compile`**.
Install with a repo-local cache: `npm install --cache "$PWD/.npmcache"` (avoids the
machine's global-npm EACCES). Base path `/worldeconomy/` for Kykli.

- **Storage is swappable** (`src/lib/storage.ts`): `StorageAdapter` interface; M1 ships
  `LocalStorageAdapter`. Notes = `{id,chapter,chapterTitle,anchor,anchorText,quote,body,
  color,createdAt,updatedAt}`.
- **Status: M1 + M2 + M3 done — only M4 (Kykli deploy) left.**
  - **M1** = reader + select→note→save, offline PWA, light/dark, scroll-spy, resume position.
  - **M3** (the bridge) = `notes_store.py` reads/writes Firestore named DB `worldeconomy`
    collection `notes` via firebase-admin + ADC (admin SDK bypasses rules); `econ notes
    [--chapter X] [--search Q]` / `econ note-add <chapter> <body>` CLI + `econ_notes` /
    `econ_note_add` MCP tools (graceful-skip if ADC/firebase-admin missing). DB created
    2026-07-21 (`gcloud firestore databases create --database=worldeconomy --location=nam5`).
  - **M2** = PWA writes notes to the same Firestore. `src/lib/firebase.ts` (shared Kykli web
    config, named DB `worldeconomy`, offline `persistentLocalCache`), `firebase/auth` Google
    popup (`stores/auth.ts`), `FirestoreAdapter` (notes → top-level `notes`; reading position
    stays device-local in localStorage). Reading is open; **notes require sign-in** (drawer
    shows a Google gate). Rules (`webreader/firestore.rules`, email-allowlist) deployed to the
    `worldeconomy` DB via the **firebaserules REST API + `x-goog-user-project` header** (firebase
    CLI not installed). Verified builds/loads/gate/clean-init; **real Google sign-in is a device
    test** (can't complete the popup headless).
  - **M4 (next)** = `npm run build` → copy `dist/` into `Kykli/worldeconomy-dist/` → nginx
    subpath `kykli.dev/worldeconomy` (ensure kykli.dev is in Firebase Auth authorized domains).
- **Gotcha:** report figures have no intrinsic CSS height, so `loading="lazy"` collapses
  them to 0px and they never load — they're eager-loaded (only the current chapter's ~28
  figures are in the DOM). Figures runtime-cached by the SW (not precached; ~21MB).