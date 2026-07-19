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
    from econlab.analysis.ch07_power import credit_gdp_panel

    p = credit_gdp_panel()
    assert p.mean18[2007] > 100                 # 111% of GDP
    assert p.mean18[1950] < 40                  # postwar repression
    assert p.mean18[2007] > 1.8 * p.mean18[1913]  # double the first-globalization peak


def test_ch7_fed_footprint_and_losses(con):
    from econlab.analysis.ch07_power import fed_footprint

    ratio, rem = fed_footprint()
    assert ratio[2022] > 30 and ratio[2007] < 8   # 6% -> 34% peak
    assert 15 < ratio[2026] < 25                  # QT brought it to ~21%
    assert rem.min() < -200                        # >$200B accumulated losses


def test_ch7_equity_ownership_concentration(con):
    from econlab.analysis.ch07_power import equity_ownership

    sh = equity_ownership()
    last = sh.dropna().iloc[-1]
    top1 = last["Top 0.1%"] + last["99-99.9%"]
    assert top1 > 45                               # ~50% of the market
    assert top1 + last["90-99%"] > 80              # top decile ~87%
    assert last["Bottom 50%"] < 3                  # ~1%


def test_ch7_wealth_summit(con):
    from econlab.analysis.ch07_power import us_wealth_top_shares

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
    from econlab.analysis.ch07_power import bank_concentration

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
    from econlab.analysis.ch08_debt import burden_history

    b = burden_history()
    assert abs(b.loc[1995, "q1"] - b.loc[1995, "q5"]) < 2      # classless before 2008
    assert b.loc[2007, "q4"] > b.loc[2007, "q1"]               # boom-era peak was upper-middle
    assert b.loc[2010, "q1"] > 15                              # the crisis spike (18.1%)
    assert b.loc[2021, "q5"] < 5.5                             # cheap money rescued the top
    assert b.loc[2024, "q1"] - b.loc[2024, "q5"] > 4.5         # the modern gap (~6pp)
    assert b.loc[2024, "q1"] > b.loc[2021, "q1"] + 1.5         # card-rate surge reopened it


# ---------- Chapter 9: Who owns the land ----------

def test_ch9_world_forest_ownership(con):
    from econlab.analysis.ch09_land import forest_ownership

    fo = forest_ownership()
    assert 68 < fo.loc["WORLD", "Public"] < 78          # FRA headline: ~73%
    assert fo.loc["MEX", "Public"] < 10                  # the ejido nation
    assert fo.loc["MEX", "Indigenous & community"] > 40  # ~58%
    assert fo.loc["CAN", "Public"] > 85                  # Crown forests
    assert fo.loc["RUS", "Public"] > 95
    assert fo.loc["SWE", "Public"] < 30                  # Nordic private forestry
    # the US inversion: mostly-private forests despite the federal estate
    assert fo.loc["USA", "Other private"] + fo.loc["USA", "Indigenous & community"] > fo.loc["USA", "Public"]


def test_ch9_us_land_stack(con):
    from econlab.analysis.ch09_land import us_stack

    s = us_stack()
    assert abs(sum(s.values()) - 100) < 0.5
    assert 26 < s["Federal"] < 30
    assert s["Private"] > 55
    home = one(con, "SELECT max_by(value,date) FROM obs WHERE series_id='fred/RHORUSQ156N'")
    assert 60 < home < 70                                # ~65.3%


def test_ch9_farmland_value_per_acre(con):
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


def test_ch9_county_land_values(con):
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


def test_ch9_land_values_through_time(con):
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


def test_ch9_county_panel_five_vintages(con):
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


def test_ch9_slider_frames_exist(con):
    from econlab.config import FIGURES

    frames = FIGURES / "frames"
    assert len(list(frames.glob("state_*.png"))) == 16   # 1880..2020 decades + 2025
    assert len(list(frames.glob("county_*.png"))) == 5   # census vintages


def test_ch9_land_report_100(con):
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

def test_ch10_rothschild_ledger(con):
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


def test_ch10_boe_denominator_and_ratio(con):
    gdp_1852 = one(con, "SELECT value FROM obs WHERE series_id='boe/ngdp' AND year=1852")
    assert 4.5e8 < gdp_1852 < 7.5e8        # ~£582M
    from econlab.analysis.ch10_dynasties import capital_vs_uk

    r = capital_vs_uk()
    assert 2.7 < r.pct_uk.max() < 3.3      # peak ~3.0% of UK GDP
    assert r.pct_uk.idxmax() == 1882
    assert r.loc[1818, "pct_uk"] < 0.5     # the climb was earned, not inherited


def test_ch10_then_vs_now(con):
    from econlab.analysis.ch10_dynasties import then_vs_now

    tn = then_vs_now()
    roth_world = tn.iloc[0]["world"]
    musk_world = tn.iloc[1]["world"]
    assert 0.20 < roth_world < 0.32        # 1882 peak: ~0.27% of world GDP
    assert musk_world > 2 * roth_world     # today's summit is ~2.4x larger


def test_ch10_no_banking_rothschild_on_forbes(con):
    rows = con.execute(
        "SELECT name, worth_usd, rank FROM billionaires WHERE name ILIKE '%rothschild%'"
    ).fetchall()
    assert len(rows) == 1                  # only Jeff Rothschild (Facebook; no relation)
    name, worth, rank = rows[0]
    assert "Jeff" in name and worth < 5e9 and rank > 1000


def test_ch10_fugger_ledger(con):
    f27 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1527")
    f46 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1546")
    f94 = one(con, "SELECT value FROM obs WHERE series_id='dynasties/fugger_capital' AND year=1494")
    assert f27 == 2_021_202 and f46 == 5_100_000
    assert f46 / f94 > 90                  # 94x in 52 years — the steepest ascent


