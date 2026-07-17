# Chapter 0 — The pipeline works: first light

*World Economy Lab, Phase 0. Generated 2026-07-17. Every number below is computed
from primary data in this repo's warehouse — nothing is quoted from secondary
sources. Reproduce with: `uv run econ refresh && uv run pytest && uv run econ figures`.*

## What exists now

A reproducible data platform: raw downloads → tidy parquet → a DuckDB warehouse
(`data/warehouse.duckdb`) with one uniform observation table, a series catalog
(units, licenses, frequencies), and an entity concordance. **1,690 series,
~9.2M observations, spanning year 1 CE → July 2026.**

| Source | Series | Obs | Entities | Span | License |
|---|---|---|---|---|---|
| World Bank WDI (bulk) | 1,498 | 9,015,914 | 264 | 1960–2025 | CC BY-4.0 |
| JST Macrohistory R6 | 53 | 111,546 | 18 | 1870–2020 | research w/ citation |
| Maddison Project 2023 | 2 | 39,241 | 169 | 1–2022 | CC BY 4.0 |
| Fed DFA | 130 | 19,110 | US | 1989–2026 Q1 | public domain |
| Shiller ie_data | 6 | 11,077 | US | 1871–2026 M7 | research use |
| Treasury FiscalData | 1 | 237 | US | 1790–2025 | public domain |

18 sanity tests pin the warehouse to known benchmarks (US GDP 2019 ≈ $21.4T,
CAPE Dec-1999 = 44.2, the canonical JST crisis years, USSR≡Σ successor states…).

## Four first calculations

### 1. The hockey stick

![World GDP, year 1 to 2022](figures/00_world_gdp_long_run.png)

Our bottom-up sum (GDP pc × population over ~170 economies) gives **$8.5T of
world output in 1950 and $130.5T in 2022** (2011 PPP$) — a 15× expansion in 72
years. Against Maddison's own 1820 world aggregate ($1.18T), the world economy
is **~110× larger than in 1820**, after ~18 centuries in which output crept
from roughly $0.04T (12 covered economies, year 1) to benchmark-scale fractions
of a trillion. Growth is *the* anomaly of the modern era.

Two integrity notes, both discovered by computation and now enforced by tests:
MPD2023 carries the USSR/Czechoslovakia/Yugoslavia **in parallel with** their
successor states (1950 USSR pop = Σ 15 successors to 6 decimals) — naive sums
double-count; and pre-1950 the country panel misses most colonial economies, so
our bottom-up line starts in 1950 and Maddison's aggregate bridges 1820–1949.

### 2. The Great Divergence — and the catch-up

![The Great Divergence](figures/00_great_divergence.png)

China ≈ Britain in living standards in 1500. By 1950 the US–China gap was
**19.1×**; by 2022 it had collapsed to **3.0×**. The divergence took four
centuries; the (partial) reconvergence took four decades.

### 3. Inflation's regime changes

![US inflation](figures/00_us_inflation.png)

Pre-1914: violent oscillation, deflation as common as inflation. Wars produce
spikes (+24% in 1917, +20% in 1947). After WWII deflation essentially
disappears — the fiat/managed-money regime trades deflation risk for a
persistent positive drift. The 1970s twin peaks, the Great Moderation, the
2021–23 spike, and **4.2% as of July 2026** — inflation is back above target.

### 4. Public debt across regimes

![US public debt / GDP](figures/00_us_debt_gdp.png)

Two fully independent constructions — JST macrohistory vs. our Treasury-debt ÷
World-Bank-GDP splice — agree within ~2pp where they overlap. War peaks (119%
in 1946), the postwar melt to 31% (1981), and the modern climb to **121% of
GDP in 2024**, above the WWII peak. The 2020s are, fiscally, a war decade
without the war.

## Also in the warehouse today

- **CAPE = 41.4 (July 2026)** — equity valuations in the top ~2% of 155 years
  of history, exceeded only by 1999–2000 and 2021.
- **Top 1% of US households hold 31.6% of net worth; the bottom 50% hold 2.5%**
  (Fed DFA, 2026 Q1).

## Caveats & decisions log

- Shiller's Yale mirror froze in Sep 2023; we resolve the live file from
  shillerdata.com (through Jul 2026). CAPE is stored from source for
  cross-checks; from Phase 2 we compute it ourselves.
- JST R6 ends 2020 (check for R7 in Phase 1). WDI unit_types are heuristic
  (`unknown` allowed, transforms will warn). Debt concepts differ slightly
  across sources (JST federal vs Treasury gross) — plotted, not blended.
- Fiscal years ≠ calendar years for FiscalData (Sep 30 end; Jun 30 pre-1977).

## Roadmap

- **Phase 1 — breadth:** FRED (needs free API key), IMF WEO/GDD/COFER, SEC
  EDGAR fundamentals, WID inequality, PWT, UN WPP demography, BACI trade,
  Energy Institute, Stooq prices.
- **Phase 2 — chapters:** long arc → nations & macro → money & markets →
  wealth & people → structural forces. Computations + figures + prose.
- **Phase 3 — apparatus:** MCP server (`econ_search/get/compare/sql/chart`)
  registered user-level so any Claude session can query this warehouse;
  synthesis chapter; compiled report.
