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


def test_markets_current_and_sane(con):
    latest, close = con.execute(
        "SELECT date, value FROM obs WHERE series_id='markets/spx' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    assert str(latest) >= "2026-07-01"  # data is current
    assert 3_000 < close < 12_000
