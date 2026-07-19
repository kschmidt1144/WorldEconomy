"""econlab MCP server — the apparatus.

Exposes the warehouse (15 sources, ~2,000 series, ~14.7M observations,
year 1 CE -> 2101) to any MCP client. Registered user-level, this makes every
Claude session a natural-language interface to the world economy.

Design: thin @tool wrappers over plain `_impl` functions (testable without a
client); every call opens a fresh read-only DuckDB connection so refreshes
in other processes never conflict.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from .config import DATA
from .model import connect

CHARTS = DATA / "charts"


def _df_text(df: pd.DataFrame, max_rows: int = 60) -> str:
    note = ""
    if len(df) > max_rows:
        note = f"({len(df):,} rows; showing first {max_rows})\n"
        df = df.head(max_rows)
    with pd.option_context("display.width", 220, "display.max_columns", 40,
                           "display.max_colwidth", 60):
        return note + (df.to_string(index=False) if len(df) else "no rows")


# ---------------- implementations (plain, testable) ----------------

def coverage_impl() -> str:
    with connect() as con:
        cov = con.execute(
            """
            SELECT c.source, count(DISTINCT c.series_id) AS series, count(o.value) AS obs,
                   count(DISTINCT o.entity) AS entities, min(o.year) AS first_yr, max(o.year) AS last_yr
            FROM catalog c JOIN obs o USING (series_id) GROUP BY 1 ORDER BY obs DESC
            """
        ).df()
        kinds = con.execute("SELECT kind, count(*) n FROM entities GROUP BY 1 ORDER BY n DESC").df()
        trade = con.execute("SELECT count(*) FROM trade").fetchone()[0]
    return (
        "econlab warehouse coverage:\n\n" + _df_text(cov)
        + "\n\nentity kinds:\n" + _df_text(kinds)
        + f"\n\nbilateral trade table: {trade:,} (year, exporter, importer, value_usd) rows"
        + "\n\nConventions: countries are ISO3 (USA, CHN; WLD = world aggregate); companies are"
        " $-prefixed tickers ($AAPL); market instruments are bare slugs (SPX, GOLD)."
        " unit_type on each series (nominal_usd/real_usd/ppp_usd/lcu/index/percent/ratio/count/physical)"
        " — never mix unit types in one computation. Annual data uses `year`; sub-annual uses `date`."
    )


def search_impl(query: str, limit: int = 25) -> str:
    with connect() as con:
        df = con.execute(
            """
            SELECT series_id, name, unit, unit_type, frequency AS freq,
                   (SELECT count(*) FROM obs o WHERE o.series_id = c.series_id) AS n_obs,
                   (SELECT max(year) FROM obs o WHERE o.series_id = c.series_id) AS last_yr
            FROM catalog c
            WHERE series_id ILIKE '%' || $1 || '%' OR name ILIKE '%' || $1 || '%'
               OR description ILIKE '%' || $1 || '%'
            ORDER BY (series_id ILIKE '%' || $1 || '%' OR name ILIKE '%' || $1 || '%') DESC,
                     n_obs DESC
            LIMIT $2
            """,
            [query, limit],
        ).df()
    return _df_text(df)


def get_impl(series_id: str, entities: list[str] | None = None,
             start: int | None = None, end: int | None = None, tail: int = 30) -> str:
    q = (
        "SELECT o.entity, e.name AS entity_name, o.year, o.date, o.value "
        "FROM obs o LEFT JOIN entities e USING (entity) WHERE o.series_id = ?"
    )
    params: list = [series_id]
    if entities:
        q += f" AND o.entity IN ({','.join('?' * len(entities))})"
        params += [e.upper() for e in entities]
    if start is not None:
        q += " AND o.year >= ?"
        params.append(start)
    if end is not None:
        q += " AND o.year <= ?"
        params.append(end)
    q += " ORDER BY o.entity, o.year, o.date"
    with connect() as con:
        meta = con.execute(
            "SELECT name, unit, unit_type, frequency FROM catalog WHERE series_id=?", [series_id]
        ).fetchone()
        df = con.execute(q, params).df()
    if meta is None:
        return f"unknown series_id {series_id!r} — use econ_search first"
    header = f"{series_id}: {meta[0]} [{meta[1] or meta[2]}] freq={meta[3]}\n"
    if len(df) > tail:
        header += f"({len(df):,} rows; showing last {tail} — pass start/end/tail to change)\n"
        df = df.tail(tail)
    return header + _df_text(df, max_rows=tail)


def compare_impl(series_id: str, entities: list[str], start: int | None = None) -> str:
    with connect() as con:
        df = con.execute(
            f"""
            SELECT year, entity, avg(value) AS value FROM obs
            WHERE series_id = ? AND entity IN ({','.join('?' * len(entities))})
              AND year >= ?
            GROUP BY 1, 2 ORDER BY 1
            """,
            [series_id, *[e.upper() for e in entities], start or 0],
        ).df()
    if df.empty:
        return "no rows — check series_id/entities with econ_search / econ_coverage"
    pivot = df.pivot(index="year", columns="entity", values="value")
    return _df_text(pivot.reset_index(), max_rows=80)


def sql_impl(query: str, max_rows: int = 50) -> str:
    try:
        with connect() as con:  # read_only=True: writes are impossible
            df = con.execute(query).df()
    except Exception as e:
        return f"SQL error: {e}"
    return _df_text(df, max_rows=max_rows)


def chart_impl(series_ids: list[str], entities: list[str] | None = None,
               start: int | None = None, end: int | None = None,
               log_scale: bool = False, title: str | None = None) -> str:
    from .viz import new_fig, source_note

    with connect() as con:
        fig, ax = new_fig(title or " / ".join(series_ids), ylabel=None)
        plotted = 0
        for sid in series_ids:
            ents = [e.upper() for e in (entities or [])]
            if not ents:
                ents = [r[0] for r in con.execute(
                    "SELECT DISTINCT entity FROM obs WHERE series_id=? LIMIT 6", [sid]
                ).fetchall()]
            for ent in ents:
                df = con.execute(
                    "SELECT year, date, value FROM obs WHERE series_id=? AND entity=? "
                    "AND year >= ? AND year <= ? ORDER BY year, date",
                    [sid, ent, start or -5000, end or 9999],
                ).df()
                if df.empty:
                    continue
                x = pd.to_datetime(df["date"]) if df["date"].notna().all() else df["year"]
                label = f"{sid.split('/')[-1]}:{ent}" if len(series_ids) > 1 else ent
                ax.plot(x, df["value"], lw=1.6, label=label)
                plotted += 1
    if plotted == 0:
        return "nothing to plot — check series/entities"
    if log_scale:
        ax.set_yscale("log")
    if plotted > 1:
        ax.legend(fontsize=8)
    source_note(ax, "econlab warehouse")
    CHARTS.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(repr((series_ids, entities, start, end, log_scale)).encode()).hexdigest()[:10]
    out = CHARTS / f"chart_{key}.png"
    fig.savefig(out)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return f"chart saved: {out} — use the Read tool on this path to view it"


def panel_impl(question: str, crosscheck: bool = False) -> str:
    """Poll every configured AI model with one question and score their agreement."""
    from .panel import available_providers, format_result, log_run, run_crosscheck, run_panel

    provs = available_providers()
    if not provs:
        return ("No AI panel providers configured. Add a key (free options: GITHUB_TOKEN "
                "for GPT, GROQ_API_KEY for Llama/DeepSeek/Qwen, GOOGLE_API_KEY for Gemini) "
                "to .env, then retry.")
    res = run_crosscheck(question, provs) if crosscheck else run_panel(question, provs)
    import datetime

    log_run(res, datetime.datetime.now().isoformat(timespec="seconds"))
    return format_result(res)


# ---------------- MCP wiring ----------------

def build_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("econlab")

    @mcp.tool()
    def econ_coverage() -> str:
        """What's in the world-economy warehouse: sources, series counts, spans,
        entity conventions. Call this first to orient."""
        return coverage_impl()

    @mcp.tool()
    def econ_search(query: str, limit: int = 25) -> str:
        """Search ~2,000 economic series by keyword (name/id/description).
        Sources: World Bank, IMF, FRED, SEC EDGAR, Maddison (year 1 CE+), JST,
        WID inequality, UN population, energy, markets, trade."""
        return search_impl(query, limit)

    @mcp.tool()
    def econ_get(series_id: str, entities: list[str] | None = None,
                 start: int | None = None, end: int | None = None, tail: int = 30) -> str:
        """Observations for one series (e.g. 'maddison/gdppc'). entities: ISO3
        codes / $TICKER / instrument slugs. start/end are years."""
        return get_impl(series_id, entities, start, end, tail)

    @mcp.tool()
    def econ_compare(series_id: str, entities: list[str], start: int | None = None) -> str:
        """One series pivoted across several entities by year — the quick way to
        compare countries (e.g. 'imf/PPPPC' for USA vs CHN vs IND)."""
        return compare_impl(series_id, entities, start)

    @mcp.tool()
    def econ_sql(query: str, max_rows: int = 50) -> str:
        """Read-only SQL (DuckDB) against tables obs(series_id, entity, year,
        date, value), catalog, entities(entity, name, kind, region…),
        trade(year, exporter, importer, value_usd) and view series (obs+catalog).
        For anything the other tools can't express."""
        return sql_impl(query, max_rows)

    @mcp.tool()
    def econ_chart(series_ids: list[str], entities: list[str] | None = None,
                   start: int | None = None, end: int | None = None,
                   log_scale: bool = False, title: str | None = None) -> str:
        """Render a line chart (PNG) of series x entities; returns the file path
        (view it with the Read tool). Don't mix unit types in one chart."""
        return chart_impl(series_ids, entities, start, end, log_scale, title)

    @mcp.tool()
    def econ_panel(question: str) -> str:
        """Cross-check a question or finding across several AI models (Claude,
        Gemini, GPT, Grok, Llama, DeepSeek, Qwen, Mistral — whichever have keys)
        and report how much they agree: a numeric-consensus score if the answers
        are numbers, else text similarity. Divergence flags a contested claim.
        Ask a well-posed, single-answer question and pin the unit."""
        return panel_impl(question, crosscheck=False)

    @mcp.tool()
    def econ_crosscheck(claim: str) -> str:
        """Have the AI panel independently vote agree / disagree / uncertain on a
        stated claim (e.g. a finding from this warehouse), and tally the verdict."""
        return panel_impl(claim, crosscheck=True)

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