def test_ch10_dynasty_peaks_table(con):
    n = one(con, "SELECT count(*) FROM dynasty_peaks")
    assert n == 10
    fams = {r[0] for r in con.execute("SELECT family FROM dynasty_peaks").fetchall()}
    assert {"Fugger", "Medici", "Rothschild", "Walton", "Mitsui"} <= fams


def test_ch10_modern_families_from_our_table(con):
    from econlab.analysis.ch10_dynasties import modern_family_shares

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
    assert tools == {"econ_coverage", "econ_search", "econ_get",
                     "econ_compare", "econ_sql", "econ_chart"}


def test_mcp_impls_answer(con):
    from econlab.mcp_server import get_impl, search_impl, sql_impl

    assert "shiller/cape" in search_impl("cape", 5)          # ranking fix holds
    assert "maddison/gdppc" in get_impl("maddison/gdppc", ["CHN"], start=2000)
    assert "SQL error" in sql_impl("DROP TABLE obs")          # read-only guard
    out = sql_impl("SELECT count(*) n FROM obs")
    assert "n" in out and "error" not in out.lower()


# ---------- Chapter 6: Synthesis ----------

def test_ch6_world_gdp_sum_no_aggregate_double_count(con):
    """IMF 3-letter aggregate codes (MAE, EUQ…) once quadrupled world sums."""
    tn, n = con.execute(
        "SELECT sum(value)/1e12, count(*) FROM obs WHERE series_id='imf/NGDPD' AND year=2026"
    ).fetchone()
    assert 100 < tn < 140   # ~$126T
    assert 180 <= n <= 200  # countries only


def test_ch6_dashboard_complete(con):
    from econlab.analysis.ch06_synthesis import state_of_the_world

    df = state_of_the_world()
    assert len(df) >= 15
    assert df["value"].notna().all()


def test_ch6_crisis_decades(con):
    from econlab.analysis.ch06_synthesis import crisis_share_by_decade

    c = crisis_share_by_decade()
    assert c.idxmax() in (1930, 2000)      # the two great crisis decades
    assert c[1930] > 30                     # a third+ of economies in crisis
    assert c.get(1950, 0) == 0              # Bretton Woods: zero systemic crises
    assert c[1960] == 0


# ---------- Chapter 4: Wealth & people ----------

def test_ch4_top1_ucurve_and_continental_contrast(con):
    from econlab.analysis.ch04_wealth import top1_series

    us, fr = top1_series("USA"), top1_series("FRA")
    assert 0.18 < us[2022] < 0.23      # ~20.7%
    assert us[1975] < 0.13             # the great compression
    assert us[2022] > us[1975] + 0.07  # the U
    assert fr[2022] < us[2022] - 0.05  # Europe's L vs America's U


def test_ch4_global_elephant(con):
    from econlab.analysis.ch04_wealth import global_elephant

    el = global_elephant()
    assert el["p0p10"] > 100                   # poorest decile more than doubled
    assert el.idxmin() in ("p80p90", "p70p80")  # the trough: rich-world middle
    assert el["p99p100"] > el["p90p100"]        # the raised trunk


def test_ch4_global_top10_long_arc(con):
    from econlab.analysis.ch04_wealth import global_shares

    gs = global_shares()
    assert 0.45 < gs["top10"].loc[2023] < 0.60
    assert gs["top10"].loc[1900:1913].max() > gs["top10"].loc[2023]  # colonial peak
    assert 0.05 < gs["bottom50"].loc[2023] < 0.12


def test_ch4_dfa_squeezed_middle(con):
    from econlab.analysis.ch04_wealth import dfa_group_shares

    df = dfa_group_shares()
    assert 12 < df["Top 0.1%"].dropna().iloc[-1] < 16      # ~14.4, from 8.6
    delta_mid = df["50-90%"].dropna().iloc[-1] - df["50-90%"].dropna().iloc[0]
    assert delta_mid < -4                                   # ~-6pp: the squeeze


def test_ch4_labor_share_decline(con):
    from econlab.analysis.ch04_wealth import labor_shares

    ls = labor_shares()
    assert ls.loc[2023, "USA"] < ls.loc[1960, "USA"] - 0.04  # 0.568 vs 0.637


# ---------- Chapter 5: Structural forces ----------

def test_ch5_aging(con):
    from econlab.analysis.ch05_structure import median_ages

    ma = median_ages()
    assert ma.loc[2050, "KOR"] > 55                       # 56.7
    assert ma.loc[2050, "CHN"] - ma.loc[2050, "USA"] > 8  # China ages past the US
    assert ma.loc[2050, "NGA"] < 26


def test_ch5_energy_decoupling_is_relative_only(con):
    from econlab.analysis.ch05_structure import energy_intensity

    i = energy_intensity()
    assert 1 - i[2023] / i[1973] > 0.35  # ~42% less energy per unit of GDP


def test_ch5_china_shock(con):
    from econlab.analysis.ch05_structure import export_shares, top_supplier_counts

    sh = export_shares()
    assert 13 < sh.loc[2024, "CHN"] < 19        # ~16% of world exports
    ts = top_supplier_counts()
    assert ts.loc[2024, "CHN"] > 90             # #1 supplier for 96 countries
    assert ts.loc[2024, "CHN"] > 2 * ts.loc[2024, "USA"]
    assert ts.loc[2000, "USA"] > ts.loc[2000, "CHN"]  # the handover happened ~2009


def test_ch5_globalization_waves(con):
    from econlab.analysis.ch05_structure import openness

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
