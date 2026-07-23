# Chapter 13 — Synthesis: how it got this way

*World Economy Lab. The capstone: every claim below points at a computation in
Chapters 0–12. The report can be read six ways, and this chapter reads them in
turn — down the **time axis** (the arc, 1870→2026); across the two **spines of
concentration** (who *owns*, and who *decides*); through the **market** that
breaks and heals; along the seam of **war**; down into the **household**; and
**geographically**, following the money to the one hub it all runs through — then
closes on the state of the world, computed fresh from the warehouse each build.*

![Vital signs](figures/13_vital_signs.png)

## The instrument

Before the findings, the machine that made them. Every number in this report is
computed in-repo from **free primary sources** — raw downloads → tidy parquet → a
DuckDB warehouse of **~50 sources, ~15 million observations, year 1 CE → 2101** —
and **190 tests re-derive the load-bearing findings on every build, so the tests
fail before the prose can lie.** A unit-type discipline (nine unit-types, never
mixed) guards the domain's oldest trap, confusing nominal, real, and PPP dollars.
The point of the apparatus is that this synthesis is not an essay about the world;
it is a *reading of a live instrument*, and every figure below regenerates with
one `econ refresh`.

## The arc, 1870 → 2026

**1870–1913 — The first globalization.** Openness climbs to 45% of GDP (Ch. 4);
the gold standard holds r−g near zero (Ch. 2); the West's share of world output
peaks at **59.2% in 1913** (Ch. 1) and the *global* top-10% income share peaks near
**60%** (Ch. 6) — global inequality's all-time maximum was the colonial world, not
ours. Banking crises hit ~half of economies each decade: integrated,
gold-constrained finance was crisis-prone.

**1914–1945 — The demolition.** Trade integration *un-happens*: openness 27% by
1938. Deflation and inflation whipsaw (US: +24% in 1917, −16% in 1921, −10% in
1932). The 1930s put 61% of economies into systemic banking crisis. Two war
mobilizations take US debt to 119% of GDP. Every "it can't reverse" about
integration died in this window.

**1946–1973 — Bretton Woods: the anomaly.** The fastest world growth ever recorded
(**2.79%/yr per person**, Ch. 1) *and* the only two decades in 150 years with **zero
systemic banking crises** (repressed, segmented finance) — while financial
repression's r−g of **−2.7pp** quietly melted the war debt (Ch. 2) and top-1% shares
compressed to ~10% (Ch. 6). Fast growth, stable finance, falling inequality — the
combination has not been repeated.

**1973–2000 — The great reordering.** The anchor breaks in 1971; by 1980, **74% of
countries have inflation above 10%** (Ch. 2). Volcker flips r−g to +1.7pp — debt now
compounds — and finance deregulates: crisis frequency returns. The US top-1% share
starts its round trip back to 20% (Ch. 6); labor's share begins its seven-point
slide. Meanwhile poor countries *diverge* through 2000 — globalization's first act
lifted the West and Japan, not yet the rest.

**2000–2026 — The China era, on leveraged foundations.** Convergence finally flips
positive (~2000, Ch. 1); world growth per person runs at **2.40%/yr** — second only
to the Golden Age — and global inequality *falls* for the first time in two
centuries. China goes from #1 supplier of 8 countries to **96** (Ch. 4). The same
era's finance put **72% of economies into systemic crisis** — broader than the
1930s — answered by QE, a debt ratchet (high-income median 43% → 60%), and by 2026
a **CAPE of 41 at the 99th percentile** of 145 years (Ch. 3). Openness plateaus at
~57%: not deglobalization — reconfiguration under a leveraged sky.

