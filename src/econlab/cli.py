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
def event(date: str) -> None:
    """Market impact of an event on a date (YYYY-MM-DD): S&P drawdown & returns after."""
    from .analysis.events import event_impact

    r = event_impact(date)
    if r is None:
        print(f"{date}: no S&P price data spanning that date (daily from 1927, monthly from 1871).")
        return
    r1 = f"{r['ret_1m']:+.1f}%" if r["ret_1m"] is not None else "n/a"
    print(f"{date}  (base {r['base_date']}, S&P {r['base']:,.0f}, {r['resolution']} data)\n"
          f"  3-month max drawdown: {r['drawdown_3m']:+.1f}%\n"
          f"  return after 1 month: {r1}\n"
          f"  return after 3 months: {r['ret_3m']:+.1f}%")


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
        ch01_longarc, ch02_nations, ch03_money, ch05_debt, ch06_wealth,
        ch09_power, ch07_land, ch04_structure, ch08_cost, ch10_chokepoints,
        ch11_levers,
        ch12_dynasties, ch13_synthesis, phase0,
    )

    phase0.main()
    ch01_longarc.main()
    ch02_nations.main()
    ch03_money.main()
    ch05_debt.main()
    ch06_wealth.main()
    ch09_power.main()
    ch07_land.main()
    ch04_structure.main()
    ch08_cost.main()
    ch10_chokepoints.main()
    ch11_levers.main()
    ch12_dynasties.main()
    ch13_synthesis.main()


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


def _fmt_note(n: dict, show_chapter: bool = False) -> str:
    import datetime

    when = datetime.datetime.fromtimestamp(n.get("updatedAt", 0) / 1000).strftime("%Y-%m-%d")
    where = n.get("anchorText") or n.get("anchor") or ""
    head = f"[{n.get('chapter', '')}] " if show_chapter else ""
    lines = [f"• {head}{where}  ({when})"]
    if n.get("quote"):
        lines.append(f'    “{n["quote"][:140]}”')
    if n.get("body"):
        lines.append(f"    {n['body']}")
    return "\n".join(lines)


@app.command()
def notes(
    chapter: str = typer.Option(None, "--chapter", "-c", help="filter by chapter slug, e.g. 10-chokepoints"),
    search: str = typer.Option(None, "--search", help="substring over quote + body"),
    limit: int = typer.Option(50, help="max notes to show"),
) -> None:
    """Read your margin notes from the tablet reader (Firestore `worldeconomy`)."""
    from .notes_store import NotesUnavailable, list_notes

    try:
        items = list_notes(chapter=chapter, query=search, limit=limit)
    except NotesUnavailable as e:
        print(f"notes unavailable: {e}")
        raise typer.Exit(code=1)
    if not items:
        print("no notes yet." if not (chapter or search) else "no matching notes.")
        return
    print(f"{len(items)} note(s):\n")
    for n in items:
        print(_fmt_note(n, show_chapter=chapter is None))
        print()


@app.command(name="note-add")
def note_add(
    chapter: str = typer.Argument(..., help="chapter slug, e.g. 10-chokepoints"),
    body: str = typer.Argument(..., help="the note text"),
    quote: str = typer.Option("", "--quote", "-q", help="the passage the note is about"),
    anchor: str = typer.Option("", "--anchor", help="element id (heading/figure) to anchor to"),
) -> None:
    """Add a margin note (syncs to the tablet reader)."""
    from .notes_store import NotesUnavailable, add_note

    try:
        n = add_note(chapter=chapter, body=body, quote=quote, anchor=anchor, source="cli")
    except NotesUnavailable as e:
        print(f"notes unavailable: {e}")
        raise typer.Exit(code=1)
    print(f"added note {n['id']} to {n['chapter']}")


if __name__ == "__main__":
    app()
