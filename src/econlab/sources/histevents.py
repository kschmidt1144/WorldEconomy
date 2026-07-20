"""Curated catalog of market-moving historical events (for the event-study apparatus).

~90 high-impact events across six categories — war, pandemic, disaster, crash,
political, monetary — each with the market-relevant date it hit. Compiled and
date-verified for `analysis/events.py`, which measures each event's S&P 500
response. Curated from the historical record (dates are facts; flagged as curated).
"""

from __future__ import annotations

import pandas as pd

from ..catalog import Series
from ..config import TIDY

SOURCE = "histevents"
TITLE = "Curated catalog of market-moving historical events"

# (market-relevant date, name, category, note)
EVENTS = [
    ("1906-04-18", "San Francisco earthquake", "disaster", "Great 1906 quake and fire devastated San Francisco; huge insurance losses forced global gold shipments and helped trigger the 1907 panic."),
    ("1907-10-22", "Panic of 1907", "crash", "Knickerbocker Trust suspends operations after a run, triggering a nationwide banking panic that JPMorgan ultimately backstopped."),
    ("1914-07-28", "WWI outbreak", "war", "Austria-Hungary declares war on Serbia, triggering World War I; the NYSE closed July 31 for ~4 months (monthly data only)."),
    ("1918-10-01", "Spanish flu — deadly second wave", "pandemic", "Peak US mortality month of the 1918 H1N1 pandemic; pre-1927 monthly-data era, date anchors the autumn wave (approximate — no single trigger day)."),
    ("1923-09-04", "Great Kanto earthquake (Japan)", "disaster", "Sept 1 quake destroyed Tokyo/Yokohama; news reached US markets after the Labor Day weekend; massive reconstruction and reinsurance impact."),
    ("1927-04-21", "Great Mississippi Flood", "disaster", "Mounds Landing levee break inundated the Delta; the most destructive US river flood, hitting agriculture and infrastructure across the South."),
    ("1929-10-29", "Black Tuesday (1929 Crash)", "crash", "Record volume selloff (~-11%) capping the Great Crash and ushering in the Great Depression."),
    ("1930-06-17", "Smoot-Hawley Tariff Act signed", "political", "Hoover signs sweeping protectionist tariffs; triggered retaliation and deepened the global trade collapse."),
    ("1931-05-11", "Credit-Anstalt Collapse", "crash", "Austria's largest bank revealed insolvency, cascading into European bank runs and deepening the global Depression."),
    ("1931-09-21", "Britain abandons the gold standard", "monetary", "UK Gold Standard (Amendment) Act suspends sterling's gold convertibility, triggering a global scramble off gold."),
    ("1932-11-08", "FDR landslide election", "political", "Roosevelt defeats Hoover, ushering in the New Deal regulatory and fiscal regime shift."),
    ("1933-04-19", "FDR takes the US off gold", "monetary", "Roosevelt announces suspension of the gold standard and gold-export embargo; the dollar begins to float and depreciate."),
    ("1939-09-01", "Germany invades Poland", "war", "Nazi invasion of Poland launches World War II in Europe (a Friday)."),
    ("1940-05-10", "Germany invades France/Low Countries", "war", "Blitzkrieg into France, Belgium and the Netherlands; sharp global equity selloff as the phony war ends."),
    ("1941-12-07", "Pearl Harbor attack", "war", "Japanese surprise attack (a Sunday) brings the US into WWII; markets fell hard on Monday Dec 8."),
    ("1944-07-22", "Bretton Woods agreement", "monetary", "44-nation conference concludes, creating the dollar-gold peg system, IMF and World Bank."),
    ("1948-11-03", "Truman upsets Dewey", "political", "Surprise Democratic win against near-universal expectations; S&P fell roughly 3-4% the day results were known."),
    ("1950-06-25", "Korean War begins", "war", "North Korea invades South Korea (a Sunday); the S&P dropped ~5% on the following trading days."),
    ("1951-03-04", "Treasury-Fed Accord", "monetary", "Agreement frees the Fed from pegging Treasury yields, restoring independent monetary policy."),
    ("1957-10-01", "Asian flu (H2N2) — US fall wave", "pandemic", "Peak of the 1957 pandemic wave in the US, coincident with the sharp Aug–Oct 1957 market decline (month-anchored, no clean single-day trigger)."),
    ("1962-05-28", "Kennedy Slide (Flash Crash of 1962)", "crash", "DJIA fell ~6.7% in a single session amid the 'Kennedy Slide' selloff, one of the sharpest one-day drops of the postwar era."),
    ("1962-10-22", "Cuban Missile Crisis", "war", "JFK's televised address revealing Soviet missiles in Cuba, the peak of Cold War nuclear brinkmanship."),
    ("1963-11-22", "JFK assassination", "war", "President Kennedy shot in Dallas (a Friday); the NYSE halted trading and closed early."),
    ("1968-12-02", "Hong Kong flu (H3N2) — US wave", "pandemic", "Onset of the deadly US wave of the 1968 H3N2 pandemic (Dec 1968–Jan 1969); date approximate, no single trigger day."),
    ("1971-08-15", "Nixon closes the gold window", "monetary", "Sunday-evening TV address ends dollar-gold convertibility plus a 10% import surcharge, effectively ending Bretton Woods."),
    ("1973-10-06", "Yom Kippur War", "war", "Egypt and Syria attack Israel; the Arab oil embargo followed Oct 17, quadrupling oil prices and driving the 1973-74 bear market."),
    ("1973-10-17", "OPEC Oil Embargo", "crash", "Arab oil producers announced the embargo, quadrupling oil prices and helping drive the brutal 1973-74 bear market."),
    ("1974-08-08", "Nixon resignation announced", "political", "Watergate culmination; Nixon announces resignation in an evening televised address."),
    ("1979-03-28", "Three Mile Island accident", "disaster", "Partial meltdown at the Pennsylvania nuclear plant; halted US reactor expansion and hammered utility/nuclear-sector stocks."),
    ("1979-10-06", "Volcker's Saturday Night Special", "monetary", "Fed shifts to targeting money-supply growth and hikes the discount rate, launching the disinflation era."),
    ("1979-12-27", "Soviet invasion of Afghanistan", "war", "Soviet forces seize Kabul, spiking Cold War tensions and gold; contributed to the 1980 oil-price and inflation surge."),
    ("1980-11-04", "Reagan elected", "political", "Republican landslide launching supply-side tax cuts and deregulation; market rallied on the pro-business mandate."),
    ("1981-06-05", "AIDS first reported", "pandemic", "CDC's MMWR published the first report of what became AIDS ('Pneumocystis Pneumonia — Los Angeles'), marking HIV/AIDS emergence."),
    ("1984-12-03", "Bhopal gas disaster", "disaster", "Union Carbide plant leak in India killed thousands overnight; company shares plunged as news broke Monday, reshaping chemical-industry liability."),
    ("1985-09-22", "Plaza Accord", "monetary", "G5 agree at the Plaza Hotel to coordinated intervention to weaken the overvalued dollar."),
    ("1986-04-28", "Chernobyl disaster", "disaster", "Soviet nuclear reactor explosion revealed to the West after Sweden detected fallout; roiled agriculture, energy and uranium markets."),
    ("1987-10-19", "Black Monday 1987", "crash", "S&P 500 fell ~20.5% in one day, the largest single-day percentage loss in history, amplified by program trading."),
    ("1989-03-24", "Exxon Valdez oil spill", "disaster", "Tanker grounded in Prince William Sound, Alaska; largest US spill to date, driving Exxon liability costs and tighter shipping regulation."),
    ("1989-10-18", "Loma Prieta earthquake", "disaster", "Oct 17 (5:04pm PT) Bay Area quake during the World Series; market reaction hit the next session amid heavy insured losses."),
    ("1989-11-09", "Fall of the Berlin Wall", "political", "East Germany opens the border overnight, symbolizing the end of the Cold War order."),
    ("1990-08-02", "Iraq invades Kuwait", "war", "Saddam Hussein's invasion doubles oil prices and triggers a sharp equity selloff into the fall of 1990."),
    ("1991-01-17", "Operation Desert Storm", "war", "US-led air campaign to liberate Kuwait begins (evening Jan 16 ET); markets staged a large relief rally."),
    ("1992-08-24", "Hurricane Andrew", "disaster", "Category 5 landfall in South Florida; then the costliest US hurricane, bankrupting insurers and reshaping catastrophe reinsurance."),
    ("1992-09-16", "Black Wednesday", "monetary", "Sterling crashes out of the ERM after the BoE's failed defense against Soros and other speculators."),
    ("1996-12-05", "Greenspan 'irrational exuberance'", "monetary", "Evening AEI speech questioning asset valuations sends global equity markets sharply lower overnight."),
    ("1997-10-27", "1997 Asian Crisis Mini-Crash", "crash", "Contagion from the Asian financial crisis drove a ~7% DJIA drop that first triggered NYSE circuit breakers."),
    ("1998-08-17", "Russian Default / LTCM", "crash", "Russia defaulted and devalued the ruble, sparking the losses that toppled hedge fund LTCM and prompted a Fed-organized rescue."),
    ("2000-03-24", "Dot-Com Peak", "crash", "S&P 500 hit its closing high, marking the top before the multi-year dot-com/tech bust."),
    ("2001-09-11", "9/11 attacks", "war", "Al-Qaeda attacks on New York and Washington; the NYSE closed and reopened Sept 17 with a ~5% drop."),
    ("2003-03-12", "SARS — WHO global alert", "pandemic", "WHO issued its first global alert on the novel SARS coronavirus; a travel advisory followed March 15, hitting Asian travel/airline equities."),
    ("2003-03-20", "US invasion of Iraq", "war", "'Shock and awe' campaign begins (airstrikes Mar 19 evening ET); equities rallied on removal of uncertainty."),
    ("2004-12-27", "Indian Ocean earthquake and tsunami", "disaster", "Dec 26 megathrust quake and tsunami killed ~230,000 across Asia; markets first reacted the following Monday."),
    ("2005-08-29", "Hurricane Katrina", "disaster", "Category 3 Gulf Coast landfall flooded New Orleans; spiked oil/gas prices and became one of the costliest US natural disasters."),
    ("2008-09-15", "Lehman Brothers Bankruptcy", "crash", "Lehman's Chapter 11 filing, the largest in US history, ignited the acute phase of the global financial crisis."),
    ("2008-09-29", "TARP Rejection", "crash", "House voted down the $700B bailout, sending the DJIA down 777 points (S&P ~-8.8%), its worst point drop to that date."),
    ("2009-03-18", "Fed QE1 expanded to Treasuries", "monetary", "FOMC adds $300B long-term Treasury purchases; 10y yields post a record one-day drop and equities rally."),
    ("2009-04-27", "H1N1 swine flu — market reaction", "pandemic", "Monday selloff (S&P ~-1%, airlines/travel hit) after weekend WHO/CDC warnings; WHO raised the pandemic alert to phase 4 the same day."),
    ("2009-06-11", "WHO declares H1N1 pandemic", "pandemic", "WHO raised the alert to phase 6, its first declared pandemic since 1968."),
    ("2010-04-20", "Deepwater Horizon / BP spill", "disaster", "Gulf of Mexico rig explosion began the largest marine oil spill; BP and offshore-drilling shares collapsed over following weeks."),
    ("2010-05-06", "Flash Crash 2010", "crash", "Algorithmic selling briefly wiped ~9% off the DJIA intraday before a rapid partial recovery."),
    ("2010-08-27", "Bernanke Jackson Hole (QE2 signal)", "monetary", "Jackson Hole speech signaling further asset purchases sets up the QE2 rally in risk assets."),
    ("2011-03-11", "Tohoku earthquake / Fukushima", "disaster", "Magnitude-9 quake and tsunami hit Japan, triggering the Fukushima nuclear crisis; global auto/supply-chain and nuclear-sector shock."),
    ("2011-08-05", "S&P downgrades US credit / debt-ceiling crisis", "political", "First-ever US AAA downgrade announced Friday after close; S&P 500 fell ~6.7% the following Monday (Aug 8)."),
    ("2011-08-08", "US Credit Downgrade", "crash", "First trading day after S&P stripped the US of its AAA rating (announced Aug 5 after close); S&P 500 fell ~6.7%."),
    ("2012-07-26", "Draghi 'whatever it takes'", "monetary", "ECB chief's London pledge to preserve the euro collapses peripheral sovereign spreads."),
    ("2012-10-29", "Hurricane Sandy", "disaster", "Superstorm made landfall in New Jersey and flooded lower Manhattan; NYSE closed for two days, a rare weather shutdown."),
    ("2013-05-22", "Taper tantrum", "monetary", "Bernanke's congressional testimony hinting at slowing QE spikes Treasury yields and hits EM assets."),
    ("2014-02-27", "Russia annexes Crimea", "war", "Russian forces seize Crimea from Ukraine; risk-off move in European and emerging markets."),
    ("2014-08-08", "Ebola — WHO declares PHEIC", "pandemic", "WHO declared the West Africa Ebola outbreak a Public Health Emergency of International Concern."),
    ("2014-09-30", "First US Ebola case", "pandemic", "CDC confirmed the first Ebola case diagnosed on US soil (Dallas); fed the mid-October 2014 market selloff."),
    ("2015-01-15", "SNB removes euro floor", "monetary", "Swiss National Bank scraps the 1.20 franc cap, causing a ~30% intraday franc surge and FX chaos."),
    ("2015-08-24", "China Devaluation / Black Monday 2015", "crash", "Fallout from the Aug 11 yuan devaluation triggered a global rout; DJIA fell ~1,000 points intraday."),
    ("2015-12-16", "Fed liftoff", "monetary", "First rate hike since 2006, ending seven years at the zero lower bound."),
    ("2016-02-01", "Zika — WHO declares PHEIC", "pandemic", "WHO declared the Zika virus outbreak a Public Health Emergency of International Concern; pressured Latin American travel/tourism."),
    ("2016-06-24", "Brexit referendum result", "political", "UK votes Leave against polls/odds; global equity selloff and sterling collapse as results confirmed overnight."),
    ("2016-11-09", "Trump wins 2016 US election", "political", "Surprise victory; overnight futures plunged limit-down then reversed to a strong rally by the cash open."),
    ("2017-08-25", "Hurricane Harvey", "disaster", "Category 4 Texas landfall dumped record rainfall on Houston; knocked out Gulf refining capacity and spiked gasoline prices."),
    ("2017-12-22", "Tax Cuts and Jobs Act signed", "political", "Corporate tax rate cut from 35% to 21%; capstone of the 2017 pro-business fiscal package."),
    ("2018-03-22", "Trump signs China Section 301 tariffs", "political", "Formal launch of the US-China trade war; Dow fell 724 points (~2.9%) on the day."),
    ("2019-08-05", "US-China tariff/yuan escalation", "political", "After Trump's new tariff threat, China let the yuan break 7/USD; S&P 500 fell ~3%, worst day of 2019."),
    ("2020-02-24", "COVID-19 — US market-crash onset", "pandemic", "Monday plunge (S&P -3.4%) as the Italian/European outbreak spread over the weekend, ending the record run from the Feb 19 peak."),
    ("2020-03-11", "WHO declares COVID-19 a pandemic", "pandemic", "WHO formally declared COVID-19 a pandemic; same-day shocks (NBA suspension, travel bans) accelerated the crash."),
    ("2020-03-15", "Fed COVID emergency cut to zero", "monetary", "Sunday emergency action cuts rates to 0-0.25% and restarts $700B QE ahead of the market crash."),
    ("2020-03-16", "COVID-19 — worst single-day crash", "pandemic", "S&P 500 fell ~12%, its largest single-day drop since 1987, triggering a circuit breaker."),
    ("2020-03-16", "COVID-19 Crash", "crash", "S&P 500 fell ~12%, its worst day since 1987, as pandemic lockdowns froze the global economy."),
    ("2020-11-04", "Biden 2020 election (results emerge)", "political", "Day after Election Day; S&P rallied ~2% on prospects of divided government (race formally called Nov 7)."),
    ("2021-11-26", "Omicron variant — market drop", "pandemic", "Black Friday selloff (S&P -2.3%, Dow -905) as WHO named the Omicron variant; worst day of 2021."),
    ("2022-02-24", "Russia invades Ukraine", "war", "Full-scale invasion sends energy and commodity prices soaring and equities sharply lower globally."),
    ("2022-08-26", "Powell's hawkish Jackson Hole", "monetary", "Terse speech warning of 'pain' to fight inflation triggers a ~3.4% S&P 500 selloff."),
    ("2022-09-28", "Hurricane Ian", "disaster", "Category 4/5 landfall in southwest Florida; among the costliest US hurricanes, straining property insurers statewide."),
    ("2023-03-10", "SVB Collapse / Regional Bank Crisis", "crash", "FDIC seized Silicon Valley Bank, sparking regional-bank contagion that soon spread to Credit Suisse's UBS rescue."),
    ("2023-10-07", "Hamas attack on Israel", "war", "Large-scale Hamas assault (a Saturday) igniting the Gaza war; oil and defense stocks rose, broad risk-off Monday."),
    ("2024-11-06", "Trump wins 2024 US election", "political", "Decisive Republican victory called early Wednesday; S&P 500 jumped ~2.5% on deregulation/tax-cut expectations."),
]


def fetch(force: bool = False) -> None:
    pass  # curated in-module


def parse() -> tuple[list[Series], pd.DataFrame]:
    df = pd.DataFrame(EVENTS, columns=["date", "name", "category", "note"]).drop_duplicates(["date", "name"])
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "events.parquet", index=False)
    obs = pd.DataFrame({"series_id": "histevents/n_events", "entity": "WLD", "year": 2026, "value": [float(len(df))]})
    series_list = [Series(series_id="histevents/n_events", source=SOURCE,
        name="Catalogued market-moving historical events", unit="events", unit_type="count", frequency="A",
        description="Count of curated cross-category historical events in the event-study catalog.",
        license="Curated (historical record)", url="")]
    return series_list, obs
