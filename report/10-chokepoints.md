# Chapter 10 — The Chokepoints: where a few control the many

*World Economy Lab. Generated 2026-07-19; module `econlab/analysis/ch10_chokepoints.py`.
Chapter 6 found that three index managers vote most of the S&P 500; this
chapter asks whether that pattern — a handful of hands on a vast lever — is
special to finance. It is not. It is the default structure of the modern
economy.*

**A note on method.** Unlike the rest of this report, most numbers here are
**curated** market-share figures, not computed from primary data — concentration
ratios live in industry reports, not open datasets. So this chapter does
something new: it **cross-checks each headline figure through the AI panel**
(Chapter 0's `econ panel` apparatus, polling three free models — Llama-3.3,
Qwen3, and GPT-OSS — independently). Where the panel's consensus corroborates
the curated number it is marked ✓; where the models diverge, that is flagged
(⚠) as an honest signal that the figure is contested or definition-sensitive.
Verify everything — including with a jury of machines.

## F1 — The map: one, two, or three entities, over and over

![The chokepoint map](figures/10_chokepoint_map.png)

Lay the economy's critical bottlenecks side by side and the same number keeps
appearing — **1, 2, 3, at most 4**:

| Chokepoint | Controllers | Share | AI panel |
|---|---|---|---|
| EUV lithography machines | **1** — ASML | **100%** | ✓ 100/100 |
| Proxy-vote advice | 2 — ISS + Glass Lewis | 95% | ✓ 98/100 |
| Credit ratings | 3 — S&P, Moody's, Fitch | 95% | ✓ 100/100 |
| Cross-border bank messaging | 1 — SWIFT | ~90% | — |
| Web search | 1 — Google | ~90% | ✓ 94/100 |
| AI accelerators | 1 — Nvidia | ~90% | ✓ 97/100 |
| Leading-edge chips (<7nm) | 1 — TSMC | ~90% | ⚠ 72/100 |
| Index-fund voting (S&P 500) | 3 — the Big Three | 88% | — |
| Rare-earth refining | 1 — China | ~87% | — |
| Global grain trade | 4 — the "ABCD" | ~75% | — |
| Desktop operating systems | 1 — Windows | ~72% | — |
| Commercial seeds & agrochem | 4 — Bayer/Corteva/Syngenta/BASF | ~60% | ✓ 100/100 |

The purest case is **ASML**: *one company, in one country (the Netherlands),*
makes every extreme-ultraviolet lithography machine on Earth — and without
those machines, no one makes an advanced chip. The AI panel agreed 100/100.
The only figure the panel *contested* was **TSMC's ~90%**: the models split
between 50% and 90% (consensus just 72/100) — correctly, because it depends on
definition. TSMC makes ~90% of the *most advanced* (sub-5nm) chips but ~60% of
*all* foundry output. The cross-check earned its keep by flagging the one
number that needed an asterisk.

Three kinds of force create these bottlenecks, and every row is one of them:
**technology** (the physics of EUV, the network effects of search), **regulation**
(credit ratings and proxy advice are quasi-official gatekeepers written into
rules), and **geography** (China's rare-earth refining, one nation's grip on a
processing step). Concentration is not a coincidence of any single industry;
it is what happens wherever a bottleneck can form.

## F2 — Control without ownership: the dual-class wedge

![The dual-class wedge](figures/10_dual_class.png)

Chapter 6 drew the line between *stewards* (who run others' money) and *owners*
(who run their own). There is a third move, the most direct answer to "who
makes the decision behind the money": **control the votes without owning the
company.** Through super-voting share classes, a founder or family commands the
firm while holding a small slice of its economics:

| | Voting power | Economic stake |
|---|---|---|
| **Zuckerberg — Meta** | **58%** | 13% |
| Page & Brin — Alphabet | 51% | 11% |
| Ford family — Ford | 40% | **2%** |
| Murdoch family — Fox/News Corp | 39% | 14% |
| Roberts — Comcast | 33% | 1% |

Mark Zuckerberg controls an outright *majority* of Meta's votes — every
director, every acquisition, every strategic pivot for ~3 billion users — on a
13% economic stake; the **Ford family runs Ford on 2%**; the Roberts family
runs Comcast on 1%. This is the ownership society's fine print: the "1.1% of
the stock market" the bottom half owns (Chapter 6) carries votes, but the
votes that *decide* are welded to founders through a share structure the index
funds cannot touch. Ownership is diffuse; control is not.

## F3 — Who manages the world's savings

![Capital pools](figures/10_capital_pools.png)

Zoom out to the pools of investable capital themselves — the money that buys
the shares that carry the votes. Set the private US index managers beside the
sovereign wealth funds of entire nations:

- **BlackRock alone ($11.5T)** manages more than the six largest sovereign
  wealth funds *combined*. The **Big Three together (~$25T)** exceed **every
  major SWF on Earth put together (~$7T)** by more than threefold.
- The largest state pools — Norway's oil fund ($1.8T), China's CIC ($1.4T),
  Abu Dhabi ($1.0T), Saudi Arabia's PIF ($0.9T) — are each a single
  decision-making body directing a nation's collective savings.

So the world's savings are managed by a startlingly short list: **three
private American firms and a dozen state funds.** Whether the manager is a
Boston mutual, a Gulf monarchy, or the Chinese state, the structure is
identical — an enormous pool, a tiny committee.

## The people at the top

The chokepoints have faces, and the Forbes billionaire ledger names them: the
individuals who *personally control* chokepoint firms — Musk ($798B, and the
controlling shareholder of Tesla, SpaceX, and X), the Google founders ($285B +
$262B), **Jensen Huang** of Nvidia ($175B, the AI-accelerator monopoly),
Ellison of Oracle, Dell, Zuckerberg, the Microsoft alumni (Gates, Ballmer).
The pattern of Chapter 6 holds economy-wide: the people who *own* the
chokepoint (founders) become centibillionaires; the people who merely *operate*
one (ASML's or SWIFT's or ISS's executives) do not. The fortune tracks
ownership of the bottleneck, not the running of it.

## What it means

The recurring "rule of few" is not a conspiracy; it is a *structure*.
Bottlenecks form wherever physics (EUV), network effects (search, operating
systems), regulation (ratings, proxy advice, payment rails), or geography
(rare earths) make a step hard to replicate — and whoever holds that step
holds everyone downstream of it. The concentration this report keeps
finding — in wealth (Chapter 5), in banks and index votes (Chapter 6), in land
(Chapter 7) — is one instance of a general law. The chokepoint is the unit of
modern power, and there are far fewer hands on the levers than the diffuse
language of "markets" and "shareholders" suggests.

## Caveats

- **Curated, not computed.** Market shares are from industry reports and
  company proxies, with the definitional fuzziness the AI cross-check makes
  visible (F1's TSMC case). Treat them as well-sourced estimates with ±5–10pp
  bands, and the *pattern* (1–4 controllers, 60–100%) as the robust finding.
- The AI panel is a *corroboration* layer, not ground truth — the models share
  training data and can share errors; a ✓ means "not obviously wrong to three
  independent frontier models," a useful but limited signal. Full transcripts
  are logged to `data/panel/runs.jsonl`.
- Voting/economic splits (F2) are point-in-time from the latest proxy
  statements and shift with share sales.
- SWF AUM figures vary by source and by whether central-bank reserves are
  counted; ranks are firmer than exact levels.

*Next: Chapter 11 — Dynasties: whether this kind of control persists across
centuries.*
