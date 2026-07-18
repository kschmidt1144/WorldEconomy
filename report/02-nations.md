# Chapter 2 — Nations & macro today

*World Economy Lab. Generated 2026-07-17; module `econlab/analysis/ch02_nations.py`,
findings pinned by tests. IMF projection years are shaded in figures.*

**The questions.** What does the country landscape look like right now? How
was inflation tamed — and how fragile was the taming? Whose debts ratcheted,
and does the arithmetic (r−g) make them sustainable?

## F1 — The development landscape, 2023–25

![Growth landscape](figures/02_growth_landscape.png)

Growth now lives in the poor-and-catching-up middle: India ~7%/yr, Vietnam and
much of South/Southeast Asia 5–7%, China ~5% (slowing but still double the
rich world), the US ~2.7%, Germany hugging zero. Sub-Saharan Africa grows in
the 3–7% range — but from income levels 30–80× below the frontier, and (Ch. 1)
only since ~2000 fast enough to close the gap.

## F2 — The taming of inflation, and the relapse

![Inflation regimes](figures/02_inflation_regimes.png)

Computed from ~200 countries' CPI paths:

- **1980: 74% of countries had inflation above 10%**; 12 above 40%.
- **2010: 8%** above 10%, none above 40% — the great disinflation was global,
  not just Volcker's America.
- **2022: 34%** above 10% again — the largest relapse since the early 1990s —
  fading to 14% by 2025.

The catalog of catastrophes (worst WEO country-years): Venezuela 2018
(**65,374%**), DR Congo 1994 (23,773%), Venezuela 2019 (19,906%), Nicaragua
1987 (13,110%), Bolivia 1985 (11,750%), Peru 1990 (7,482%). Every one is a
fiscal collapse financed by the printing press — inflation's extreme tail is
always a fiscal phenomenon.

## F3 — The debt ratchet

![Debt distribution](figures/02_debt_distribution.png)

Median general-government debt/GDP for high-income countries: 40% (1980) →
43% (2007) → **60% (2020)** → 56% (2024). Each crisis ratchets the level up;
no peacetime consolidation has ever brought it back down. Emerging economies
run structurally lower ratios (39% median, 2024) — not prudence, but harder
borrowing constraints and periodic restructurings.

## F4 — r − g: the quiet variable that decides everything

![r minus g](figures/02_r_minus_g.png)

Whether debt melts or compounds depends on the gap between the interest rate
and nominal growth. Computed for the US, 1872→2026, the regimes are stark:

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
has. Today's configuration (121% of GDP, r−g mildly negative) is stable only
while growth and inflation stay above the Treasury curve — a bet, not a law.

## Caveats

- GDD high-income medians before ~1970 rest on thin samples (n≈8 in 1950).
- WEO inflation is annual-average CPI; hyperinflation peaks measured monthly
  are far worse than the annual figures shown.
- r−g uses the 10-yr Treasury as "r" — the government's actual average
  funding rate is smoother and lags the market rate.

*Next: Chapter 3 — Money & markets: what assets have actually returned for
150 years, what valuations say now, and how credit booms end.*
