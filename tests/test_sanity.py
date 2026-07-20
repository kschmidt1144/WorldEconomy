"""Sanity suite: the warehouse must reproduce known benchmark values.

Tolerances are deliberately generous — these catch unit blunders (thousands vs
persons, ratio vs percent), broken parses, and stale data, not revisions.
"""

from __future__ import annotations

import pytest

from econlab.catalog import UNIT_TYPES
from econlab.model import connect


@pytest.fixture(scope="session")
def con():
    c = connect(read_only=True)
    yield c
    c.close()


def one(con, sql: str, *params):
    return con.execute(sql, list(params)).fetchone()[0]


# ---------- schema integrity ----------

def test_no_orphan_series(con):
    n = one(
        con,
        "SELECT count(DISTINCT o.series_id) FROM obs o "
        "LEFT JOIN catalog c USING (series_id) WHERE c.series_id IS NULL",
    )
    assert n == 0


def test_unit_types_valid(con):
    bad = con.execute(
        f"SELECT DISTINCT unit_type FROM catalog WHERE unit_type NOT IN {tuple(UNIT_TYPES)}"
    ).fetchall()
    assert bad == []


def test_entities_cover_obs(con):
    n = one(
        con,
        "SELECT count(DISTINCT o.entity) FROM obs o "
        "LEFT JOIN entities e USING (entity) WHERE e.entity IS NULL",
    )
    assert n == 0


# ---------- benchmark values ----------

def test_us_nominal_gdp_2019(con):
    v = one(
        con,
        "SELECT value FROM obs WHERE series_id='wdi/NY.GDP.MKTP.CD' AND entity='USA' AND year=2019",
    )
    assert 20e12 < v < 23e12  # ~$21.4T


def test_world_population_2022(con):
    wdi = one(
        con, "SELECT value FROM obs WHERE series_id='wdi/SP.POP.TOTL' AND entity='WLD' AND year=2022"
    )
    assert 7.5e9 < wdi < 8.4e9  # ~7.95B
    # Maddison country sum should agree within a few percent
    mad = one(
        con,
        "SELECT sum(value) FROM obs o JOIN entities e USING (entity) "
        "WHERE series_id='maddison/pop' AND year=2022 AND e.kind='country'",
    )
    assert abs(mad - wdi) / wdi < 0.05


def test_maddison_us_gdppc_2018(con):
    v = one(
        con, "SELECT value FROM obs WHERE series_id='maddison/gdppc' AND entity='USA' AND year=2018"
    )
    assert 45_000 < v < 65_000  # ~55k in 2011 PPP$


def test_maddison_reaches_year_one(con):
    v = one(con, "SELECT min(year) FROM obs WHERE series_id='maddison/gdppc'")
    assert v == 1


def test_shiller_cape_dec_1999(con):
    v = one(con, "SELECT value FROM obs WHERE series_id='shiller/cape' AND date='1999-12-31'")
    assert 40 < v < 48  # 44.2, the dot-com peak


def test_shiller_is_current(con):
    v = one(con, "SELECT max(year) FROM obs WHERE series_id='shiller/sp_price'")
    assert v >= 2026


def test_jst_panel_shape(con):
    n = one(con, "SELECT count(DISTINCT entity) FROM obs WHERE series_id LIKE 'jst/%'")
    assert n == 18


def test_jst_us_crises_canonical(con):
    years = {
        r[0]
        for r in con.execute(
            "SELECT year FROM obs WHERE series_id='jst/crisisJST' AND entity='USA' AND value=1"
        ).fetchall()
    }
    assert {1893, 1907, 1930, 2007} <= years


def test_jst_us_debtgdp_is_ratio_scale(con):
    v = one(
        con, "SELECT value FROM obs WHERE series_id='jst/debtgdp' AND entity='USA' AND year=2019"
    )
    assert 0.5 < v < 2.0  # a fraction, not percent — guards double-scaling


def test_dfa_top1_wealth_share_2019q4(con):
    v = one(
        con,
        "SELECT sum(value) FROM obs WHERE date='2019-12-31' AND series_id IN "
        "('dfa/nwshare.net_worth.toppt1','dfa/nwshare.net_worth.remainingtop1')",
    )
    assert 27 < v < 35  # ~31% of US household net worth held by top 1%


def test_fiscaldata_first_and_current(con):
    v1790 = one(
        con, "SELECT value FROM obs WHERE series_id='fiscaldata/debt_outstanding' AND year=1790"
    )
    assert 70e6 < v1790 < 72e6  # $71,060,508.50
    latest = one(con, "SELECT max(year) FROM obs WHERE series_id='fiscaldata/debt_outstanding'")
    assert latest >= 2025


def test_wdi_is_current(con):
    v = one(con, "SELECT max(year) FROM obs WHERE series_id LIKE 'wdi/%'")
    assert v >= 2024


def test_world_aggregation_matches_maddison_reference(con):
    """From 1950 (near-complete country coverage) our bottom-up world GDP must
    track Maddison's own aggregate. Pre-1950 our sum is a documented lower
    bound (colonial-era economies enter the panel at 1950), so not tested."""
    from econlab.analysis.maddison_world import maddison_world_reference, world_gdp_annual

    ours = world_gdp_annual().set_index("year")["gdp"]
    ref = maddison_world_reference().set_index("year")["gdp"]
    for y in (1950, 1970, 2000, 2019):
        assert abs(ours[y] - ref[y]) / ref[y] < 0.06, f"{y}: ours={ours[y]:.3g} ref={ref[y]:.3g}"


def test_successor_partition_no_double_count(con):
    """After partition, a composite (USSR…) and its successors never coexist
    in the same year, and population is continuous across each handoff."""
    from econlab.analysis.maddison_world import SUCCESSORS, load_panel, successor_partition

    panel = successor_partition(load_panel())
    years = panel.groupby("entity")["year"].apply(set)

    for comp, succs in SUCCESSORS.items():
        if comp not in years.index:
            continue
        comp_years = years[comp]
        handoff = None
        for s in succs:
            if s in years.index:
                overlap = comp_years & years[s]
                assert not overlap, f"{comp}/{s} both counted in {sorted(overlap)[:3]}"
                first = min(years[s])
                handoff = first if handoff is None else max(handoff, first)
        # boundary continuity: composite pop just before ~= successor sum just after
        before = panel.loc[(panel.entity == comp) & (panel.year == handoff - 1), "pop"].sum()
        after = panel.loc[
            panel.entity.isin(succs) & (panel.year == handoff), "pop"
        ].sum()
        if before and after:
            assert abs(after - before) / before < 0.05, f"{comp} handoff jump {before}->{after}"


def test_wdi_breadth(con):
    n_series = one(con, "SELECT count(*) FROM catalog WHERE source='wdi'")
    assert n_series > 1_000
    n_obs = one(con, "SELECT count(*) FROM obs WHERE series_id LIKE 'wdi/%'")
    assert n_obs > 5_000_000


# ---------- Phase 1 sources ----------

def test_imf_us_debt_and_gdp(con):
    debt = one(
        con, "SELECT value FROM obs WHERE series_id='imf/GGXWDG_NGDP' AND entity='USA' AND year=2024"
    )
    assert 110 < debt < 130  # ~121% of GDP
    gdp = one(
        con, "SELECT value FROM obs WHERE series_id='imf/NGDPD' AND entity='USA' AND year=2025"
    )
    assert 28e12 < gdp < 33e12  # ~$30T (scale-normalization guard)


def test_imf_projections_present(con):
    v = one(con, "SELECT max(year) FROM obs WHERE series_id='imf/NGDP_RPCH'")
    assert v >= 2029


def test_pwt_us_labor_share(con):
    v = one(con, "SELECT value FROM obs WHERE series_id='pwt/labsh' AND entity='USA' AND year=2019")
    assert 0.55 < v < 0.65  # ~0.60 — guards ratio-vs-percent scaling


def test_unwpp_world_population_now_and_2100(con):
    now = one(
        con,
        "SELECT value FROM obs WHERE series_id='unwpp/TPopulation1July' AND entity='WLD' AND year=2024",
    )
    assert 7.9e9 < now < 8.4e9  # thousands->persons normalization guard
    end = one(
        con,
        "SELECT value FROM obs WHERE series_id='unwpp/TPopulation1July' AND entity='WLD' AND year=2100",
    )
    assert 9.0e9 < end < 11.5e9  # UN medium variant ~10.2B


def test_energy_world_primary_consumption(con):
    v = one(
        con,
        "SELECT value FROM obs WHERE series_id='energy/primary_energy_consumption' "
        "AND entity='WLD' AND year=2023",
    )
    assert 150_000 < v < 200_000  # ~172k TWh


def test_edgar_apple_revenue_2023(con):
    v = one(
        con, "SELECT value FROM obs WHERE series_id='edgar/revenues' AND entity='$AAPL' AND year=2023"
    )
    assert 350e9 < v < 420e9  # ~$383B


