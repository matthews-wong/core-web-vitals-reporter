"""Command-line entry point for core-web-vitals-reporter.

Usage:
    core-web-vitals-reporter data/sample_lighthouse.json
    core-web-vitals-reporter report.json --markdown out.md --top 10
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .parse import load_report
from .report import render_console, render_markdown
from .thresholds import Rating


@click.command()
@click.argument("report_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--markdown",
    "markdown_out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a Markdown report to this file (also printed to stdout with --stdout-md).",
)
@click.option(
    "--stdout-md",
    is_flag=True,
    default=False,
    help="Print the Markdown report to stdout instead of the rich console view.",
)
@click.option(
    "--top",
    "top",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Number of top opportunities to surface.",
)
@click.option(
    "--fail-on-poor",
    is_flag=True,
    default=False,
    help="Exit with a non-zero status if any Core Web Vital is rated poor (useful in CI).",
)
@click.version_option(version=__version__, prog_name="core-web-vitals-reporter")
def main(
    report_path: Path,
    markdown_out: Path | None,
    stdout_md: bool,
    top: int,
    fail_on_poor: bool,
) -> None:
    """Turn a Lighthouse JSON REPORT_PATH into a focused Core Web Vitals report."""
    console = Console()

    try:
        report = load_report(report_path, max_opportunities=top)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Error:[/red] {report_path} is not valid JSON ({exc}).")
        raise SystemExit(2) from exc

    if stdout_md:
        click.echo(render_markdown(report))
    else:
        render_console(report)

    if markdown_out is not None:
        markdown_out.write_text(render_markdown(report), encoding="utf-8")
        if not stdout_md:
            console.print(f"[green]Markdown report written to[/green] {markdown_out}")

    if fail_on_poor:
        poor_core = [
            m for m in report.metrics if m.is_core and m.rating is Rating.POOR
        ]
        if poor_core:
            names = ", ".join(m.label for m in poor_core)
            console.print(f"[red]Failing:[/red] poor Core Web Vitals detected ({names}).")
            sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
