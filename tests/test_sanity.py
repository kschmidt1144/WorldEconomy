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
