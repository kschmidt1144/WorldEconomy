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
        ch01_longarc, ch02_nations, ch03_money, ch04_wealth,
        ch05_structure, ch06_synthesis, ch07_power, ch08_debt, ch09_land, phase0,
    )

    phase0.main()
    ch01_longarc.main()
    ch02_nations.main()
    ch03_money.main()
    ch04_wealth.main()
    ch05_structure.main()
    ch06_synthesis.main()
    ch07_power.main()
    ch08_debt.main()
    ch09_land.main()


@app.command()
def compile() -> None:
    """Compile report/*.md into one self-contained HTML (figures embedded)."""
    import base64
    import datetime
    import re

    import markdown as md

    from .config import REPORT

    chapters = sorted(REPORT.glob("[0-9][0-9]-*.md"))
    body_parts = []
    for ch in chapters:
        html = md.markdown(ch.read_text(), extensions=["tables", "fenced_code"])
        body_parts.append(f'<section id="{ch.stem}">\n{html}\n</section>')
    body = "\n<hr/>\n".join(body_parts)

    def embed(match: "re.Match[str]") -> str:
        rel = match.group(1)
        p = REPORT / rel
        if not p.exists():
            return match.group(0)
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'src="data:image/png;base64,{b64}"'

    body = re.sub(r'src="(figures/[^"]+)"', embed, body)

    css = """
    body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:880px;
         margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1f2328}
    img{max-width:100%;border:1px solid #d0d7de;border-radius:6px;margin:.5rem 0}
    table{border-collapse:collapse;margin:1rem 0}
    td,th{border:1px solid #d0d7de;padding:.3rem .6rem;font-size:.92rem}
    th{background:#f6f8fa} h1{border-bottom:2px solid #d0d7de;padding-bottom:.3rem;margin-top:3rem}
    em{color:#57606a} hr{border:none;border-top:2px solid #d0d7de;margin:3rem 0}
    """
    stamp = datetime.date.today().isoformat()
    out = REPORT / "world-economy-report.html"
    out.write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>World Economy Lab — Report</title>"
        f"<style>{css}</style></head><body>"
        f"<p><em>World Economy Lab — compiled {stamp}. Every figure and number "
        "computed from primary data; regenerate with `econ refresh && econ figures && econ compile`.</em></p>"
        f"{body}</body></html>"
    )
    print(f"compiled: {out} ({out.stat().st_size/1e6:.1f} MB, {len(chapters)} chapters)")


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


if __name__ == "__main__":
    app()
