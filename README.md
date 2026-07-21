# World Economy Lab

> Understand how the world economy works — and how it got this way — by
> computing everything yourself from primary data.

A personal economics education program disguised as a data platform. Fourteen
canonical primary sources — World Bank, IMF, SEC, UN, Maddison, the World
Inequality Database, central-bank and treasury records — feed a local
warehouse of **~15 million observations spanning year 1 CE to 2101** (UN and
IMF projections included). On top of it: a chaptered report in which **every
claim is recomputed from raw data**, and a query apparatus that answers
questions about the world economy with live calculations instead of
citations.

## The premise

Most economic understanding is secondhand — summaries of summaries of
somebody's regression. The rule here is different: **no claim enters the
report unless it is computed in this repo from primary data.** Reading that
the top-1% income share follows a U-curve is trivia. Reproducing the U-curve
from WID microdata — and watching your own aggregation land on the published
result — is understanding. The project is the course; writing it is taking it.

## What it is — three things

1. **A warehouse of the measurable world.** One uniform observation table
   (1,985 series, 14 sources, countries + companies + markets + people),
   a strict units catalog (nominal vs real vs PPP is enforced, not hoped),
   an entity concordance that survives collapsed empires and ticker
   collisions, and a bilateral trade table of 857k flows. Raw downloads are
   manifest-tracked; `econ refresh` rebuilds everything from source.

2. **A course you write by taking it.** Thirteen chapters in four movements:
   **macro** (the lab → the long run of growth → nations & macro → money &
   markets → structural forces) → **distribution** (the debt ledger → wealth
   & people → who owns the land → what things cost) → **power** (balance
   sheets of power → the chokepoints) → **close** (dynasties across centuries
   → synthesis: *how it got this way*, read down the time axis and across the
   concentration spine, closing with a live-computed state of the world).
   Each chapter is computations + figures + prose, and 150 benchmark tests
   pin the warehouse to reality (CAPE Dec-1999 = 44.2, Apple FY2023 =
   $383B, USSR ≡ Σ successor states…).

3. **An apparatus for asking questions.** The `econ` CLI
   (`search / get / sql / compare / figures / compile`) and a user-level MCP
   server, so any Claude session becomes a natural-language interface to the
   warehouse — *"how does US debt/GDP today compare with the 1946 peak?"* →
   computed answer, with the query shown.

4. **A cross-checking panel.** `econ panel "<question>"` polls several AI
   models (Claude, Gemini, GPT, Grok, Llama, DeepSeek, Qwen, Mistral —
   whichever have keys) and scores how much they *agree* — a numeric-consensus
   score when the answers are numbers, else text similarity; `econ crosscheck`
   tallies agree/disagree/uncertain on a claim. Extends "verify everything"
   from data to models: divergence flags a contested finding. Free keys get you
   real breadth (see `.env.example`); also an MCP tool (`econ_panel`).

## Education by data-wrangling

The gotchas ledger in `CLAUDE.md` is part of the curriculum, not an
appendix. The raw data itself teaches: Maddison carries the USSR *in
parallel* with its fifteen successor states (naive world sums double-count
an empire); the ticker `SUN` is Sunoco, not the Soviet Union; WID publishes
fractions where the API publishes shares; a company can report revenue under
two different XBRL tags across eras. Learning to catch these **is** economic
literacy — it's what separates computing an answer from quoting one.

## Personal by design

Single-user, local-first, **free data sources only**. Everything is
reproducible from a clean clone: `uv sync && uv run econ refresh` rebuilds
the raw layer, warehouse, and every figure. No keys required except an
optional free FRED key for the US financial-series extension.

## A public face on Kykli (planned)

The warehouse and apparatus stay local. The **report** is the publishable
surface: chapters render to static HTML and can ship at `kykli.dev` alongside
the other apps — a public, read-only artifact of the education, regenerated
whenever the data refreshes.

## Quick start

```bash
uv sync
uv run econ refresh          # ~6GB of primary data -> warehouse
uv run pytest                # 119 benchmark tests must pass
uv run econ figures          # regenerate report figures
uv run econ search "debt"    # explore the catalog
```

Start with [`report/00-the-lab.md`](report/00-the-lab.md) — the methods
chapter: the machine, its rules, the live inventory, and the chapter map.
`uv run econ compile` renders the whole report to one self-contained HTML
file with navigation, dashboard, and year-slider maps.

## Status

- **Phase 0 ✅** — platform + first light (6 sources, 4 figures, chapter 0)
- **Phase 1 ✅** — full breadth: 15 sources incl. FRED, ~14.7M obs,
  companies + trade + demography + energy + inequality
- **Phase 2 ✅** — the report: chapters 0–6, with a live-computed state of
  the world closing the synthesis
- **Phase 3 ✅** — the `econlab` MCP apparatus (any Claude session queries
  the warehouse) + compiled single-file HTML report
- **Question-driven expansion ✅** — the debt ledger, balance sheets of
  power, who owns the land (county-level values, year-slider maps), and
  dynasties (Rothschild/Fugger/Medici ledgers, deep-time survivors, the
  crowns of Europe) — now 29 sources, ~15.0M obs, 74 figures, 119 tests
- **2026-07-19** — editorial reorg into a deliberate arc (evidence →
  synthesis last), then a Wave 1–3 depth pass: the thinnest chapters
  rebuilt question-driven, +2 sources (COFER reserve currencies, World
  Bank commodity prices), +13 figures, +14 tests
