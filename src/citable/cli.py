"""Typer CLI. `citable audit DOMAIN` is the only audit command in v0.1.x."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def _bail_on_missing_dep(name: str, hint: str) -> None:
    """Friendly error when a dep is not installed. Skips the traceback so users
    see a clear next step instead of a stack."""
    print(
        f"\n  citable cannot start: missing dependency `{name}`.\n"
        f"  {hint}\n"
        f"  After reinstall, run `citable doctor` to verify the environment.\n",
        file=sys.stderr,
    )
    sys.exit(1)


try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
except ImportError as e:
    _bail_on_missing_dep(
        e.name or "typer/rich",
        "Reinstall citable. The recommended path is `pipx install citable`. "
        "If you cloned the repo, run `pip install --upgrade pip && pip install -e .` inside a venv.",
    )

from citable import __version__
from citable.banner import render_banner
from citable.checks import run_all_checks
from citable.crawler import crawl, normalize_domain, normalize_target
from citable.models import AuditReport, Verdict
from citable.promo import recommend_for
from citable.scoring import finalize
from citable.xlsx_writer import write_report

app = typer.Typer(
    help="AI search visibility audit. Built by Work-Smart.ai.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _default_output_path(target: str) -> Path:
    root, prefix = normalize_target(target)
    host = urlparse(root).netloc.replace(":", "-")
    # If scoped to a path, include a slug in the filename so audits of /resources/
    # vs /blog/ vs root don't overwrite each other.
    slug = ""
    if prefix:
        slug = "_" + prefix.strip("/").replace("/", "-")
    date_str = datetime.now().strftime("%Y-%m-%d")
    return Path.cwd() / "citable-reports" / f"{host}{slug}-{date_str}.xlsx"


def _print_banner() -> None:
    console.print(render_banner(), style="bold cyan")


def _print_summary(report: AuditReport, out_path: Path) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(justify="right", style="bold")
    table.add_column()

    grade_color = {
        "A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red",
    }[report.letter_grade]
    table.add_row("Score", f"[{grade_color}]{report.overall_score:.0f}/100 ({report.letter_grade})[/{grade_color}]")

    # Category breakdown
    for cat, score in report.category_scores.items():
        if score < 0:
            table.add_row(cat, "[dim]n/a (no checks)[/dim]")
            continue
        color = "green" if score >= 70 else ("yellow" if score >= 55 else "red")
        table.add_row(cat, f"[{color}]{score:.0f}[/{color}]")

    console.print()
    console.print(Panel(table, title="Audit Summary", border_style="cyan"))

    # Top issue + recommendation
    if report.top_issue_check_id:
        top = next((r for r in report.check_results if r.check_id == report.top_issue_check_id), None)
        if top:
            console.print()
            console.print(f"[bold]Top issue:[/bold] {top.name}")
            console.print(f"  {top.message}")
            url, blurb = recommend_for(report.top_issue_check_id)
            console.print()
            console.print(f"[dim]Want help fixing this? Work-Smart.ai builds AI-citable sites for mid-market companies.[/dim]")
            console.print(f"[dim]{blurb}[/dim]")
            console.print(f"[blue underline]{url}[/blue underline]")

    console.print()
    console.print(f"[bold]Report saved:[/bold] [green]{out_path}[/green]")


async def _run_audit(target: str, pages: int, force_googlebot: bool) -> AuditReport:
    """Run crawl + checks. Live progress display."""
    root, prefix = normalize_target(target)
    display = f"{root}{prefix}" if prefix else root
    started = datetime.now().isoformat(timespec="seconds")

    report = AuditReport(domain=display, started_at=started, finished_at="")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        crawl_task = progress.add_task(f"Crawling {display}", total=None)
        report_pages, ctx = await crawl(target, max_pages=pages, force_googlebot=force_googlebot)
        progress.update(crawl_task, completed=1, total=1, description=f"Crawled {len(report_pages)} pages")

        check_task = progress.add_task("Running checks", total=1)
        results = run_all_checks(report_pages, ctx)
        progress.update(check_task, completed=1, description=f"Ran {len(results)} checks")

    report.pages = report_pages
    report.check_results = results
    report.finished_at = datetime.now().isoformat(timespec="seconds")
    finalize(report)
    return report


@app.command()
def audit(
    target: str = typer.Argument(
        ...,
        help=(
            "Target to audit. Accepts a domain or a URL with a path. "
            "Examples: `example.com`, `https://example.com`, "
            "`https://example.com/resources/` (scopes the audit to /resources/* only)."
        ),
    ),
    pages: int = typer.Option(20, "--pages", "-p", help="Maximum pages to crawl (default 20, max 100)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output xlsx path. Default: ./citable-reports/{host}{_prefix}-{date}.xlsx"),
    no_googlebot: bool = typer.Option(False, "--no-googlebot", help="Use default citable UA instead of Googlebot UA"),
    no_banner: bool = typer.Option(False, "--no-banner", help="Suppress ASCII banner (for CI usage)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress, log final summary only"),
) -> None:
    """Audit a website for AI search visibility and SEO foundations.

    Pass a domain to audit the whole site, or a URL with a path
    (like `example.com/blog/`) to scope the audit to one section.

    Outputs a 3-sheet xlsx with summary, action list, and per-page detail.
    """
    pages = max(1, min(pages, 100))
    domain = target

    if not no_banner and not quiet:
        _print_banner()

    out_path = output if output else _default_output_path(domain)

    if quiet:
        console.quiet = True

    try:
        report = asyncio.run(_run_audit(domain, pages, force_googlebot=not no_googlebot))
    except KeyboardInterrupt:
        console.print("\n[red]Audit interrupted.[/red]")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        console.print(f"\n[red]Audit failed:[/red] {e}")
        raise

    out_path = write_report(report, out_path)

    if quiet:
        console.quiet = False
        console.print(f"{out_path}")
        return

    _print_summary(report, out_path)


@app.command()
def version() -> None:
    """Print citable version."""
    console.print(f"citable v{__version__}")


@app.command()
def doctor() -> None:
    """Diagnose the current environment. Reports Python version, dependency
    versions, venv status, and writes a one-line summary you can paste into
    a bug report."""
    import platform
    import sys as _sys

    py_version = ".".join(str(x) for x in _sys.version_info[:3])
    py_ok = _sys.version_info >= (3, 10)
    in_venv = _sys.prefix != getattr(_sys, "base_prefix", _sys.prefix)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(justify="right", style="bold")
    table.add_column()

    py_color = "green" if py_ok else "red"
    table.add_row("Python", f"[{py_color}]{py_version}[/{py_color}]" + ("" if py_ok else " (need 3.10+)"))
    table.add_row("Platform", f"{platform.system()} {platform.release()} ({platform.machine()})")
    table.add_row("Venv", "[green]yes[/green]" if in_venv else "[yellow]no (recommended to use pipx or venv)[/yellow]")

    # Dependency probe
    deps = {
        "httpx": ">=0.27",
        "bs4": "beautifulsoup4>=4.12",
        "openpyxl": ">=3.1",
        "typer": ">=0.12",
        "rich": ">=13.7",
        "lxml": ">=5.0",
    }
    missing: list[str] = []
    for module, required in deps.items():
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            table.add_row(module, f"[green]{ver}[/green] (required {required})")
        except ImportError:
            missing.append(module)
            table.add_row(module, f"[red]missing[/red] (required {required})")

    console.print()
    console.print(Panel(table, title="citable doctor", border_style="cyan"))
    console.print()

    if missing:
        console.print(
            f"[red]Missing dependencies:[/red] {', '.join(missing)}\n"
            f"[dim]Reinstall citable to pull them in: pip install -e . (in a venv) or pipx install citable[/dim]"
        )
        raise typer.Exit(code=1)

    if not py_ok:
        console.print("[red]Python too old.[/red] Install Python 3.10 or newer and recreate your venv.")
        raise typer.Exit(code=1)

    if not in_venv:
        console.print(
            "[yellow]Tip:[/yellow] running outside a venv works but is fragile. "
            "Reinstall via [bold]pipx install citable[/bold] for a clean isolated install."
        )

    console.print("[green]All checks passed. Ready to audit.[/green]")
    console.print(f"[dim]citable v{__version__} · python {py_version}[/dim]")


if __name__ == "__main__":
    app()
