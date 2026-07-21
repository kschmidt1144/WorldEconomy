# Chapter 5 — The Debt Ledger: who owes, who owns, who pays

*World Economy Lab. Generated 2026-07-17; module `econlab/analysis/ch05_debt.py`,
findings pinned by tests. Companion to Chapter 9: there the asset side of
power, here the liability side — and the interest that flows between them.*

## F1 — Who owes: nations, people, companies

| Government debt, 2024 | $T | %GDP | per person |
|---|---|---|---|
| United States | **35.4** | 121% | **$104,085** |
| China | 16.7 | 88% | $11,800 |
| Japan | 9.9 | **237%** | $80,039 |
| UK / France / Italy | 3.7 / 3.6 / 3.2 | 101–135% | $52–55k |

Corporate side, from the SEC ledger: the largest borrower in America is
**Fannie Mae ($4.15T of long-term debt)** — the mortgage system itself —
followed by the big banks (Morgan Stanley $363B, BofA $326B, Citi $316B).

## F2 — Who owns the US federal debt

![Who owns the federal debt](figures/05_who_owns_federal_debt.png)

$39.1T decomposed: **$27.0T domestic private investors** (funds, banks,
pensions, households) · **$9.3T foreign** (TIC cross-validates FRED within
1%) · **$4.7T Federal Reserve** (post-QT, from ~$8.5T). America mostly owes
itself; foreign holders peaked at 34% (2014) and have *fallen* to ~24%.

Among foreigners (May 2026): **Japan $1,143B → UK $949B → China $659B**.
Two anti-folklore facts: **China has cut its holdings 36% since early 2022
and now ranks third** — it holds under 1.7% of US federal debt; and the
Belgium/Cayman/Luxembourg entries (~$450B each) are custody chains, not
national positions — the honest limit of ownership data. (Wiring this
uncovered a trap: Treasury's classic `mfh.txt` mirror **froze in March
2023**; the live table is `slt_table5.txt`, and a staleness test now guards it.)

**Follow the money, and lose the trail.** That custody caveat is worth pulling
on, because it is far bigger than a footnote. Rank *all* the foreign holders and
the second-largest — ahead of China — is the **United Kingdom ($949B)**, which
is not the British public but **London custody**. Below it sit **Belgium
($472B) — Euroclear**, the international securities depository; **the Cayman
Islands ($471B)**, **Luxembourg ($436B)** and **Ireland ($357B)**, fund and SPV
domiciles; and **Switzerland ($281B)**, private banking.

![Who finances America](figures/05_who_finances_america.png)

Add the six together and **$2.97 trillion — 31.7% of all foreign-held US
Treasuries — sits behind custodians whose beneficial owners are simply not in
the data.** The absurdity is clearest at Belgium: 11.7 million people "holding"
$472B is roughly **$40,000 of Treasuries per resident, versus ~$470 per person
in China — an 86× gap** — because it is not Belgians buying, it is Euroclear
booking the world's bonds in Brussels. So the folk phrase "the world lends to
America" is true, but for nearly a third of it *who* the world is cannot be read
from the ownership data at all — the purest follow-the-money-and-lose-the-trail
series in this whole report. What we *can* see is shifting underneath the
opacity: the dollar's share of disclosed FX reserves has slipped to **56%**
(COFER, from ~70% in 2000) and China has cut its own stake 36% since 2022 — but
the veil means we cannot fully see who is stepping in behind them. (The
by-country history needed to watch that veil thicken over time isn't yet in the
warehouse — the `mfh.txt` archive froze in 2023 — a backfill for another dig.)

## F3 — What US households pay

![Debt service](figures/05_debt_service.png)

Measured (Fed): **11.2% of disposable income** goes to debt service — 5.9pp
mortgage + 5.3pp consumer. The 2007 peak was 15.7%; the 2021 floor 9.8%.

Computed (stocks × rates, assumptions stated): **≈ $1.13T of interest per
year**, ≈ $8,600/household:

| Type | Stock | Rate | Interest/yr |
|---|---|---|---|
| Mortgages | $13.85T | 4.3% *(effective; new loans 6.5%)* | $596B |
| Credit cards | $1.34T | **20.9%** (Fed-measured) | $281B |
| Auto | $1.57T | 7.5% (Fed-measured) | $117B |
| Student | $1.78T | 5.5% (assumption) | $98B |
| Other | $0.46T | 8.0% (assumption) | $37B |

Credit cards: **7% of the debt, 25% of the interest.**

Cross-country (BIS common methodology — right panel): the US at **8.0%** is
mid-pack. **Norway 20.7%, Australia 15.5%, Canada 14.0%** — the
variable-rate, expensive-housing economies — vs Italy at 4.2%. Household
debt stocks agree: Switzerland 125% of GDP, Australia 112%, **US 69%** (the
US actually deleveraged after 2008). America's burden problem is
*composition*, not level.

