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
