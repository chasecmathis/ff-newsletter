"""ffnews — ingest ESPN data, build fact packs, draft and verify newsletters."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from . import espn, facts, ingest
from .config import MissingCredential, newsletter_path

app = typer.Typer(help=__doc__, no_args_is_help=True, add_completion=False)
console = Console()


def _parse_weeks(spec: str | None, year: int) -> list[int]:
    """Accepts '6', '1-6', '1,3,5', or None for every played week."""
    if not spec:
        return espn.playable_weeks(year)
    weeks: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            weeks.extend(range(int(start), int(end) + 1))
        elif part:
            weeks.append(int(part))
    return sorted(set(weeks))


def ingest_cmd(
    year: int = typer.Option(..., "--year", "-y"),
    weeks: str = typer.Option(None, "--weeks", "-w", help="e.g. 6, 1-6, or 1,3,5. Defaults to every played week."),
    force: bool = typer.Option(False, "--force", help="Re-pull weeks already on disk."),
) -> None:
    """Pull ESPN data into committed JSON snapshots."""
    try:
        ingest.ingest_league(year)
        console.print(f"[green]✓[/] league.json for {year}")
        for week in _parse_weeks(weeks, year):
            result = ingest.ingest_week(year, week, force=force)
            if result is None:
                console.print(f"[dim]·[/] week {week:>2} already on disk (--force to re-pull)")
            elif not result["transactionsAvailable"]:
                console.print(f"[yellow]![/] week {week:>2}: {len(result['matchups'])} matchups, "
                              f"but ESPN returned a malformed transaction feed — roster moves "
                              f"unavailable for this week")
            else:
                console.print(f"[green]✓[/] week {week:>2}: {len(result['matchups'])} matchups, "
                              f"{len(result['transactions'])} transactions")
    except (MissingCredential, espn.EspnUnavailable) as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)


def build_facts(
    year: int = typer.Option(..., "--year", "-y"),
    weeks: str = typer.Option(None, "--weeks", "-w"),
) -> None:
    """Derive the fact pack the site and the newsletter both read."""
    targets = _parse_weeks(weeks, year) if weeks else facts.regular_season_weeks(year)
    for week in targets:
        if facts.is_playoff_week(year, week):
            console.print(f"[yellow]·[/] week {week:>2} is a playoff week — ESPN reports it as a "
                          f"multi-week total, so it has no single-week stats. Skipped.")
            continue
        pack = facts.build(year, week)
        console.print(f"[green]✓[/] week {week:>2}: {len(pack['facts'])} facts")


@app.command()
def standings(
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(None, "--week", "-w"),
) -> None:
    """Print the standings as computed from local snapshots."""
    week = week or max(facts.regular_season_weeks(year))
    table = Table(title=f"{year} standings through week {week}", header_style="bold")
    for col in ("#", "Team", "Record", "PF", "PA", "Streak"):
        table.add_column(col, justify="right" if col in {"#", "PF", "PA"} else "left")
    for row in facts.standings_through(year, week):
        table.add_row(str(row["rank"]), row["name"], row["record"],
                      f"{row['pointsFor']:.1f}", f"{row['pointsAgainst']:.1f}", row["streak"])
    console.print(table)


@app.command()
def draft(
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    effort: str = typer.Option("high", "--effort", help="low | medium | high | xhigh | max"),
    skip_verify: bool = typer.Option(False, "--skip-verify"),
    quick: bool = typer.Option(False, "--quick", help="Skip the Claude audit pass; run number checks only."),
) -> None:
    """Draft the week's newsletter with Claude, grounded in the fact pack."""
    from .draft import write_newsletter

    try:
        path = write_newsletter(year, week, effort=effort, run_verify=not skip_verify, deep=not quick)
    except MissingCredential as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"\n[green]✓[/] draft written to [bold]{path}[/]")
    console.print("[dim]Read the flags above, edit the file, then: ffnews publish[/]")


@app.command()
def verify(
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    deep: bool = typer.Option(True, "--deep/--quick", help="Include the Claude audit pass."),
) -> None:
    """Check every number and name in a draft against the fact pack."""
    from .verify import report

    path = newsletter_path(year, week)
    if not path.exists():
        console.print(f"[red]No newsletter at {path}[/]")
        raise typer.Exit(1)
    ok = report(year, week, path.read_text(), deep=deep)
    raise typer.Exit(0 if ok else 1)


@app.command()
def publish(
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
) -> None:
    """Flip a reviewed draft to published so the site will build it."""
    path = newsletter_path(year, week)
    if not path.exists():
        console.print(f"[red]No newsletter at {path}[/]")
        raise typer.Exit(1)
    text = path.read_text()
    if "status: draft" not in text:
        console.print("[yellow]Already published.[/]")
        raise typer.Exit(0)
    path.write_text(text.replace("status: draft", "status: published", 1))
    console.print(f"[green]✓[/] {path.name} published")


# typer derives command names from function names; keep the CLI verbs clean.
app.command(name="ingest")(ingest_cmd)
app.command(name="facts")(build_facts)

if __name__ == "__main__":
    app()