def test_edgar_no_future_fiscal_years(con):
    v = one(con, "SELECT max(year) FROM obs WHERE series_id LIKE 'edgar/%'")
    assert v <= 2027


def test_company_ticker_namespace_isolated(con):
    """Every company entity is $-prefixed; ISO3 space stays for countries
    (ticker SUN must never shadow the former USSR again)."""
    n = one(con, "SELECT count(*) FROM entities WHERE kind='company' AND entity NOT LIKE '$%'")
    assert n == 0
    kind = one(con, "SELECT kind FROM entities WHERE entity='SUN'")
    assert kind == "historical"


def test_wid_us_top1_income_share(con):
    v = one(
        con,
        "SELECT value FROM obs WHERE series_id='wid/sptincj992.p99p100' AND entity='USA' AND year=2022",
    )
    assert 0.15 < v < 0.25  # ~0.20 as a fraction — guards percent-vs-fraction


def test_pinksheet_commodities(con):
    # basket present, long, and sanely scaled
    n_series = one(con, "SELECT count(DISTINCT series_id) FROM catalog WHERE source='pinksheet'")
    assert n_series >= 12
    oil_1960 = one(con, "SELECT value FROM obs WHERE series_id='pinksheet/oil' AND year=1960 ORDER BY date LIMIT 1")
    assert 1 < oil_1960 < 3          # ~$1.63/bbl in 1960 (guards scale)
    oil_2008 = one(con, "SELECT max(value) FROM obs WHERE series_id='pinksheet/oil' AND year=2008")
    assert oil_2008 > 90             # 2008 spike ~$133


def test_ch8_commodity_supercycles(con):
    from econlab.analysis.ch04_structure import commodity_real_index

    ci = commodity_real_index()
    # flat-to-falling real trend: 2025 basket ends near the 1960=100 base
    assert 70 < ci["basket"].iloc[-1] < 130
    # the 1999 real low and the 2011 China peak
    assert ci.loc[1999, "basket"] < 75
    assert ci.loc[2011, "basket"] > ci.loc[1999, "basket"] * 1.5
    # real oil quadrupled-plus in the 1970s
    assert ci.loc[1980, "oil"] > 500


def test_bls_cpi_items(con):
    # the story-critical items FRED lacks, fetched from BLS
    for slug in ("childcare", "televisions", "physicians"):
        n = one(con, "SELECT count(*) FROM obs WHERE series_id=?", f"bls/{slug}")
        assert n > 100, slug


def test_ch9_price_divergence(con):
    from econlab.analysis.ch08_cost import price_divergence

    d = price_divergence().iloc[-1]  # 2024, indexed to 2000=100
    assert d["Televisions"] < 15            # collapsed ~98%
    assert d["Software"] < 30
    assert d["Hospital services"] > 250     # soared
    assert d["Childcare"] > 180
    # the divide: services above wages, manufactured goods below
    assert d["Hospital services"] > d["Wages"] > d["Toys"]
    assert d["Apparel"] < 130               # apparel ~flat in dollars


def test_ch9_wage_quartiles(con):
    from econlab.analysis.ch08_cost import wage_quartiles, real_price_index

    nom = wage_quartiles().iloc[-1]          # 2024, 2000=100 nominal
    # U-shape: median grew slowest, top and bottom faster
    assert nom["Median"] < nom["10th"] and nom["Median"] < nom["90th"]
    assert nom["90th"] > 220                 # top decile ~228
    real = wage_quartiles(real=True).iloc[-1]
    assert (real > 100).all()                # every percentile gained real ground
    assert real["90th"] > real["Median"]     # top gained most
    # nobody kept up with care: top decile real gain < real childcare/college/hospital
    childcare_real = real_price_index("bls/childcare").iloc[-1]
    hospital_real = real_price_index("fred/CUUR0000SEMD").iloc[-1]
    assert real["90th"] < childcare_real < hospital_real


def test_ch9_groceries_vs_wages(con):
    from econlab.analysis.ch08_cost import necessities_vs_wages

    n = necessities_vs_wages().dropna().iloc[-1]  # 1970=100
    assert n["Groceries (food at home)"] < n["Wages"]   # food got cheaper in work-hours


def test_ch9_housing_squeeze(con):
    from econlab.analysis.ch08_cost import housing_view

    h = housing_view()
    assert h["real_price"].iloc[-1] > 1.6 * h["real_price"].iloc[0]   # real price ~doubled
    assert 4.0 < h["p2i"].iloc[-1] < 6.5                              # price-to-income ~5


def test_ch9_inflation_inequality(con):
    from econlab.analysis.ch08_cost import inflation_by_income

    inf = inflation_by_income()
    cum_low = (1 + inf.low_income / 100).prod()
    cum_high = (1 + inf.high_income / 100).prod()
    assert cum_low > cum_high            # the poor's basket inflated more
    assert inf.gap.mean() > 0            # persistently, not just once


def test_ch1_takeoff_diffusion(con):
    from econlab.analysis.ch01_longarc import takeoff_dates

    td = takeoff_dates().set_index("entity")["takeoff"]
    assert td["NLD"] < 1600 and td["GBR"] < 1800     # the first modern economies
    assert td["JPN"] < td["CHN"] < td["IND"]         # the orderly Asian diffusion
    assert td["GHA"] > 2000                          # Africa last
    assert td.max() - td.min() > 400                 # five centuries of diffusion


def test_ch6_bank_concentration(con):
    from econlab.analysis.ch09_power import bank_concentration

    bc = bank_concentration()
    share = bc["top5_sum"] / bc["all_banks"]
    assert 0.45 < share < 0.65          # top-5 hold ~54% of US bank assets
    assert bc["detail"]["$JPM"] > 3e12  # JPMorgan the largest


def test_ch6_bank_consolidation(con):
    from econlab.analysis.ch09_power import bank_count

    bc = bank_count()
    assert bc["anchors"].max() > 29000        # ~30,500 unit-bank peak (1921)
    assert bc["anchors"].idxmax() == 1921
    assert bc["usnum"].loc[1984] > 13000      # FRED USNUM starts ~14,400
    assert bc["current"] < 6000               # consolidated to ~4,300 today


def test_ch6_great_shift(con):
    from econlab.analysis.ch09_power import the_great_shift

    sh = the_great_shift()
    mf = sh["Mutual funds"].dropna()
    assert mf.loc[1950] < 3 and mf.iloc[-1] > 60      # 1% -> ~77% of GDP
    banks = sh["Banks (depository)"].dropna()
    assert 55 < banks.iloc[-1] < 90                    # banks roughly flat, not exploding
    assert mf.iloc[-1] > banks.iloc[-1] * 0.9          # funds now rival banks


def test_ch6_evolution_curated(con):
    from econlab.analysis.ch09_power import CB_COUNT, NEW_TITANS, HEDGE_FUND_AUM

    assert CB_COUNT[1668] == 1 and CB_COUNT[2024] > 150   # central banking: 1 -> universal
    assert max(NEW_TITANS, key=NEW_TITANS.get) == "BlackRock"
    assert HEDGE_FUND_AUM[2024] / HEDGE_FUND_AUM[1990] > 50  # ~115x since 1990


def test_ch10_chokepoints(con):
    from econlab.analysis.ch10_chokepoints import PANEL_CHECK, chokepoints_df

    df = chokepoints_df()
    assert len(df) >= 12
    # the purest monopoly: one firm, 100%, AI panel corroborated
    asml = df[df.who == "ASML"].iloc[0]
    assert asml.n == 1 and asml.share == 100
    # every chokepoint is 1-4 controllers commanding a majority
    assert (df.n <= 4).all() and (df.share >= 55).all()
    # the panel flagged TSMC as contested (definition-sensitive) but not ASML
    assert PANEL_CHECK["EUV lithography machines"][0] >= 95
    assert PANEL_CHECK["Leading-edge chips (<7nm)"][0] < 85


def test_ch10_dual_class_and_pools(con):
    from econlab.analysis.ch10_chokepoints import CAPITAL_POOLS, DUAL_CLASS, the_controllers

    # control without ownership: voting >> economic for every dual-class case
    assert all(voting > econ for _, voting, econ in DUAL_CLASS)
    zuck = next(d for d in DUAL_CLASS if "Zuckerberg" in d[0])
    assert zuck[1] > 50 and zuck[2] < 20        # majority votes on a minority stake
    # the Big Three manage more than the sovereign funds combined
    aum = {k: v for _, k, v in [(n, k, v) for n, k, v in CAPITAL_POOLS]}
    big3 = sum(v for _, k, v in CAPITAL_POOLS if k == "asset mgr")
    swf = sum(v for _, k, v in CAPITAL_POOLS if k == "SWF")
    assert big3 > swf * 2
    # the controllers are real people from the billionaires table
    assert len(the_controllers()) >= 8