## F4 — Who pays what: income

![Interest by income](figures/05_interest_by_income.png)

| Income group | Interest/hh/yr | Blended rate | Consumer share of debt |
|---|---|---|---|
| Bottom 20% | $2,111 | **7.0%** | 45% |
| Middle (40–60%) | $6,715 | 6.3% | 33% |
| 80–99% | $17,018 | 5.5% | 20% |
| Top 1% | $47,032 | **5.2%** | 14% |

**The poor borrow expensive; the rich borrow cheap.** Nearly half the bottom
quintile's debt is 10–21% consumer credit; 86% of the top 1%'s is ~4%
mortgage money — leverage against assets returning 7% real (Ch. 3). The same
households who own 1.1% of equities (Ch. 9) pay the highest price for money:
the ownership channel, running in reverse.

**Debt → interest → income, year-aligned (2024 debt stocks, 2024 Census mean
money income):**

| Bracket | Income/hh | Debt/hh | Interest/hh | **Debt/income** | **Interest/income** |
|---|---|---|---|---|---|
| Bottom 20% | $18,460 | $28,757 | $2,022 | **1.56×** | **11.0%** |
| 20–40% | $49,380 | $53,552 | $3,778 | 1.08× | 7.7% |
| 40–60% | $84,390 | $103,661 | $6,580 | 1.23× | 7.8% |
| 60–80% | $136,800 | $167,608 | $10,165 | 1.23× | 7.4% |
| Top 20% | $316,100 | $331,155 | $18,226 | 1.05× | **5.8%** |