Two structural facts sit under the whole arc. First, **growth itself is a 200-year
anomaly**: from year 1 to 1820 income per person grew ~**0.002%/yr**, and by 2022
the two Asian giants (28.8% of world output) and the whole West (31.1%) produce
nearly equal shares — roughly the **1820 configuration restored** (Ch. 1). Second,
**the engine is switching off**: the population term that drove growth falls from
1.90%/yr in the Golden Age to **0.31%/yr for 2022–2100**, and world population peaks
at **10.29 billion in 2084** — so every future gain must come from productivity, in
economies that are aging (China's median age 20.9 in 1980 → 52.1 by 2050) and cannot
yet run rich on little energy (Ch. 4).

## Spine I — Who owns: concentration by default

Half of this report was built by following one question — *who controls what?* —
into every corner of the economy, and it kept returning the same shape. Not a
conspiracy; an **arithmetic**. From several independent directions, a few hold a lot:

- **Assets.** The US top 1% own **~32%** of household wealth; the bottom half,
  **2.5%** (Ch. 6). The gap widens *mechanically*: the top 0.1% hold their wealth as
  productive capital, the bottom half as a house and a car. The line drawn in 1929,
  erased by 1975, has been redrawn.
- **The ground.** Land concentrates too — the federal government alone holds
  ~**15× the hundred largest private owners combined**, and value pools where people
  are: cities generate ~90% of GDP on **3%** of the land (Ch. 7).
- **Institutions.** Finance shifted from banks to funds — banks consolidated
  **~30,500 → ~4,300** while a new form, the index manager, rose past any bank
  (**BlackRock $11.5T**, Ch. 9). The Big Three now are the largest single shareholder
  of **~88% of the S&P 500**, own a median **~25%** of the 500 largest firms, and cast
  **~25% of the votes** — through a few hundred stewardship staff (Ch. 9–10).
- **Labor's counterparty.** As ownership concentrated, labor's share of US output fell
  **~7 points since 1960** — on the order of **$2 trillion a year** moved from
  paychecks to capital (Ch. 6, 8).

## Spine II — Who decides: the apparatus of capture

Ownership is only half the shape. The report's longest thread (Chapter 10) followed
the *other* half — **who decides** — and found that control routinely splits off from
ownership, and that around every pool of public power or public wealth, a channel
evolves to convert it into private gain. **Influence, it turns out, is a market**,
and it clears most efficiently where the ratio of *power controlled* to *scrutiny
applied* is highest.

**Control detaches from ownership.** Super-voting shares let a founder command a
company he barely owns (Zuckerberg: **58% of the votes on 13% of the economics**). The
Big Three *own* ~25% of corporate America but *vote* it **~95% with management**. And
the single most powerful recurring meeting on Earth is not a billionaire summit but
the **FOMC**: twelve people, eight closed meetings a year, whose decisions move the
S&P **1.3×** a normal day — and across **130 meetings the chair's proposed action has
carried every single time**, against 65 dissents. Control concentrates not in twelve
people but in one.

**And the state itself is a set of capturable surfaces.** Reading them by branch:

- **Legislative & executive.** ~**18% of registered lobbyists are former officials**
  (~80% out of Congress); the top-five weapons primes captured **~$112B** of FY2024
  DoD contracts, seat **13 of 54 directors** who are retired generals, and the
  fourteen largest contractors employed **37,032 former DoD personnel** (Ch. 10). The
  loop's ROI is real but its *form* matters: gross ratios run $760–$1,400 of
  government money per $1 lobbied, but the best-*identified*, pure-profit return is a
  **tax rule-change** (the 2004 repatriation holiday, **~$220 saved per $1**; Eli
  Lilly turned $8.5M into $2B) — a rule-change is rent, a contract is revenue you must
  still deliver. Earmarks returned in 2022 (**$14.6B**, following placement not
  population — Alaska pulls ~20× California's per-capita haul).
- **Judicial** — the least-watched branch, captured both ways. State supreme-court
  election spending ran **$46M (2000) → $157M (2023–24)**, the first cycle in which
  outside groups outspent the candidates; on the federal side, **131 judges heard 685
  cases in companies they owned**, and the Supreme Court had **no ethics code until
  November 2023**.
- **The public estate.** The government owns **640M acres (28% of the country)** and
  charges below cost — or nothing — to strip its value: hardrock minerals pay a **$0
  royalty** (~$4.9B/yr taken free), grazing runs a **93% discount**, and the 1996
  spectrum giveaway handed broadcasters ~$70B free while auctions of the same airwaves
  later raised **$233B**.
- **State & local** — the retail end, where leverage is highest and scrutiny lowest.
  **90,837 local governments** spend ~$1.9T and seat 96% of America's elected
  officials; an LA County supervisor controls **~$38,000 of budget per $1 of salary**;
  and beyond the budget sit the bigger pools officials steer — **~$6T in public
  pensions**, **$4.2T in municipal debt**, **$45–90B/yr in development subsidies**
  (Foxconn: $4B promised, $80M delivered) — each with its own documented pay-to-play.
  Federal prosecutors convicted **4,422 local officials** of corruption over 2004–23.

The through-line of the whole apparatus: **almost none of it is illegal.** The deepest
chokepoints are not conspiracies but incentives, operating in the open.

**One honest counter-current** (Chapter 10's reality check): this spine is a law of
*ownership and control*, not of everything. Even as wealth, corporate control, and the
shrinking public market concentrated (top-1% wealth ~23% → ~32%; listed US firms
**halved to ~3,900**), the *physical and monetary commons* went the other way — the
**top-4 oil share fell 64% → 49%** and the **dollar's reserve share 76% → 56%**. The
hands tightened on who owns and who decides, and loosened on who pumps the oil and
whose money the world holds. But one of those loosenings is thinner than it looks —
as the hub section shows.

## The market: wounded by contagion, healed by the central bank

Turn the same instrument on the market itself (Chapter 3). Over three centuries risky
assets pay for their risk — equities and housing ~**6.9% real**, versus 2.4% for bonds
and 1.0% for bills — Piketty's r > g in asset form. But the *pain* those returns
compensate is hidden by nominal charts: in real terms there have been **12 drawdowns
of 20%+ since 1871**, the 1929 crash cost **−81% and took 29 years** to recover, and
the 1968–82 Great Inflation was a **−63% real** crash nearly invisible in nominal
prices.

Point a reusable event-study engine at a century of shocks and two laws emerge. First,
**only financial contagion consistently breaks markets** — a **−14%** median drawdown,
versus ~−7% for wars and pandemics and just −5% for political shocks; markets barely
flinch at ballots or bombs, and buckle at bank runs. Second, **only the central bank
consistently heals them** — **7 of the 12 biggest rallies of the past century are Fed
or monetary pivots**, and *buying the first shock of a systemic crash* still lost 2.5%
a year later, because the rebound comes from the bottom and the bottom is called by
policy. Widen it to every asset and the corollary is that **there is no unconditional
hedge**: gold is the one universal haven, but Treasuries — the reflexive safe asset —
**fail in a supply shock** (a mere +0.3%, and they *fell with stocks* in 2022, which is
why the 60/40 portfolio had its worst year in a century); developed markets crash in
lockstep (correlations ~0.9) while only a walled-off market like China's (0.51)
genuinely diversifies. The instrument even points forward: a CAPE of **41.4** implies
about **−2.6%/yr real** for the coming decade, and pre-crisis credit growth of ~7.4%
over five years roughly doubles near-term crisis odds.

## The economics of war

War is the seam where concentration and crisis meet. It is **net-destructive** — and
yet it reliably *transfers* wealth to whoever supplies what war consumes. In World War
II, the arsenal and the safe-distanced won while the battlefield lost: US real GDP per
person grew **+61%** and Britain ended 8% above 1938, while France fell to **54%**,
Japan to 65%, and Germany to **44%** of pre-war output (Ch. 2). The transfer runs
through commodities — a war spikes a commodity only when a belligerent supplies it (the
1990 Gulf War was **pure energy**: oil +80%, wheat *−30%*; the 2022 invasion of Ukraine,
whose combatants export energy, grain and metals, lit **every** category: coal +187%,
wheat +54%). And the arms trade is itself a chokepoint: since 1960 the **US alone
supplied 46%** of world arms exports, the top five 79%, and the five UN Security Council
members — the body charged with keeping the peace — **77%**. US military spending in
2022 (**$861B**) exceeded the next nine nations combined, and the post-Cold-War "peace
dividend" was one-sided: the US cut its burden from 6.1% to 3.1% of GDP, then rebuilt to
4.9%, while the rest of the world never re-armed. War sits at the intersection of the
capture apparatus (defense primes, the revolving door) and the market (the supply shock).

## The household ledger

Bring the arc down to the kitchen table (Chapter 8), and the aggregate good news frays.
The story is not broad unaffordability but a **specific split**: since 2000, the things
**made by people** outran every wage group while the things **made by factories**
collapsed — hospital services to an index of 343, college 266, childcare 235, against
new cars 125, apparel 101, and televisions **2**. Real wages did rise for every
percentile (median **+10%**, tenth +17%, ninetieth +25%), so the squeeze is
*composition*, not stagnation — but no wage quartile kept pace with care, and the
low-income basket rose **106%** against 97% for the high-income one. Debt then runs the
same hierarchy *in reverse*: the blended borrowing rate falls from **7.0% for the
bottom fifth to 5.2% for the top 1%**, credit cards are 7% of household debt but 25% of
its interest — and this regressive machine is a **manufactured post-2008 policy era**,
the bottom-minus-top interest-share gap widening from 0.3pp in 1995 to **6.0pp by 2024**
as cheap-money refinancing cut the wealthy's rates while credit-card floors held the
poor near 9.5%. The macro story got better; the median budget got tighter.

## The hub: America at the center of the world's money

Read the report geographically — following the money — and every arrow bends toward one
country. **The world lends to one nation.** In 2024 the surplus savers (China +$417bn,
Germany +$272bn, Japan +$189bn) shipped their capital abroad, and the United States
absorbed the largest share, running a **−$1,172bn current-account deficit — roughly half
of the world's surpluses** (Ch. 2), paid for by issuing the world's reserve asset. A
third of that lending is unreadable: **$2.97 trillion — 31.7% of foreign-held
Treasuries — sits behind custody domiciles** (London, Euroclear/Belgium, the Caymans)
whose true owners are not in the data; Belgium's residents "hold" ~$40,000 of Treasuries
each, an **86× gap** over China's ~$470, because it is Euroclear booking the world's
bonds in Brussels (Ch. 5).

Trace the arrow back *out*, and the visible channel is small while the invisible one is
enormous. Since 1960 the US has sent **$587bn in aid to 172 countries** — nine in ten
nations on Earth — but the real reach is the **Federal Reserve's dollar swap lines**:
after Lehman the balance went **$62B → $583B in twelve weeks** (26% of the Fed's balance
sheet, lent to *foreign* central banks). To feel the scale: **the Fed lent more to the
world in the single week of December 2008 ($583B) than the US gave in aid to all 172
countries over sixty-three years ($587B).** And a swap line is *membership*, granted at
US discretion — five allies hold permanent, unlimited lines; everyone else is outside,
including, pointedly, **the world's second-largest economy, which has never had one.**
The deepest lever the United States holds is not a grant or a weapon; it is the Fed's
willingness — or refusal — to backstop your banking system in dollars.

Which is why "de-dollarization" is real but misread. The dollar's reserve share *has*
eroded — **76% (2000) → 56%** — but the renminbi peaked at just **2.9% (2022) and fell
back to ~2%**, tripped by capital controls and the lesson of 2022's freezing of Russia's
reserves; what absorbed the decline was a **diffuse basket of small, safe currencies**
(rising ~3% → ~13%). The world is hedging away from the dollar and toward *nothing in
particular*. This is the one place the concentration spine runs backwards — the monetary
commons genuinely de-concentrated — **and yet the hub's power did not move an inch,
because that power was never the reserve share; it was the backstop. There is, as yet,
no second dollar — and no second lender of last resort.**

## The counterweight: what endures

If concentration is the spine, Chapter 12 is the vertebra that tests it — and the news
is that **great fortunes almost never last.** Peak family wealth, measured against home
GDP across five centuries, clusters in a narrow band: the Rothschild fortune peaked near
**3.0% of British GDP (1882)**, and Musk today commands ~**2.5% of US GDP** — the same
order of magnitude, 144 years apart. And the fortunes get *killed* — by states, by
partible inheritance, by war, by taxation — so reliably that what actually endures is
not wealth but **wealth-adjacent institutions**: the Kong lineage across ~80
generations, the Uffizi still paying its city dividends **590 years** on, the House of
Osman's 726-year run. Value that cannot be confiscated, inflated, or divided outlives
every balance sheet. Concentration is a structural tendency the system returns to — but
it is *bounded* and *impermanent*, which is the hopeful qualification the rest of the
report earns.

## The state of the world — July 2026 (computed live)

| Metric | Value | Context |
|---|---|---|
| World population | 8.30B | peaks 10.29B in 2084 (UN medium) |
| World median age | 31.1 yrs | 21.5 in 1980 → 36.1 by 2050 |
| World GDP | $126T | sum of 190 countries, current US$ |
| World real growth 2026 | 2.6%/yr | GDP-weighted |
| US inflation (CPI yoy) | 4.2% | above target four years running |
| Fed funds / 10-yr Treasury | 3.63% / 4.57% | curve re-steepened, +0.4pp |
| High-yield spread | 2.71pp | top-decile tightness |
| Fed balance sheet | $6.74T | down from $8.97T peak |
| S&P 500 / CAPE | 7,458 / 41.4 | 99th percentile of 145 years |
| US federal debt / GDP | 121% | above the 1946 war peak |
| US r−g | ≈ −1.3pp | debt melts — while growth holds |
| US top-1% wealth share | 31.6% | bottom 50%: 2.5% |
| Global top-10% income share | 53% | falling since 2000 |
| China share of world exports | 16% | #1 supplier to 96 countries |
| US-dollar share of FX reserves | 56% | ~76% in 2000; lost share went to a small-currency basket, not the RMB |
| World trade / GDP | 57% | 2008 peak was 60% |
| World primary energy | 177 PWh/yr | GDP intensity −42% since 1973 |

## What the report teaches

1. **Growth is a 200-year-old anomaly** that shifted its address — West (1820–1950),
   then East (1980–) — and now runs on productivity alone as population fades (Ch. 1, 4).
2. **Finance's stability is a policy regime, not a natural state** — zero crises under
   repression, 72%-breadth under liberalization — and **debt arithmetic (r−g) beats debt
   rhetoric**, deciding what budgets never do (Ch. 2, 3).
3. **Concentration is a structural tendency, not an episode.** From assets to land to
   the index vote, a few hold a lot — but the levers are fewer, and more often *public*
   (the FOMC) or *delegated* (the index stewards), than the mythology allows; and the
   spine runs *backwards* on the physical and monetary commons (Ch. 6–10).
4. **Control split off from ownership — and the machinery is built to ratify.** The
   deciding hand is rarely the owning one: the Big Three vote ~95% with management, the
   FOMC chair has carried all 130 meetings, and the swap line is switched on or off at US
   discretion (Ch. 10, 2).
5. **Influence is a market, and almost all of it is legal.** Wherever public power or
   public wealth pools — the tax code, a defense contract, a county commission, the
   mineral estate, a judge's docket — a channel evolves to convert it into private gain;
   the bigger and quieter the pool, the more developed the channel (Ch. 10).
6. **Markets are wounded by contagion and healed by the central bank** — the shock sets
   the depth, the Fed sets the duration, and there is no unconditional hedge, only
   shock-conditional ones (Ch. 3).
7. **War is net-destructive but selectively enriching** — it transfers wealth to whoever
   supplies weapons, oil, credit, and safe distance, and the arms trade is a five-nation
   chokepoint (Ch. 2).
8. **Distribution is chosen, and it reaches the kitchen table.** Same century, same
   technology: America's U-curve, Europe's L — and since 2000 the things made by people
   outran every wage, while a post-2008 debt regime made the poor borrow dear and the
   rich borrow cheap (Ch. 6, 8, 5).
9. **All money bends toward one hub, whose deepest lever is untouched** — the US deficit
   absorbs the world's savings, a third of the trail hides behind custody domiciles, and
   the Fed's discretionary backstop, not the reserve share, is the real power (Ch. 2, 5).
10. **Concentration is bounded and impermanent.** Great fortunes cluster near 1–3% of
    home GDP and are reliably killed by states, heirs, war, and tax; what endures is
    wealth-adjacent institutions, not wealth (Ch. 12).
11. **The world's tangible levers rotate — except money.** The dominant lever changes
    every 30–70 years (bullion → coal → oil → the dollar → capital markets → chips-and-
    sanctions), and each rotation re-ranks nations; but the money lever alone has never
    moved *against* the leading power, only with it, London to New York (Ch. 11).
12. **The 2026 configuration** — record-valuation markets, war-level debt, above-target
    inflation, fading demographics, plateaued trade, concentrated ownership, captured
    decision-points, and the fastest hegemonic supply-chain handover ever measured — is
    historically novel *as a combination*. The warehouse now watches it move.

*The apparatus (Phase 3) turns this report from a snapshot into an instrument: every
number above regenerates with one refresh.*