def test_ch10_hidden_hands_and_13f(con):
    from econlab.analysis.ch10_chokepoints import BIG3_OWNERSHIP, HIDDEN_HANDS

    # the 13F-computed Big Three ownership: ~a fifth of every mega-cap
    vals = list(BIG3_OWNERSHIP.values())
    assert all(12 < v < 25 for v in vals)
    assert 15 < sum(vals) / len(vals) < 21          # ~18% average
    assert BIG3_OWNERSHIP["Nvidia"] > BIG3_OWNERSHIP["JPMorgan"]
    # the roster names the obscure deciders, not the famous founders
    names = " ".join(h[0] for h in HIDDEN_HANDS)
    for who in ("Abdel Majeid", "Galloway", "Colton", "Tangen", "Retelny", "La Salla"):
        assert who in names
    assert "Musk" not in names and "Zuckerberg" not in names
    # the stewardship heads direct trillions of equity votes
    stewards = [h for h in HIDDEN_HANDS if h[4] is not None]
    assert sum(h[4] for h in stewards) > 12         # ~$14T+ of votable equity


def test_ch10_elite_network(con):
    from econlab.analysis.ch10_chokepoints import BRIDGERS, ELITE_VENUES, VENUE_EDGES

    venues = {v[0] for v in ELITE_VENUES}
    for v in ("Business Roundtable", "Council on Foreign Relations", "Trilateral Commission", "Bilderberg"):
        assert v in venues
    # every documented overlap edge connects two real venues
    for a, b, _ in VENUE_EDGES:
        assert a in venues and b in venues
    assert len(BRIDGERS) >= 3                        # people who bridge several venues


def test_ch10_conference_impact(con):
    from econlab.analysis.ch10_chokepoints import jackson_hole_effect

    e = jackson_hole_effect()
    # the Fed's symposium moves markets more than a normal day; Davos moves less
    assert e["jh_absmean"] > e["base_absmean"] * 1.2
    assert e["davos_absmean"] < e["base_absmean"]
    # 2022's "pain" speech was a big down day
    assert e["jh"][2022] < -2.5


def test_ch10_npx_votes(con):
    from econlab.analysis.ch10_chokepoints import npx_voting

    r = npx_voting()
    mgr = r["managers"]
    assert len(mgr) == 3                              # all three managers computed
    # every one sides with management ~90-97% (the "own a quarter, vote with mgmt" finding)
    assert (mgr["pct"].between(88, 99)).all()
    assert mgr["votes"].sum() > 50_000               # tens of thousands of real votes
    cats = dict(zip(r["categories"]["category"], r["categories"]["pct"]))
    assert cats["DIRECTOR ELECTIONS"] > 90           # the routine ballot is rubber-stamped


def test_ch10_board_interlocks(con):
    from econlab.analysis.ch10_chokepoints import board_interlocks

    r = board_interlocks(500)
    assert r["n_dir"] > 2000                      # thousands of large-cap directors captured
    # a real but THIN network: a minority interlock, and no mid-century-style hubs
    assert 5 < r["pct"] < 30
    assert r["busiest"] <= 12
    assert r["n_inter"] >= 100                     # interlocks exist, just sparse


def test_ch10_fomc_dissents(con):
    from econlab.analysis.ch10_chokepoints import fomc_dissent_record

    r = fomc_dissent_record()
    assert r["meetings"] >= 120                       # parsed the modern statement era
    assert 40 <= r["dissents"] <= 120                 # dissents happen, but are rare
    # the chair's action carried every meeting: dissents/meeting well below a majority
    assert r["dissents"] / r["meetings"] < 1.0
    # Esther George (KC Fed hawk) is the most frequent dissenter of the era
    assert r["top"].iloc[0]["member"] == "George"


def test_ch05_custody_bloc(con):
    from econlab.analysis.ch05_debt import CUSTODY_CENTERS, who_finances_america

    r = who_finances_america()
    # roughly a third of foreign holdings sit behind six custodian jurisdictions
    assert 25 < r["bloc_share"] < 40
    assert r["bloc_total"] > r["china"] * 3          # the bloc dwarfs China's stake
    # each custody jurisdiction is a real top holder in the snapshot
    held = set(r["top"]["entity"])
    assert set(CUSTODY_CENTERS).issubset(held)


def test_ch10_concentration_dashboard(con):
    from econlab.analysis.ch10_chokepoints import concentration_dashboard

    d = {s["title"]: s for s in concentration_dashboard()}
    # the whole point: concentration is NOT rising everywhere — opposite signs
    assert any(s["rose"] is True for s in d.values())
    assert any(s["rose"] is False for s in d.values())
    # ownership/control rose...
    assert d["US top-1% wealth share"]["end"] > d["US top-1% wealth share"]["start"]
    assert d["US listed companies"]["end"] < d["US listed companies"]["start"] / 1.5  # market halved-ish
    # ...while the commons de-concentrated
    assert d["US-dollar share of FX reserves"]["end"] < d["US-dollar share of FX reserves"]["start"]
    assert d["Top-4 oil producers' share"]["end"] < d["Top-4 oil producers' share"]["start"]


def test_ch10_big3_computed_ownership(con):
    from econlab.analysis.ch10_chokepoints import BIG3_OWNERSHIP, big3_computed_ownership

    df = big3_computed_ownership(500)
    # a real, broad computation — not eight constants
    assert len(df) >= 400
    med = df["big3_pct"].median()
    assert 20 < med < 30                              # broad large-cap median ~25%
    assert (df["big3_pct"] >= 20).mean() > 0.6        # most large caps are >=20% owned
    # structural three-way split: Vanguard now the largest, State Street smallest
    assert df["van_pct"].mean() > df["blk_pct"].mean() > df["ssga_pct"].mean()
    # the computed mega-cap stakes clear (or beat) the hand-entered snapshot
    lut = {r.ticker: r.big3_pct for r in df.itertuples()}
    assert lut["$AAPL"] >= BIG3_OWNERSHIP["Apple"]
    assert lut["$JPM"] >= BIG3_OWNERSHIP["JPMorgan"]


def test_ch10_fomc_multi_asset(con):
    from econlab.analysis.ch10_chokepoints import fomc_reaction

    r = fomc_reaction()
    # one FOMC decision moves stocks, rates, and volatility all more than a normal day
    for asset in ("S&P 500", "2yr yield", "VIX"):
        assert r[asset]["ratio"] > 1.2
    assert r["2yr yield"]["ratio"] > r["10yr yield"]["ratio"]   # short end most Fed-sensitive


def test_ch6_who_decides(con):
    from econlab.analysis.ch09_power import BIG3_SP500_STAKE, finance_founders

    # the Giant Three's ownership of the S&P 500 roughly quadrupled since 1998
    assert BIG3_SP500_STAKE[2024] > 3.5 * BIG3_SP500_STAKE[1998]
    assert BIG3_SP500_STAKE[2024] > 20                      # ~22% of the average firm
    # founder-owners: hedge-fund/PE billionaires, computed from the table
    fo = finance_founders(8)
    assert len(fo) == 8 and fo.iloc[0]["wealth_bn"] > 40    # Griffin ~$52B leads
    assert fo["wealth_bn"].is_monotonic_decreasing


def test_ch4_sovereign_defaults(con):
    from econlab.analysis.ch05_debt import sovereign_default_ledger, crisis_clock, NEVER_DEFAULTED

    led = sovereign_default_ledger()
    assert led.index[0] == "Spain" and led.iloc[0] >= 12   # Spain the champion
    assert "United States" in NEVER_DEFAULTED and "England/UK" in NEVER_DEFAULTED
    clock = crisis_clock()
    # crisis returned in the 2000s after the quiet Bretton-Woods decades
    assert clock.loc[1950, "crisis_country_yrs"] < 1
    assert clock.loc[2000, "crisis_country_yrs"] > 5


def test_cofer_reserve_shares(con):
    # dollar dominance, eroding: ~71% (1999) -> ~56% (2025)
    usd99 = one(con, "SELECT value FROM obs WHERE series_id='cofer/reserve_share.USD' AND year=1999")
    usd25 = one(con, "SELECT value FROM obs WHERE series_id='cofer/reserve_share.USD' AND year=2025")
    assert 68 < usd99 < 76 and 52 < usd25 < 62 and usd25 < usd99
    # shares of allocated reserves sum to ~100% in a recent year
    tot = one(con, "SELECT sum(value) FROM obs WHERE series_id LIKE 'cofer/reserve_share.%' AND year=2024")
    assert 97 < tot < 103
    # the renminbi never arrived
    cny = one(con, "SELECT value FROM obs WHERE series_id='cofer/reserve_share.CNY' AND year=2025")
    assert cny < 4