Both ratios are regressive: the bottom quintile is simultaneously the *most
leveraged relative to income* (1.56×) and pays the *highest interest share*
(11.0% — nearly double the top's 5.8%) — while holding the least debt in
dollars. The middle class clusters at ~1.1–1.2× and ~7.5%. (CPS money income
misses top capital income — true top ratios are even lower — and misses
in-kind transfers at the bottom; group-level rates understate what
low-income borrowers actually pay. The offsets don't cancel: every
refinement steepens the gradient.)

## F5 — The interest burden through time: regressivity is post-2008

![Burden history](figures/05_burden_history.png)

Estimated interest ÷ mean bracket income, 1994→2024, with time-varying rates
(mortgage: 10-yr trailing mean of the 30-yr rate as effective-rate proxy;
consumer: card/auto rates weighted by the national stock mix):

| | 1995 | 2007 | 2010 | 2016 | 2021 | 2024 |
|---|---|---|---|---|---|---|
| Bottom 20% | 9.7% | 13.2% | **18.1%** | 9.6% | 9.8% | **12.2%** |
| 60–80% | 10.9% | **13.8%** | 10.6% | 6.6% | 6.1% | 8.2% |
| Top 20% | 9.4% | 11.2% | 9.8% | 6.0% | **4.8%** | 6.3% |

Three eras, one story:

1. **Before 2008 the burden was roughly classless** — in 1995 the gap
   between bottom and top was 0.3pp, and at the credit-boom peak the
   *60–80%* bracket was the most burdened (13.8%): mortgage debt was
   democratic, and so was its cost.
2. **2008–2010 hit the bottom asymmetrically**: their income crashed while
   their debt stayed — the bottom quintile's burden spiked to **18.1%** in
   2010, the worst reading for any group in the record.
3. **The cheap-money decade rescued the mortgage classes and skipped the
   poor.** Refinancing at 3% halved the burden for every bracket that
   borrows against houses (Top 20%: 11.2% → 4.8%). Credit-card rates never
   fell below ~7%, so the bottom quintile's floor stayed ~9.5%. Then
   2022–24 card rates (record ~21%) reopened the scissors: **12.2% vs 6.3%
   — a 6.0pp gap, the widest outside the crisis itself.**

The regressive interest burden is not an eternal fact — it is a *policy
era*. It was manufactured after 2008 by a rescue channel (cheap secured
credit) that the bottom quintile structurally cannot access.

## F6 — Who pays what: race, age, education

![Demographic burdens](figures/05_demographic_burdens.png)

- **Race:** Black households carry *more consumer debt per household
  ($48.5k) than White households ($37.3k)* but less than half the mortgage
  debt — **49% of their borrowing is expensive money vs 25%** (blended ~7.3%
  vs ~5.8%). Same interest bills, opposite functions: one builds home
  equity, the other finances the gap. This *understates* the disparity,
  since within each debt type minority borrowers face above-average rates.
- **Age:** the lifecycle peak is 40–54 (**$12,148/hh/yr**); under-40s carry
  a 33% consumer share (student debt); 70+ fades to $3,886.
- **Education:** college households borrow the most (**$219k/hh**) at the
  best composition (24% consumer) — big cheap debt is a privilege of
  collateral and income. No-HS households borrow least, yet 40% of it is
  expensive.

## F7 — The sovereign ledger: who defaults, and who never has

![Sovereign defaults](figures/05_sovereign_defaults.png)

Everything above this is *household* debt — money that must be repaid because
no family can simply declare its debts void. Above the households sits the
one borrower who can: the sovereign. A government that cannot pay does not go
bankrupt in a court; it *defaults* — and default is the oldest event in
finance, distributed with a striking regularity across nations.

The historical record (curated from Reinhart & Rogoff's *This Time Is
Different*) splits the world into two clubs. The **serial defaulters**, led by
**Spain — 13 external defaults since 1800**, the all-time champion — followed
by Venezuela (11), Ecuador (10), and a long Latin American and southern
European tail that has restructured its external debt eight or nine times
each. And the **never-defaulted club**: the United States, England, the
Commonwealth dominions, Scandinavia, and (a modern addition) the disciplined
exporters of East Asia — sovereigns that have *never once* failed to pay
external creditors. The lesson of the two clubs is Reinhart & Rogoff's
central finding: **default is not mainly about how much you owe, but about
whether your institutions treat repayment as non-negotiable.** Spain
defaulted at debt levels a fraction of what Britain carried through the same
centuries without missing a coupon.

The right panel adds the *banking*-crisis clock computed from Chapter 3's
JST flags: the share of economies in systemic crisis peaked in the **1930s
(7.8%)**, went almost silent through the repressed Bretton-Woods decades
(1940s–1960s ≈ 0), and returned to **1930s levels in the 2000s (7.2%)**. The
two panels rhyme: sovereign default and banking crisis are the two ways the
credit system fails, and both were tamed for one mid-century generation and
have since come back.

**From curated to computed.** The ledger above is hand-counted from published
scholarship. We can now *compute* the modern record directly, from the Bank of
Canada–Bank of England sovereign-default database — an annual stock of every
government's defaulted debt, 1960–2023:

![Computed sovereign defaults](figures/05_defaults_computed.png)

Two things curation could not give. First, **the dollar scale**: the single
largest sovereign default on record is **Greece's 2012 PSI restructuring —
$312 billion** in defaulted debt, larger than Brazil's 1980s crisis ($149B),
Argentina's 2001–05 collapse ($115B), or Iraq's war arrears ($111B). And the
Eurozone crisis put *advanced* economies back in the ledger for the first time
in generations — Greece, Ireland ($88B), Portugal ($53B), Puerto Rico ($61B).
Second, and decisively, **the computed data confirms Reinhart & Rogoff's thesis
that default is about institutions, not debt levels** — the right panel plots
every country's gross debt/GDP against its number of defaults since 1960, and
there is *no positive relationship*. The nine sovereigns that have **never
defaulted since 1960** — Japan, Singapore, the US, Canada, the Netherlands,
Switzerland, the Nordics — carry an **average of 93% of GDP in debt**, *more*
than the serial defaulters' 75%. **Japan carries 215% of GDP and has never
missed a coupon; Turkey has defaulted seven times, never above 24%.** Debt
intolerance is a property of institutions and credibility, not of the ratio on
the balance sheet — exactly the two-club pattern the curated ledger drew, now
reproduced from a computed database with the arithmetic attached.

## Caveats

- The since-1800 default *counts* are curated from published scholarship
  (Reinhart-Rogoff); counts vary by ±1–2 with the definition of "default"
  (missed payment vs restructuring vs redenomination), and any single
  country's exact number is approximate. The modern record (dollar amounts +
  episodes since 1960) is now **computed** from the BoC–BoE database and shown
  alongside; the two-club pattern is robust in both. The computed panel starts
  in 1960, so pre-1960 serial defaulters (Spain especially) fall outside it.
- Interest-only estimates; the 11.2% ratio includes principal. BIS DSR uses
  a common 18-yr amortization assumption (that's *why* it's comparable) —
  the Fed's 11.2% and BIS's 8.0% are both correct answers to different
  questions.
- Mortgage effective rate (4.3%) is a stated assumption — the stock is
  dominated by pandemic-era coupons; using the 6.5% new-loan rate would be
  wrong. Group-level estimates apply aggregate rates to group stocks;
  true within-group rates worsen every disparity shown.
- Student-loan interest is currently distorted by federal
  forbearance/IDR plans; the 5.5% is contractual, not necessarily paid.

*Next: Chapter 6 — Wealth & People: who owns the assets behind the debt, and how unequally.*
