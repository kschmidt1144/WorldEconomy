"""`econ` CLI — the human-facing verbs (the MCP server will mirror these)."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


@app.command()
def refresh(
    source: list[str] = typer.Option(None, "--source", "-s", help="source name(s); default all"),
    force: bool = typer.Option(False, help="re-download even if cached"),
    build: bool = typer.Option(True, help="rebuild warehouse after refresh"),
) -> None:
    """Fetch + parse sources into the tidy layer, then rebuild the warehouse."""
    from .refresh import refresh as _refresh

    results = _refresh(list(source) if source else None, force=force, build=build)
    failed = [k for k, v in results.items() if isinstance(v, str)]
    if failed:
        raise typer.Exit(code=1)


@app.command()
def build() -> None:
    """Rebuild warehouse.duckdb from the tidy layer (no downloads)."""
    from .entities import build_entities
    from .model import build_warehouse

    build_entities()
    print(f"warehouse rebuilt: {build_warehouse()}")


@app.command()
def search(query: str, limit: int = 25) -> None:
    """Search the series catalog (name/id/description, case-insensitive)."""
    import pandas as pd

    from .model import connect

    with connect() as con:
        df = con.execute(
            """
            SELECT series_id, name, unit, frequency AS freq,
                   (SELECT count(*) FROM obs o WHERE o.series_id = c.series_id) AS n_obs
            FROM catalog c
            WHERE series_id ILIKE '%' || $1 || '%'
               OR name ILIKE '%' || $1 || '%'
               OR description ILIKE '%' || $1 || '%'
            ORDER BY n_obs DESC
            LIMIT $2
            """,
            [query, limit],
        ).df()
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(df.to_string(index=False) if len(df) else "no matches")


@app.command()
def get(
    series_id: str,
    entity: list[str] = typer.Option(None, "--entity", "-e"),
    start: int = typer.Option(None, help="first year"),
    end: int = typer.Option(None, help="last year"),
    tail: int = typer.Option(20, help="show last N rows (0 = all)"),
) -> None:
    """Print observations for a series."""
    import pandas as pd

    from .model import connect

    q = "SELECT entity, year, date, value FROM obs WHERE series_id = $1"
    params: list = [series_id]
    if entity:
        q += f" AND entity IN ({','.join('?' * len(entity))})"
        params += list(entity)
    if start is not None:
        q += " AND year >= ?"
        params.append(start)
    if end is not None:
        q += " AND year <= ?"
        params.append(end)
    q += " ORDER BY entity, year, date"
    with connect() as con:
        df = con.execute(q, params).df()
    if tail and len(df) > tail:
        print(f"({len(df):,} rows; last {tail})")
        df = df.tail(tail)
    with pd.option_context("display.width", 200):
        print(df.to_string(index=False) if len(df) else "no data")


@app.command()
def sql(query: str, limit_rows: int = 50) -> None:
    """Run read-only SQL against the warehouse (tables: obs, catalog, entities; view: series)."""
    import pandas as pd

    from .model import connect

    with connect() as con:
        df = con.execute(query).df()
    if len(df) > limit_rows:
        print(f"({len(df):,} rows; first {limit_rows})")
        df = df.head(limit_rows)
    with pd.option_context("display.width", 240, "display.max_columns", 40):
        print(df.to_string(index=False))


@app.command()
def figures() -> None:
    """Regenerate all report figures from the warehouse."""
    from .analysis import (
        ch01_longarc, ch02_nations, ch03_money, ch04_debt, ch05_wealth,
        ch06_power, ch07_land, ch08_structure, ch09_cost, ch10_dynasties,
        ch11_synthesis, phase0,
    )

    phase0.main()
    ch01_longarc.main()
    ch02_nations.main()
    ch03_money.main()
    ch04_debt.main()
    ch05_wealth.main()
    ch06_power.main()
    ch07_land.main()
    ch08_structure.main()
    ch09_cost.main()
    ch10_dynasties.main()
    ch11_synthesis.main()


@app.command()
def compile() -> None:
    """Compile report/*.md into the navigable single-file web view."""
    from .report_build import build

    build()


@app.command()
def coverage() -> None:
    """Warehouse coverage summary by source."""
    import pandas as pd

    from .model import connect

    with connect() as con:
        df = con.execute(
            """
            SELECT c.source,
                   count(DISTINCT c.series_id) AS series,
                   count(o.value)              AS obs,
                   count(DISTINCT o.entity)    AS entities,
                   min(o.year)                 AS first_year,
                   max(o.year)                 AS last_year
            FROM catalog c JOIN obs o USING (series_id)
            GROUP BY 1 ORDER BY obs DESC
            """
        ).df()
    with pd.option_context("display.width", 200):
        print(df.to_string(index=False))


@app.command()
def panel(
    question: str,
    model: list[str] = typer.Option(None, "--model", "-m", help="restrict to these provider names"),
) -> None:
    """Ask several AI models the same question; measure how much they agree."""
    import datetime

    from .panel import available_providers, format_result, log_run, run_panel

    provs = available_providers()
    if model:
        provs = [p for p in provs if p.name in set(model)]
    res = run_panel(question, providers=provs)
    print(format_result(res))
    if res.answers:
        log_run(res, datetime.datetime.now().isoformat(timespec="seconds"))


@app.command()
def crosscheck(claim: str) -> None:
    """Have the AI panel vote agree/disagree/uncertain on a stated claim."""
    import datetime

    from .panel import available_providers, format_result, log_run, run_crosscheck

    res = run_crosscheck(claim, providers=available_providers())
    print(format_result(res))
    if res.answers:
        log_run(res, datetime.datetime.now().isoformat(timespec="seconds"))


@app.command(name="panel-models")
def panel_models() -> None:
    """List the cross-check providers and whether each has an API key configured."""
    from .panel import PROVIDERS

    ready = [p for p in PROVIDERS.values() if p.available()]
    print(f"{'provider':12} {'tier':5} {'ready':6} model / how to enable")
    for p in PROVIDERS.values():
        how = "" if p.available() else f"set {p.key_names[0]}"
        print(f"{p.name:12} {p.tier:5} {'✓' if p.available() else '–':6} {p.model}  {how}")
    print(f"\n{len(ready)} of {len(PROVIDERS)} ready. Free keys: GITHUB_TOKEN (GPT), "
          "GROQ_API_KEY (Llama/DeepSeek/Qwen), GOOGLE_API_KEY (Gemini free tier), "
          "MISTRAL_API_KEY, OPENROUTER_API_KEY.")


if __name__ == "__main__":
    app()