def test_ch2_global_imbalances(con):
    from econlab.analysis.ch02_nations import global_imbalances

    ca = global_imbalances(2024)
    assert ca.min() < -900          # US deficit ~ -$1.17tn
    assert ca.idxmin() == "USA"
    assert ca.max() > 300           # China surplus ~ +$417bn
    assert ca.idxmax() == "CHN"


def test_ch2_convergence_ladder(con):
    from econlab.analysis.ch02_nations import convergence_ladder

    cl = convergence_ladder()
    assert cl.loc[1913, "ARG"] > 50         # Argentina 1913: ~60% of US
    assert cl.loc[2022, "ARG"] < 40         # fell to ~31%
    assert cl.loc[2022, "KOR"] > 60         # Korea climbed to ~71%
    assert cl.loc[1960, "KOR"] < 20         # from ~10%


def test_ch3_crash_catalog(con):
    from econlab.analysis.ch03_money import crash_catalog

    cat = crash_catalog()
    assert len(cat) >= 10                       # ~12 real drawdowns >=20% since 1871
    worst = cat.iloc[0]
    assert worst["depth_pct"] < -75             # 1929 crash ~ -81% real
    assert str(worst["peak"])[:4] == "1929"
    assert worst["recover_yrs"] > 20            # a quarter-century underwater
    # 1968-82 Great Inflation is a real crash the nominal view hides
    inflation_crash = cat[cat["peak"].astype(str).str[:4].isin(["1968", "1969", "1972", "1973"])]
    assert (inflation_crash["depth_pct"] < -50).any()


def test_ch3_long_rates_arc(con):
    from econlab.analysis.ch03_money import long_rates

    lr = long_rates()
    assert lr.loc[1703, "UK consol"] > 5        # ~6% in 1703
    assert lr.loc[1900, "UK consol"] < 3.5      # ~2.6% by 1900
    peak = lr.loc[1975:1985].max().max()
    assert peak > 12                            # Volcker-era ~14%, the great exception


def test_ch3_yield_curve_inversions(con):
    # every inversion trough is below zero; series is current
    lo = one(con, "SELECT min(value) FROM obs WHERE series_id='fred/T10Y2Y'")
    assert lo < -1                              # 1980/2023 inversions well below zero
    latest = one(con, "SELECT max(date) FROM obs WHERE series_id='fred/T10Y2Y'")
    assert str(latest) >= "2026-06-01"


def test_ch5_wealth_composition_gradient(con):
    from econlab.analysis.ch06_wealth import wealth_composition

    comp = wealth_composition()
    # the engine: real estate falls, equities rise, monotonically bottom->top
    re = comp.loc["Real estate"]
    eq = comp.loc["Equities & funds"]
    assert re["Bottom 50%"] > 40 and re["Top 0.1%"] < 15
    assert eq["Top 0.1%"] > 45 and eq["Bottom 50%"] < 12
    assert list(re) == sorted(re, reverse=True)     # real estate strictly falls
    assert list(eq) == sorted(eq)                   # equities strictly rise


def test_ch5_billionaires_shape(con):
    n = one(con, "SELECT count(*) FROM billionaires")
    assert n > 3000
    top_country = con.execute(
        "SELECT country FROM billionaires GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
    ).fetchone()[0]
    assert top_country == "United States"
    total_t = one(con, "SELECT sum(worth_usd)/1e12 FROM billionaires")
    assert 12 < total_t < 30  # ~$20T of billionaire wealth
    top10_share = one(
        con, "SELECT 100.0*sum(CASE WHEN rank<=10 THEN worth_usd END)/sum(worth_usd) FROM billionaires"
    )
    assert 8 < top10_share < 25  # power-law concentration even within the list


def test_ch5_extreme_poverty_collapse(con):
    world = con.execute(
        "SELECT year, value FROM obs WHERE series_id='wdi/SI.POV.DDAY' AND entity='WLD' "
        "AND year IN (1981, 2024) ORDER BY year"
    ).df().set_index("year")["value"]
    assert world[1981] > 40 and world[2024] < 15   # ~47% -> ~10%
    eap_last = one(
        con, "SELECT value FROM obs WHERE series_id='wdi/SI.POV.DDAY' AND entity='EAS' "
        "ORDER BY year DESC LIMIT 1"
    )
    assert eap_last < 6  # East Asia's near-eradication


def test_baci_world_exports_2023(con):
    v = one(
        con, "SELECT sum(value) FROM obs WHERE series_id='baci/exports_total' AND year=2023"
    )
    assert 15e12 < v < 30e12  # world goods exports ~$23T (thousand-USD guard)


def test_trade_table_bilateral(con):
    n = one(con, "SELECT count(*) FROM trade")
    assert n > 500_000
    us_to_chn = one(
        con, "SELECT value_usd FROM trade WHERE exporter='USA' AND importer='CHN' AND year=2023"
    )
    assert 80e9 < us_to_chn < 250e9  # ~$145B


def test_fred_current_and_scaled(con):
    y = one(con, "SELECT max(year) FROM obs WHERE series_id='fred/CPIAUCSL'")
    assert y >= 2026  # data currency
    walcl = one(
        con, "SELECT max_by(value, date) FROM obs WHERE series_id='fred/WALCL'"
    )
    assert 4e12 < walcl < 9e12  # Fed balance sheet ~$6.7T — guards millions-scale slip
    dgs10 = one(con, "SELECT max_by(value, date) FROM obs WHERE series_id='fred/DGS10'")
    assert 1 < dgs10 < 9


