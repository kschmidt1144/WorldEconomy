# Chapter 2 — Nations & macro today

*World Economy Lab. Generated 2026-07-19; module `econlab/analysis/ch02_nations.py`,
findings pinned by tests. IMF projection years are shaded in figures.*

**The questions.** What does the country landscape look like right now — who
is catching up and who is falling behind? How was inflation tamed, and how
fragile was the taming? Whose debts ratcheted? How does the world's money
actually flow between nations — and what currency does it flow in? And under
it all: does the arithmetic (r−g) make any of this sustainable?

## F1 — The development landscape, 2023–25

![Growth landscape](figures/02_growth_landscape.png)

Growth now lives in the poor-and-catching-up middle: India ~7%/yr, Vietnam and
much of South/Southeast Asia 5–7%, China ~5% (slowing but still double the
rich world), the US ~2.7%, Germany hugging zero. Sub-Saharan Africa grows in
the 3–7% range — but from income levels 30–80× below the frontier, and (Ch. 1)
only since ~2000 fast enough to close the gap. The cross-section is a snapshot;
the story is the *movie* — which is F2.

## F2 — The convergence ladder: three fates

![Convergence ladder](figures/02_convergence_ladder.png)

Run each country's GDP per capita as a share of the US, 1900→2022 (Maddison),
and every nation falls into one of three fates:

- **The climbers.** South Korea went from ~10% of US income in 1960 to **71%**
  today — the single greatest catch-up in the record. China ran from ~5% (1980)
  to **33%**; the whole East Asian miracle is this one line-shape repeated.
- **The frontier.** Germany (80%), Japan (65%), Britain (66%) have oscillated
  in a band just below the US for a century — the rich world converged *with
  each other* long ago and has stayed there.
- **The regression.** And then **Argentina** — the cautionary tale of the
  whole chapter. In **1913 Argentina was at 60% of US income, richer per head
  than France or Germany**, one of the ten richest countries on Earth. It then
  spent a century falling: 52% (1950), 44% (1980), **31% (2022)** — down to
  China's level. No war destroyed it; a century of institutional dysfunction,
  inflation, and default did. Convergence is not automatic, and development can
  run in reverse.

## F3 — The taming of inflation, and the relapse

![Inflation regimes](figures/02_inflation_regimes.png)

Computed from ~200 countries' CPI paths:

- **1980: 74% of countries had inflation above 10%**; 12 above 40%.
- **2010: 8%** above 10%, none above 40% — the great disinflation was global,
  not just Volcker's America.
- **2022: 34%** above 10% again — the largest relapse since the early 1990s —
  fading to 14% by 2025.

The catalog of catastrophes (worst WEO country-years) shows what the tail
looks like when it fails completely:

| Country | Year | Annual CPI |
|---|---|---|
| Venezuela | 2018 | **65,374%** |
| DR Congo | 1994 | 23,773% |
| Venezuela | 2019 | 19,906% |
| Nicaragua | 1987 | 13,110% |
| Bolivia | 1985 | 11,750% |
| Peru | 1990 | 7,482% |

Every one is a fiscal collapse financed by the printing press. **Inflation's
extreme tail is always a fiscal phenomenon** — a government that cannot tax or
borrow enough prints the difference, and the currency dies.

## F4 — The debt ratchet

![Debt distribution](figures/02_debt_distribution.png)

Median general-government debt/GDP for high-income countries: 40% (1980) →
43% (2007) → **60% (2020)** → 56% (2024). Each crisis ratchets the level up;
no peacetime consolidation has ever brought it durably back down. Emerging
economies run structurally lower ratios (39% median, 2024) — not prudence, but
harder borrowing constraints and periodic restructurings (the sovereign
default ledger is Chapter 5). Whether these levels are dangerous depends
entirely on F7's r−g.

## F5 — Global imbalances: the world lends to one country

![Global imbalances](figures/02_global_imbalances.png)

Money flows between nations through the current account — a surplus country is
lending to the rest of the world, a deficit country borrowing from it. In 2024
the surpluses cluster in the exporters and agers: **China +$417bn, Germany
+$272bn, Japan +$189bn**, Taiwan, Netherlands, Korea. And on the other side of
the ledger, absorbing nearly all of it, sits one country: **the United States,
−$1,172bn** — a deficit roughly equal to *the sum of every major surplus
combined*.

This is the modern monetary order in one bar chart. The world's savers
(export-led Asia, surplus Europe, the oil states) send their capital to the
US, which runs the deficit that lets everyone else run a surplus, and pays for
it by issuing the world's reserve asset — Treasuries. It is stable as long as
the surplus nations keep wanting dollars. Which raises F6.

## F6 — What the world holds: dollar dominance, slowly eroding

![Reserve currencies](figures/02_reserve_currencies.png)

The currency composition of the world's ~$12-trillion of official FX reserves
(IMF COFER), the hardest measure of monetary hegemony there is:

| | USD | EUR | JPY | GBP | CNY |
|---|---|---|---|---|---|
| 1999 | **71%** | 18% | 6% | 3% | — |
| 2025 | **56%** | 20% | 6% | 4% | **2%** |

Two facts, both important. First, **the dollar's dominance is real but
eroding** — down ~15 points in a quarter-century, a slow structural drift as
central banks diversify. Second, and more surprising: **the loss has not gone
to the renminbi.** Despite China being the world's largest exporter and second
economy, the yuan has stalled at ~2% of reserves — capital controls and an
unconvertible currency keep it from reserve status. What actually gained were
the "nontraditional" currencies (Canadian and Australian dollars, the Swiss
franc, and a rising "other" bucket): the world is hedging *away* from the
dollar, but toward a basket, not toward a single successor. There is no
challenger; there is only diversification.

## F7 — r − g: the quiet variable that decides everything

![r minus g](figures/02_r_minus_g.png)

Whether the debts of F4 melt or compound depends on the gap between the
interest rate and nominal growth. Computed for the US, 1872→2026, the regimes
are stark:

| Era | mean r − g |
|---|---|
| 1880–1913 (classical) | −0.9pp |
| 1919–1939 (interwar deflation) | **+1.9pp** |
| 1946–1980 (financial repression) | **−2.7pp** — the WWII debt *melted* |
| 1981–2000 (Volcker regime) | **+1.7pp** — debt compounds |
| 2001–2020 | −0.5pp |
| 2024–26 (current) | ≈ **−1.3pp** (10Y ~4.3% vs nominal growth ~5.5–6%) |

The postwar miracle of "growing out of" 119% debt/GDP was mostly *melting*
out of it: a decade of negative real rates did what no budget surplus ever
has. Today's configuration (US public debt ~121% of GDP, r−g mildly negative)
is stable only while growth and inflation stay above the Treasury curve — a
bet, not a law, and the same bet the whole imbalance system in F5 quietly
depends on.

## Caveats

- GDD high-income medians before ~1970 rest on thin samples (n≈8 in 1950).
- WEO inflation is annual-average CPI; hyperinflation peaks measured monthly
  are far worse than the annual figures shown.
- The convergence ladder uses Maddison GDP-per-capita; pre-war Argentina and
  other early figures carry wider error bands than the modern series, but the
  *direction* (a 30-point fall relative to the US) is unambiguous.
- COFER covers only *allocated* reserves (~93% of the total); the "unallocated"
  remainder is not attributed to currencies. Shares are of the allocated pool.
- r−g uses the 10-yr Treasury as "r" — the government's actual average funding
  rate is smoother and lags the market rate.

*Next: Chapter 3 — Money & markets: what assets have actually returned over the long run, and the price of risk.*
