# Chapter 3 — Money & markets

*World Economy Lab. Generated 2026-07-17; module `econlab/analysis/ch03_money.py`,
findings pinned by tests.*

**The questions.** What do assets actually return over long horizons? Do
valuations predict anything? What warns of financial crises? And how
top-heavy has corporate America become?

## F1 — The rate of return on everything (reproduced)

![Return on everything](figures/03_return_on_everything.png)

Pooled over 16–18 economies, 1870–2020, real annual returns computed from JST
total-return series against each country's CPI:

| Asset | mean real return |
|---|---|
| **Equities** | **6.9%/yr** |
| **Housing** | **6.9%/yr** |
| Government bonds | 2.4%/yr |
| Bills | 1.0%/yr |

The headline of Jordà-Knoll-Kuvshinov-Schularick-Taylor's *Rate of Return on
Everything*, reproduced from primary data: risky assets ≈ 7% real for 150
years — housing as much as equities, with half the volatility — and the gap
over safe assets (~5pp) **is** Piketty's r > g in asset form. Wealth that is
invested compounds faster than economies grow; Chapter 5 shows what that does
to distributions.

## F2 — Valuations predict the decade, not the year

![CAPE vs forward returns](figures/03_cape_forward.png)

Every month 1881–2016 plotted: starting CAPE vs the *next ten years'*
realized real total return. The fit: **forward return ≈ 13.0 − 0.38 × CAPE**
(so each CAPE point costs ~0.4pp/yr of the following decade). The scatter is
wide — valuation is nearly useless for the next year — but the decade slope
is unmistakable.

**July 2026: CAPE = 41.4, the 99.1st percentile of 145 years.** The naive
fitted implication is ≈ **−2.6%/yr real for 2026–2036**. Historical months
with CAPE > 38 (1929, 1998–2000, 2021) delivered −5 to +2%/yr over their
following decades. This is arithmetic, not prophecy: high prices on the same
cash flows are borrowed future returns.

## F3 — Credit booms precede crises (Schularick–Taylor, reproduced)

![Credit and crises](figures/03_credit_crises.png)

Across 18 economies and 150 years: in the 1–2 years before a systemic
banking crisis, trailing 5-year real credit growth averaged **7.4%/yr**,
versus **4.5%** in all other times. A logit of crisis onset on credit growth
(hand-rolled IRLS — no black boxes) gives **β = +4.7**: moving credit growth
from 4.5% to 7.4% roughly **doubles the near-term crisis odds** off a ~6%
base rate. "This time the lending is sound" has been wrong for a century and
a half; credit growth remains the single best early-warning indicator known.

## F4 — Corporate concentration: real, but smaller than folklore

![Concentration](figures/03_concentration.png)

Measured honestly — top-10 share of the **top-500** US filers' revenues (a
fixed universe; shares of *all* filers would be a coverage artifact, since
EDGAR's XBRL population tripled over 2010–2024) — concentration bottomed in
2018 at 19.4% and has climbed every year since: **22.8% in 2025**. Rising,
clearly; but revenue concentration is far milder than the market-cap
concentration that dominates headlines — profits and valuations concentrate
much faster than sales.

## Also computed

- **Yield curve** (10Y−2Y): +0.37pp as of July 17, 2026 — re-steepened after
  the 2022–24 inversion, the classic post-inversion, mid-easing shape.
- Credit spreads: high-yield OAS 2.71% — top-decile tightness; markets are
  priced for tranquility at the 99th valuation percentile.

## Caveats

- JST returns are annual and survivorship-light but not survivorship-free
  (Russia 1917 and similar total losses are absent).
- CAPE regression is descriptive; overlapping 10-yr windows overstate
  statistical precision (the slope, not the t-stat, is the point).
- Pre-2016 EDGAR concentration levels remain composition-contaminated even
  in the fixed universe; the post-2018 trend is the reliable part.

*Next: Chapter 5 — Wealth & people: who owns what, a century of top shares,
and what happened to labor's slice.*