def test_markets_current_and_sane(con):
    latest, close = con.execute(
        "SELECT date, value FROM obs WHERE series_id='markets/spx' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    assert str(latest) >= "2026-07-01"  # data is current
    assert 3_000 < close < 12_000


# ---------- Chapter 1: The Long Arc ----------

def test_ch1_bloc_shares(con):
    from econlab.analysis.ch01_longarc import bloc_shares_annual

    s = bloc_shares_annual()
    chn_ind = s["China"] + s["India"]
    west = s["Western Europe"] + s["Western Offshoots"]
    assert 40 < chn_ind[1820] < 50      # ~45.3%
    assert 7 < chn_ind[1950] < 12       # ~9.4% — the trough
    assert 25 < chn_ind[2022] < 33      # ~28.8% — the return
    assert 55 < west[1913] < 64         # ~59.2%
    assert west[1913] > west[1950]      # the West peaked before WWI, not in 1950


def test_ch1_golden_age_is_the_record(con):
    from econlab.analysis.ch01_longarc import growth_eras

    eras = growth_eras()
    assert eras["1950-1973"] == eras.max()
    assert 2.5 < eras["1950-1973"] < 3.1   # ~2.79 %/yr
    assert eras["1-1820"] < 0.05           # eighteen centuries of ~nothing
    assert eras["2000-2022"] > eras["1973-2000"]  # the China-era silver medal


def test_ch1_convergence_began_around_2000(con):
    from econlab.analysis.ch01_longarc import rolling_growth_gap

    gap = rolling_growth_gap().set_index("start")["gap"]
    assert gap[1985] < -1.0   # divergence at its worst
    assert gap[1990] < -1.0
    assert gap[2000] > 0.3    # the flip
    assert gap[2005] > 0.5


def test_ch1_two_sigmas_tell_different_stories(con):
    from econlab.analysis.ch01_longarc import sigma_paths

    sig = sigma_paths()
    assert sig.loc[2022, "unweighted"] > sig.loc[1950, "unweighted"]  # countries diverged
    assert sig.loc[2022, "pop_weighted"] < sig.loc[1980, "pop_weighted"]  # people converged


# ---------- Chapter 2: Nations & macro ----------

def test_ch2_inflation_regimes(con):
    from econlab.analysis.ch02_nations import inflation_regimes, worst_inflation_episodes

    reg = inflation_regimes()
    assert 65 < reg.loc[1980, "gt10"] < 85    # ~74% of countries above 10% in 1980
    assert reg.loc[2010, "gt10"] < 12         # the great disinflation
    assert reg.loc[2022, "gt10"] > 25         # the relapse
    worst = worst_inflation_episodes(1)
    assert worst.loc[0, "entity"] == "VEN" and worst.loc[0, "value"] > 10_000


def test_ch2_debt_ratchet(con):
    from econlab.analysis.ch02_nations import debt_distribution

    d = debt_distribution()
    hi = d[d.grp == "High income"].set_index("year")
    assert hi.loc[2020, "med"] > hi.loc[2007, "med"] + 10  # the post-2008 ratchet
    assert 45 < hi.loc[2024, "med"] < 70


def test_ch2_r_minus_g_regimes(con):
    from econlab.analysis.ch02_nations import us_r_minus_g

    rg = us_r_minus_g()["rg"]
    assert rg.loc[1946:1980].mean() < -1.5    # financial repression
    assert rg.loc[1981:2000].mean() > 1.0     # the Volcker regime
    assert rg.loc[2024] < 0                   # today: g above r again


# ---------- Chapter 3: Money & markets ----------

def test_ch3_return_on_everything(con):
    from econlab.analysis.ch03_money import pooled_real_returns

    pooled, _ = pooled_real_returns()
    m = pooled["mean"]
    assert 6 < m["Equities"] < 8 and 6 < m["Housing"] < 8      # both ~6.9
    assert 1.5 < m["Gov. bonds"] < 3.5 and 0.2 < m["Bills"] < 1.8
    assert m["Equities"] > m["Gov. bonds"] + 3                  # the risk premium


def test_ch3_cape_predicts_decade(con):
    from econlab.analysis.ch03_money import cape_forward

    df, slope, intercept, current = cape_forward()
    assert -0.5 < slope < -0.25            # ~-0.38 per CAPE point
    assert 35 < current < 50               # July 2026 ~41.4
    assert intercept + slope * current < 1  # implied decade: ~nothing, or less
    percentile = (df.cape < current).mean()
    assert percentile > 0.95


def test_ch3_credit_booms_precede_crises(con):
    from econlab.analysis.ch03_money import credit_crisis_stats

    s = credit_crisis_stats()
    assert s["pre_crisis"].mean() - s["normal"].mean() > 2  # ~7.4 vs ~4.5
    assert s["logit_beta"] > 2


def test_ch3_concentration_rising_post2018(con):
    from econlab.analysis.ch03_money import revenue_concentration

    conc = revenue_concentration()
    assert conc.loc[2025, "top10"] > conc.loc[2018, "top10"]  # 22.8 > 19.4
    assert 15 < conc.loc[2025, "top10"] < 35


# ---------- Chapter 7: Balance sheets of power ----------

def test_ch7_financial_hockey_stick(con):
    from econlab.analysis.ch09_power import credit_gdp_panel

    p = credit_gdp_panel()
    assert p.mean18[2007] > 100                 # 111% of GDP
    assert p.mean18[1950] < 40                  # postwar repression
    assert p.mean18[2007] > 1.8 * p.mean18[1913]  # double the first-globalization peak


def test_ch7_fed_footprint_and_losses(con):
    from econlab.analysis.ch09_power import fed_footprint

    ratio, rem = fed_footprint()
    assert ratio[2022] > 30 and ratio[2007] < 8   # 6% -> 34% peak
    assert 15 < ratio[2026] < 25                  # QT brought it to ~21%
    assert rem.min() < -200                        # >$200B accumulated losses


def test_ch7_equity_ownership_concentration(con):
    from econlab.analysis.ch09_power import equity_ownership

    sh = equity_ownership()
    last = sh.dropna().iloc[-1]
    top1 = last["Top 0.1%"] + last["99-99.9%"]
    assert top1 > 45                               # ~50% of the market
    assert top1 + last["90-99%"] > 80              # top decile ~87%
    assert last["Bottom 50%"] < 3                  # ~1%


def test_ch7_wealth_summit(con):
    from econlab.analysis.ch09_power import us_wealth_top_shares

    tw = us_wealth_top_shares()
    assert 0.30 < tw.top1[2024] < 0.40             # ~35%
    assert tw.top1[1978] < 0.25                    # the compression
    assert tw.top01[2024] > 2.2 * tw.top01[1978]   # top 0.1% round trip


def test_ch7_billionaires_snapshot(con):
    n, total, us_total = con.execute(
        "SELECT count(*), sum(worth_usd), "
        "sum(CASE WHEN country='United States' THEN worth_usd END) FROM billionaires"
    ).fetchone()
    assert n > 2_500
    assert 12e12 < total < 30e12                   # ~$19.8T
    bottom50 = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='dfa/nw.net_worth.bottom50'")
    assert us_total > bottom50                      # US billionaires > US bottom half


def test_ch7_bank_concentration(con):
    from econlab.analysis.ch09_power import bank_concentration

    bc = bank_concentration()
    assert 0.35 < bc["top5_sum"] / bc["all_banks"] < 0.7  # ~54% (concept caveat noted)


def test_ch7_household_count_units_fixed(con):
    v = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='dfa/nwd.household_count.bottom50'")
    assert 5.5e7 < v < 7.5e7  # ~67.6M households — guards the 1e6 scaling slip


# ---------- Debt ownership (Ch. 7 extension) ----------

def test_debt_ownership_us_decomposition(con):
    total = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/GFDEBTN'")
    foreign = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/FDHBFIN'")
    fed = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/FDHBFRBN'")
    assert 35e12 < total < 45e12          # ~$39T
    assert 7e12 < foreign < 12e12         # ~$9.3T
    assert 3e12 < fed < 7e12              # ~$4.7T
    assert foreign + fed < total          # decomposition is coherent


def test_debt_ownership_tic_current_and_cross_source(con):
    latest = one(con, "SELECT max(date) FROM obs WHERE series_id='tic/us_treasury_holdings'")
    assert str(latest) >= "2026-04-30"    # the frozen-mirror trap, guarded
    jpn = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='tic/us_treasury_holdings' AND entity='JPN'")
    chn = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='tic/us_treasury_holdings' AND entity='CHN'")
    gbr = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='tic/us_treasury_holdings' AND entity='GBR'")
    assert jpn > gbr > chn                # the 2020s reshuffle: UK passed China
    assert 500e9 < chn < 900e9            # ~$659B, down from >$1.3T in 2013
    # TIC grand total must agree with FRED's independent foreign-holdings series
    tic_total = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='tic/us_treasury_holdings' AND entity='WLD'")
    fred_foreign = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/FDHBFIN'")
    assert abs(tic_total - fred_foreign) / fred_foreign < 0.10


def test_debt_per_company_and_per_capita_derivable(con):
    fnma = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='edgar/debt_lt_q' AND entity='$FNMA'")
    assert fnma > 3e12                    # Fannie Mae ~$4.2T — the largest borrower
    percap = one(
        con,
        """SELECT d.value/100*g.value/p.value FROM obs d
           JOIN obs g ON g.series_id='imf/NGDPD' AND g.entity='USA' AND g.year=2024
           JOIN obs p ON p.series_id='imf/LP' AND p.entity='USA' AND p.year=2024
           WHERE d.series_id='imf/GG_DEBT_GDP' AND d.entity='USA' AND d.year=2024""",
    )
    assert 90_000 < percap < 115_000      # ~$104k of government debt per American


# ---------- Household interest burden ----------

def test_household_debt_service_ratios(con):
    tdsp = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/TDSP'")
    mdsp = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/MDSP'")
    cdsp = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/CDSP'")
    assert 9 < tdsp < 14                       # ~11.2% of disposable income
    assert abs((mdsp + cdsp) - tdsp) < 0.6     # components sum coherently
    peak = one(con, "SELECT max(value) FROM obs WHERE series_id='fred/TDSP'")
    assert peak > 15                           # the 2007 peak (15.7%)


def test_household_debt_stocks_and_rates(con):
    assert 12e12 < one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/HHMSDODNS'") < 16e12
    assert 1.1e12 < one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/REVOLSL'") < 1.7e12
    cc = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/TERMCBCCALLNS'")
    assert 17 < cc < 25                        # ~21% — the price of being illiquid


def test_dfa_income_group_debt_coverage(con):
    hh = one(con, "SELECT sum(v) FROM (SELECT max_by(value,date) v FROM obs "
                  "WHERE series_id LIKE 'dfa/inc.household_count.%' GROUP BY series_id)")
    assert 125e6 < hh < 142e6                  # all US households covered
    top1_mort = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='dfa/inc.home_mortgages.pct99to100'")
    assert top1_mort > 5e11                    # top-1% mortgage stock ~$1.1T


# ---------- Cross-country + demographic debt burdens ----------

def test_bis_dsr_cross_country(con):
    def dsr(e):
        return one(con, f"SELECT max_by(value,date) FROM obs WHERE series_id='bis/dsr_households' AND entity='{e}'")
    assert dsr("NOR") > 15            # Norway ~20.7% — heaviest burden
    assert 6 < dsr("USA") < 10        # ~8.0% (BIS common method; Fed TDSP=11.2%)
    assert dsr("ITA") < 6             # Italy ~4.2%
    assert dsr("AUS") > dsr("USA")    # commonwealth housing-debt economies
    latest = one(con, "SELECT max(date) FROM obs WHERE series_id='bis/dsr_households'")
    assert str(latest) >= "2025-06-30"


def test_dfa_demographic_debt_structure(con):
    def gv(sid):
        return one(con, f"SELECT max_by(value,date) FROM obs WHERE series_id='{sid}'") or 0
    # Black households: consumer credit ~half of debt vs ~quarter for White
    b_m, b_c = gv("dfa/race.home_mortgages.black"), gv("dfa/race.consumer_credit.black")
    w_m, w_c = gv("dfa/race.home_mortgages.white"), gv("dfa/race.consumer_credit.white")
    assert b_c / (b_m + b_c) > w_c / (w_m + w_c) + 0.15
    # age: the 40-54 group carries the peak mortgage load per household
    hh4054 = gv("dfa/age.household_count.age40to54")
    hh70 = gv("dfa/age.household_count.age70plus")
    assert gv("dfa/age.home_mortgages.age40to54") / hh4054 > 2 * (
        gv("dfa/age.home_mortgages.age70plus") / hh70
    )
    # education: college households carry ~5x+ the mortgage of no-HS households
    m_col = gv("dfa/edu.home_mortgages.college") / gv("dfa/edu.household_count.college")
    m_nohs = gv("dfa/edu.home_mortgages.nohs") / gv("dfa/edu.household_count.nohs")
    assert m_col > 5 * m_nohs


# ---------- Debt / interest / income ratios ----------

def test_census_income_by_quintile(con):
    q1 = one(con, "SELECT value FROM obs WHERE series_id='census/mean_hh_income.q1' AND year=2024")
    q5 = one(con, "SELECT value FROM obs WHERE series_id='census/mean_hh_income.q5' AND year=2024")
    assert 16_000 < q1 < 21_000        # $18,460
    assert 290_000 < q5 < 340_000      # $316,100
    first = one(con, "SELECT min(year) FROM obs WHERE series_id='census/mean_hh_income.q1'")
    assert first <= 1970               # history back to 1967


def test_interest_income_ratio_is_regressive(con):
    """Bottom quintile: most leveraged AND highest interest share of income."""
    def d24(comp, grp):
        return one(con, f"SELECT avg(value) FROM obs WHERE series_id='dfa/inc.{comp}.{grp}' AND year=2024") or 0

    def ratios(grp, inc_slug):
        hh = d24("household_count", grp)
        m, c = d24("home_mortgages", grp) / hh, d24("consumer_credit", grp) / hh
        y = one(con, f"SELECT value FROM obs WHERE series_id='census/mean_hh_income.{inc_slug}' AND year=2024")
        interest = m * 4.3 / 100 + c * 10.4 / 100
        return (m + c) / y, interest / y

    lev_bottom, burden_bottom = ratios("pct00to20", "q1")
    assert 1.3 < lev_bottom < 1.9          # ~1.56x income
    assert 0.09 < burden_bottom < 0.13     # ~11% of income in interest

    hh99 = d24("household_count", "pct80to99")
    hh1 = d24("household_count", "pct99to100")
    m5 = (d24("home_mortgages", "pct80to99") + d24("home_mortgages", "pct99to100")) / (hh99 + hh1)
    c5 = (d24("consumer_credit", "pct80to99") + d24("consumer_credit", "pct99to100")) / (hh99 + hh1)
    y5 = one(con, "SELECT value FROM obs WHERE series_id='census/mean_hh_income.q5' AND year=2024")
    burden_top = (m5 * 4.3 / 100 + c5 * 10.4 / 100) / y5
    assert burden_top < 0.07               # ~5.8%
    assert burden_bottom > 1.5 * burden_top  # the regressivity itself


def test_burden_history_regressivity_is_post2008(con):
    from econlab.analysis.ch05_debt import burden_history

    b = burden_history()
    assert abs(b.loc[1995, "q1"] - b.loc[1995, "q5"]) < 2      # classless before 2008
    assert b.loc[2007, "q4"] > b.loc[2007, "q1"]               # boom-era peak was upper-middle
    assert b.loc[2010, "q1"] > 15                              # the crisis spike (18.1%)
    assert b.loc[2021, "q5"] < 5.5                             # cheap money rescued the top
    assert b.loc[2024, "q1"] - b.loc[2024, "q5"] > 4.5         # the modern gap (~6pp)
    assert b.loc[2024, "q1"] > b.loc[2021, "q1"] + 1.5         # card-rate surge reopened it


# ---------- Chapter 8: Who owns the land ----------

def test_ch11_world_forest_ownership(con):
    from econlab.analysis.ch07_land import forest_ownership

    fo = forest_ownership()
    assert 68 < fo.loc["WORLD", "Public"] < 78          # FRA headline: ~73%
    assert fo.loc["MEX", "Public"] < 10                  # the ejido nation
    assert fo.loc["MEX", "Indigenous & community"] > 40  # ~58%
    assert fo.loc["CAN", "Public"] > 85                  # Crown forests
    assert fo.loc["RUS", "Public"] > 95
    assert fo.loc["SWE", "Public"] < 30                  # Nordic private forestry
    # the US inversion: mostly-private forests despite the federal estate
    assert fo.loc["USA", "Other private"] + fo.loc["USA", "Indigenous & community"] > fo.loc["USA", "Public"]


def test_ch11_us_land_stack(con):
    from econlab.analysis.ch07_land import us_stack

    s = us_stack()
    assert abs(sum(s.values()) - 100) < 0.5
    assert 26 < s["Federal"] < 30
    assert s["Private"] > 55
    home = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/RHORUSQ156N'")
    assert 60 < home < 70                                # ~65.3%


def test_ch11_farmland_value_per_acre(con):
    us = one(con, "SELECT value FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
                  "AND entity='USA' AND year=2025")
    assert us == 4350                     # the published national average
    n = one(con, "SELECT count(*) FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
                 "AND year=2025 AND entity LIKE 'US-%'")
    assert n == 48                        # AK/HI not surveyed
    hi = one(con, "SELECT max(value) FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
                  "AND year=2025 AND entity LIKE 'US-%'")
    lo = one(con, "SELECT min(value) FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
                  "AND year=2025 AND entity LIKE 'US-%'")
    assert hi == 22500 and lo == 725      # Rhode Island vs New Mexico: 31x
    ia = one(con, "SELECT value FROM obs WHERE series_id='nass/farm_realestate_per_acre' "
                  "AND entity='US-IA' AND year=2025")
    assert ia == 9790                     # the Corn Belt premium


def test_ch11_county_land_values(con):
    n, med, hi, lo = con.execute(
        "SELECT count(*), median(value), max(value), min(value) FROM obs "
        "WHERE series_id='agcensus/agland_value_per_acre' AND year=2022"
    ).fetchone()
    assert n > 3_000                       # 3,072 counties
    assert 4_000 < med < 4_800             # $4,382 — coheres with NASS state survey
    assert hi > 1e6                        # Staten Island's last farms: $2.55M/acre
    assert lo < 300                        # deep west Texas
    top = one(con, "SELECT e.name FROM obs o JOIN entities e USING(entity) "
                   "WHERE o.series_id='agcensus/agland_value_per_acre' AND o.year=2022 "
                   "ORDER BY o.value DESC LIMIT 1")
    assert "Richmond" in top               # the urban-fringe effect, personified


def test_ch11_land_values_through_time(con):
    """The 175-year panel: booms and busts must be where history put them."""
    def us(y):
        return one(con, "SELECT value FROM obs WHERE series_id='agsurvey/farm_realestate_per_acre' "
                        f"AND entity='USA' AND year={y}")
    assert one(con, "SELECT min(year) FROM obs WHERE series_id='agsurvey/farm_realestate_per_acre'") <= 1850
    assert us(1850) == 11
    assert us(1933) < 0.5 * us(1920)          # the 1930s bust: $69 -> $30
    assert us(1987) < us(1981)                # the '80s farm crisis
    assert us(2025) == 4350                   # exact cross-source match with `nass`
    ia81 = one(con, "SELECT value FROM obs WHERE series_id='agsurvey/farm_realestate_per_acre' "
                    "AND entity='US-IA' AND year=1981")
    ia87 = one(con, "SELECT value FROM obs WHERE series_id='agsurvey/farm_realestate_per_acre' "
                    "AND entity='US-IA' AND year=1987")
    assert ia87 < 0.65 * ia81                 # Iowa lost ~47% nominal in six years


def test_ch11_county_panel_five_vintages(con):
    vintages = one(con, "SELECT count(DISTINCT year) FROM obs WHERE series_id='agcensus/agland_value_per_acre'")
    assert vintages == 5                      # 2002..2022
    med02 = one(con, "SELECT median(value) FROM obs WHERE series_id='agcensus/agland_value_per_acre' AND year=2002")
    assert 1_500 < med02 < 1_900              # $1,673
    # real decade change 2012->2022, median county ~ +19%
    chg = one(con, """
        WITH cpi AS (SELECT avg(CASE WHEN year=2022 THEN v END)/avg(CASE WHEN year=2012 THEN v END) AS infl
                     FROM (SELECT year, avg(value) v FROM obs WHERE series_id='shiller/cpi' GROUP BY 1))
        SELECT median(100*((a.value/b.value)/(SELECT infl FROM cpi)-1))
        FROM obs a JOIN obs b USING (entity)
        WHERE a.series_id='agcensus/agland_value_per_acre' AND a.year=2022
          AND b.series_id='agcensus/agland_value_per_acre' AND b.year=2012""")
    assert 10 < chg < 30


def test_ch11_slider_frames_exist(con):
    from econlab.config import FIGURES

    frames = FIGURES / "frames"
    assert len(list(frames.glob("state_*.png"))) == 16   # 1880..2020 decades + 2025
    assert len(list(frames.glob("county_*.png"))) == 5   # census vintages


def test_ch11_land_report_100(con):
    n, total, biggest = con.execute(
        "SELECT count(*), sum(acres), max(acres) FROM landowners"
    ).fetchone()
    assert n == 100
    assert 2.5e6 < biggest < 3.0e6        # Kroenke 2.7M
    assert 40e6 < total < 47e6            # 43.3M acres = 1.9% of the US
    assert total < 0.025 * 2.27e9         # the hundred biggest own <2.5% of America
    dynasties = one(con, "SELECT count(*) FROM landowners WHERE name ILIKE '%family%' "
                         "OR name ILIKE '%heirs%' OR name ILIKE '%ranch%'")
    assert dynasties >= 65                # an inheritance ledger (72/100)


# ---------- Chapter 10: dynasties ----------

def test_ch11_rothschild_ledger(con):
    total_1899 = one(con, "SELECT value FROM obs WHERE "
                          "series_id='dynasties/rothschild_capital_total' AND year=1899")
    assert total_1899 == 41_452_000        # Ferguson App.2 Table c, to the pound
    paris_1874 = one(con, "SELECT value FROM obs WHERE "
                          "series_id='dynasties/rothschild_capital_paris' AND year=1874")
    total_1874 = one(con, "SELECT value FROM obs WHERE "
                          "series_id='dynasties/rothschild_capital_total' AND year=1874")
    assert paris_1874 / total_1874 > 0.55  # Paris became the center
    naples_last = one(con, "SELECT max(year) FROM obs WHERE "
                           "series_id='dynasties/rothschild_capital_naples'")
    assert naples_last == 1862             # closed with Italian unification
    frankfurt_last = one(con, "SELECT max(year) FROM obs WHERE "
                              "series_id='dynasties/rothschild_capital_frankfurt'")
    assert frankfurt_last == 1899          # wound up 1901, no male heirs


def test_ch11_boe_denominator_and_ratio(con):
    gdp_1852 = one(con, "SELECT value FROM obs WHERE series_id='boe/ngdp' AND year=1852")
    assert 4.5e8 < gdp_1852 < 7.5e8        # ~£582M
    from econlab.analysis.ch11_dynasties import capital_vs_uk

    r = capital_vs_uk()
    assert 2.7 < r.pct_uk.max() < 3.3      # peak ~3.0% of UK GDP
    assert r.pct_uk.idxmax() == 1882
    assert r.loc[1818, "pct_uk"] < 0.5     # the climb was earned, not inherited


def test_ch11_then_vs_now(con):
    from econlab.analysis.ch11_dynasties import then_vs_now

    tn = then_vs_now()
    roth_world = tn.iloc[0]["world"]
    musk_world = tn.iloc[1]["world"]
    assert 0.20 < roth_world < 0.32        # 1882 peak: ~0.27% of world GDP
    assert musk_world > 2 * roth_world     # today's summit is ~2.4x larger


def test_ch11_no_banking_rothschild_on_forbes(con):
    rows = con.execute(
        "SELECT name, worth_usd, rank FROM billionaires WHERE name ILIKE '%rothschild%'"
    ).fetchall()
    assert len(rows) == 1                  # only Jeff Rothschild (Facebook; no relation)
    name, worth, rank = rows[0]
    assert "Jeff" in name and worth < 5e9 and rank > 1000


def test_ch11_fugger_ledger(con):
    f27 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1527")
    f46 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1546")
    f94 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1494")
    assert f27 == 2_021_202 and f46 == 5_100_000
    assert f46 / f94 > 90                  # 94x in 52 years — the steepest ascent


def test_ch11_medici_ledger(con):
    profits = one(con, "SELECT sum(value) FROM obs WHERE series_id='dynasties/medici_profit_period'")
    assert profits == 442_611              # 151,820 + 290,791 (de Roover)
    cap27 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/medici_capital' AND year=1427")
    dep27 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/medici_curia_deposits' AND year=1427")
    assert dep27 / cap27 == 4              # the Pope's money: 4 florins per own florin
    spend = one(con, "SELECT value FROM obs WHERE series_id='dynasties/medici_conversion_spend'")
    assert spend > profits                 # Cosimo spent 1.5x lifetime profits on power


def test_ch11_deep_survivors(con):
    n = one(con, "SELECT count(*) FROM deep_survivors")
    assert n >= 20
    # no Western FAMILY with solid documentation crosses the fall of Rome
    # (sacred offices — Kong, the Patriarchate — are the exception that proves it)
    western_crossers = one(con, """
        SELECT count(*) FROM deep_survivors
        WHERE start_year < 476 AND (end_year IS NULL OR end_year > 700)
          AND documentation = 'solid' AND kind != 'sacred office'
          AND name NOT LIKE '%Japanese%'""")
    assert western_crossers == 0
    kong = one(con, "SELECT 2026 - start_year FROM deep_survivors WHERE name LIKE '%Kong family%'")
    assert kong > 2_500                    # older than the Republic, still going
    senate_end = one(con, "SELECT end_year FROM deep_survivors WHERE name LIKE '%senatorial%'")
    assert 590 < senate_end < 620          # the extinction horizon


def test_ch11_millennium_witnesses(con):
    """The warehouse's own long series must carry the textbook shocks."""
    p48 = one(con, "SELECT value FROM obs WHERE series_id='boe/pop_england' AND year=1348")
    p51 = one(con, "SELECT value FROM obs WHERE series_id='boe/pop_england' AND year=1351")
    assert p51 / p48 < 0.6                 # Black Death: −46% in three years
    c = lambda y: one(con, f"SELECT value FROM obs WHERE series_id='boe/cpi' AND year={y}")  # noqa: E731
    assert c(1650) / c(1500) > 5           # the Tudor-Stuart price revolution (~6.7x)
    assert c(1913) < c(1815)               # the gold-standard century: prices FELL
    assert 900 < c(2015) / c(1209) < 1500  # millennium inflation ~1,214x
    dom = one(con, "SELECT min(year) FROM obs WHERE series_id='boe/pop_england'")
    assert dom <= 1086                     # Domesday is in the warehouse


def test_ch11_eastern_mirror(con):
    osman = one(con, "SELECT 2026 - start_year FROM deep_survivors WHERE name LIKE '%Osman%'")
    assert osman > 720                     # 726 years of documented male line
    cant = one(con, "SELECT start_year FROM deep_survivors WHERE name LIKE '%Kantakouzenos%'")
    assert cant <= 1150                    # the impossible family
    sinai = one(con, "SELECT start_year FROM deep_survivors WHERE name LIKE '%Sinai%'")
    assert sinai == 548                    # Justinian's monastery, still open
    # the Ottoman flatline vs the republican takeoff (Maddison, our warehouse)
    t = lambda y: one(con, f"SELECT value FROM obs WHERE series_id='maddison/gdppc' AND entity='TUR' AND year={y}")  # noqa: E731
    assert t(1820) / t(1500) < 1.35        # +27% in three centuries
    assert t(2022) / t(1820) > 20          # 28x after the rules changed


def test_ch11_royal_lines(con):
    n, realms = con.execute("SELECT count(*), count(DISTINCT realm) FROM royal_lines").fetchone()
    assert n >= 50 and realms == 12
    # the plateau and the extinction event, computed from the table
    crowned = lambda y: one(con, f"""
        SELECT count(DISTINCT realm) FROM royal_lines
        WHERE start_year <= {y} AND coalesce(end_year, 2026) >= {y}""")  # noqa: E731
    assert crowned(1700) >= 11             # the full plateau
    assert crowned(2026) == 5              # Britain, Spain, Denmark, Sweden, Monaco
    assert one(con, "SELECT end_year FROM royal_lines WHERE realm='Poland' "
                    "ORDER BY start_year DESC LIMIT 1") == 1795
    assert one(con, "SELECT end_year IS NULL FROM royal_lines WHERE house='Bourbon' AND realm='Spain'")
    assert one(con, "SELECT end_year IS NULL FROM royal_lines WHERE house='Windsor'")
    grimaldi = one(con, "SELECT 2026 - start_year FROM royal_lines WHERE house='Grimaldi'")
    assert grimaldi > 700                  # the longest single-name run


def test_ch11_dynasty_peaks_table(con):
    n = one(con, "SELECT count(*) FROM dynasty_peaks")
    assert n == 10
    fams = {r[0] for r in con.execute("SELECT family FROM dynasty_peaks").fetchall()}
    assert {"Fugger", "Medici", "Rothschild", "Walton", "Mitsui"} <= fams


def test_ch11_modern_families_from_our_table(con):
    from econlab.analysis.ch11_dynasties import modern_family_shares

    m = modern_family_shares()
    assert m.loc["Walton", "worth"] > 400e9          # ~$485B, richest family
    assert m.loc["Walton", "members"] >= 5
    assert 1.7 < m.loc["Ambani", "pct_home"] < 2.6   # Rockefeller-scale vs India
    assert m.loc["Boehringer", "members"] >= 10      # the quiet 15


# ---------- Phase 3: the MCP apparatus ----------

def test_mcp_server_builds_with_all_tools(con):
    import asyncio

    from econlab.mcp_server import build_server

    tools = {t.name for t in asyncio.run(build_server().list_tools())}
    assert tools == {"econ_coverage", "econ_search", "econ_get", "econ_compare",
                     "econ_sql", "econ_chart", "econ_panel", "econ_crosscheck"}


def test_mcp_impls_answer(con):
    from econlab.mcp_server import get_impl, search_impl, sql_impl

    assert "shiller/cape" in search_impl("cape", 5)          # ranking fix holds
    assert "maddison/gdppc" in get_impl("maddison/gdppc", ["CHN"], start=2000)
    assert "SQL error" in sql_impl("DROP TABLE obs")          # read-only guard
    out = sql_impl("SELECT count(*) n FROM obs")
    assert "n" in out and "error" not in out.lower()


# ---------- Chapter 9: Synthesis ----------

def test_ch6_world_gdp_sum_no_aggregate_double_count(con):
    """IMF 3-letter aggregate codes (MAE, EUQ…) once quadrupled world sums."""
    tn, n = con.execute(
        "SELECT sum(value)/1e12, count(*) FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
    ).fetchone()
    assert 100 < tn < 140   # ~$126T
    assert 180 <= n <= 200  # countries only


def test_ch6_dashboard_complete(con):
    from econlab.analysis.ch12_synthesis import state_of_the_world

    df = state_of_the_world()
    assert len(df) >= 15
    assert df["value"].notna().all()


def test_ch6_crisis_decades(con):
    from econlab.analysis.ch12_synthesis import crisis_share_by_decade

    c = crisis_share_by_decade()
    assert c.idxmax() in (1930, 2000)      # the two great crisis decades
    assert c[1930] > 30                     # a third+ of economies in crisis
    assert c.get(1950, 0) == 0              # Bretton Woods: zero systemic crises
    assert c[1960] == 0


# ---------- Chapter 5: Wealth & people ----------

def test_ch4_top1_ucurve_and_continental_contrast(con):
    from econlab.analysis.ch06_wealth import top1_series

    us, fr = top1_series("USA"), top1_series("FRA")
    assert 0.18 < us[2022] < 0.23      # ~20.7%
    assert us[1975] < 0.13             # the great compression
    assert us[2022] > us[1975] + 0.07  # the U
    assert fr[2022] < us[2022] - 0.05  # Europe's L vs America's U


def test_ch4_global_elephant(con):
    from econlab.analysis.ch06_wealth import global_elephant

    el = global_elephant()
    assert el["p0p10"] > 100                   # poorest decile more than doubled
    assert el.idxmin() in ("p80p90", "p70p80")  # the trough: rich-world middle
    assert el["p99p100"] > el["p90p100"]        # the raised trunk


def test_ch4_global_top10_long_arc(con):
    from econlab.analysis.ch06_wealth import global_shares

    gs = global_shares()
    assert 0.45 < gs["top10"].loc[2023] < 0.60
    assert gs["top10"].loc[1900:1913].max() > gs["top10"].loc[2023]  # colonial peak
    assert 0.05 < gs["bottom50"].loc[2023] < 0.12


def test_ch4_dfa_squeezed_middle(con):
    from econlab.analysis.ch06_wealth import dfa_group_shares

    df = dfa_group_shares()
    assert 12 < df["Top 0.1%"].dropna().iloc[-1] < 16      # ~14.4, from 8.6
    delta_mid = df["50-90%"].dropna().iloc[-1] - df["50-90%"].dropna().iloc[0]
    assert delta_mid < -4                                   # ~-6pp: the squeeze


def test_ch4_labor_share_decline(con):
    from econlab.analysis.ch06_wealth import labor_shares

    ls = labor_shares()
    assert ls.loc[2023, "USA"] < ls.loc[1960, "USA"] - 0.04  # 0.568 vs 0.637


# ---------- Chapter 6: Structural forces ----------

def test_ch5_aging(con):
    from econlab.analysis.ch04_structure import median_ages

    ma = median_ages()
    assert ma.loc[2050, "KOR"] > 55                       # 56.7
    assert ma.loc[2050, "CHN"] - ma.loc[2050, "USA"] > 8  # China ages past the US
    assert ma.loc[2050, "NGA"] < 26


def test_ch5_energy_decoupling_is_relative_only(con):
    from econlab.analysis.ch04_structure import energy_intensity

    i = energy_intensity()
    assert 1 - i[2023] / i[1973] > 0.35  # ~42% less energy per unit of GDP


def test_ch5_china_shock(con):
    from econlab.analysis.ch04_structure import export_shares, top_supplier_counts

    sh = export_shares()
    assert 13 < sh.loc[2024, "CHN"] < 19        # ~16% of world exports
    ts = top_supplier_counts()
    assert ts.loc[2024, "CHN"] > 90             # #1 supplier for 96 countries
    assert ts.loc[2024, "CHN"] > 2 * ts.loc[2024, "USA"]
    assert ts.loc[2000, "USA"] > ts.loc[2000, "CHN"]  # the handover happened ~2009


def test_ch5_globalization_waves(con):
    from econlab.analysis.ch04_structure import openness

    jst, wdi = openness()
    assert jst[1938] < jst[1913] - 15   # the interwar collapse
    assert wdi[2008] > wdi[2024]        # hyperglobalization peaked in 2008


def test_ch1_population_peak_and_fading_tailwind(con):
    from econlab.analysis.ch01_longarc import decomposition, world_population_peak

    year, peak = world_population_peak()
    assert 2078 < year < 2092          # UN medium: ~2084
    assert 10.0e9 < peak < 10.6e9      # ~10.29B
    d = decomposition()
    assert 0.2 < d["pop"].iloc[-1] < 0.45  # 2022-2100 population term ~0.31%/yr


# ---------- the AI cross-checking panel ----------

def test_panel_number_parsing():
    from econlab.panel.panel import parse_number

    assert parse_number("ANSWER: 35%") == 35.0
    assert parse_number("$19.8 trillion") == 19.8e12
    assert parse_number("2.3 billion") == 2.3e9
    assert parse_number("no number here") is None


def test_panel_agreement_scoring():
    from econlab.panel.panel import _score_numeric

    tight, _ = _score_numeric([34, 35, 36, 35])
    wide, _ = _score_numeric([10, 35, 90])
    assert tight > 90 and wide < 30       # high consensus when tight, low when spread


def test_panel_providers_registry():
    from econlab.panel.providers import PROVIDERS

    # the frontier labs the user named are all registered, plus free breadth
    for name in ("claude", "gemini", "gpt", "grok", "llama", "deepseek", "mistral"):
        assert name in PROVIDERS
    assert any(p.tier == "free" for p in PROVIDERS.values())


def test_panel_end_to_end_mock(monkeypatch):
    import econlab.panel.panel as P
    from econlab.panel.providers import Provider

    fakes = {
        "a": "The top 1% owns roughly a third.\nANSWER: 34%\nCONFIDENCE: 0.8",
        "b": "About 35 percent.\nANSWER: 35%\nCONFIDENCE: 0.7",
        "c": "Around 36%.\nANSWER: 36%\nCONFIDENCE: 0.6",
    }
    provs = [Provider(n, n.upper(), "openai", "m", ("K",)) for n in fakes]
    monkeypatch.setattr(P, "ask", lambda p, q, s, **k: fakes[p.name])
    res = P.run_panel("What share of US wealth does the top 1% own?", providers=provs)
    assert res.mode == "numeric" and res.consensus > 90   # 34/35/36 -> tight
    assert all(a.error is None for a in res.answers)


def test_panel_crosscheck_mock(monkeypatch):
    import econlab.panel.panel as P
    from econlab.panel.providers import Provider

    fakes = {
        "a": "Accurate.\nVERDICT: agree\nCONFIDENCE: 0.9",
        "b": "Broadly correct.\nVERDICT: agree\nCONFIDENCE: 0.8",
        "c": "Hard to say.\nVERDICT: uncertain\nCONFIDENCE: 0.4",
    }
    provs = [Provider(n, n.upper(), "openai", "m", ("K",)) for n in fakes]
    monkeypatch.setattr(P, "ask", lambda p, q, s, **k: fakes[p.name])
    res = P.run_crosscheck("The US top 1% owns about 35% of wealth", providers=provs)
    assert res.mode == "verdict" and res.summary["tally"]["agree"] == 2
