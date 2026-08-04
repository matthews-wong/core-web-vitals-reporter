"""Render a :class:`~cwvreporter.parse.LighthouseReport` to console + Markdown.

Console output uses ``rich`` tables with colour-coded ratings; the Markdown
renderer produces the same information as a portable document. Both share the
formatting helpers so the two views never drift.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .parse import LighthouseReport, Metric, Opportunity
from .thresholds import THRESHOLDS, Rating

# Colour + glyph per rating, reused by the console renderer.
_RATING_STYLE: dict[Rating, tuple[str, str]] = {
    Rating.GOOD: ("green", "GOOD"),
    Rating.NEEDS_IMPROVEMENT: ("yellow", "NEEDS IMPROVEMENT"),
    Rating.POOR: ("red", "POOR"),
}

_RATING_MARKDOWN: dict[Rating, str] = {
    Rating.GOOD: "🟢 Good",
    Rating.NEEDS_IMPROVEMENT: "🟡 Needs improvement",
    Rating.POOR: "🔴 Poor",
}


def _format_value(metric: Metric) -> str:
    """Human-friendly value string, preferring Lighthouse's own display value."""
    if metric.value is None:
        return "n/a"
    if metric.display:
        return metric.display
    if metric.unit == "ms":
        seconds = metric.value / 1000
        return f"{seconds:.2f} s" if metric.value >= 1000 else f"{metric.value:.0f} ms"
    return f"{metric.value:.3f}"


def _format_savings(opportunity: Opportunity) -> str:
    """Compose a compact 'estimated savings' string for an opportunity."""
    parts: list[str] = []
    if opportunity.savings_ms:
        parts.append(f"{opportunity.savings_ms / 1000:.2f} s")
    if opportunity.savings_kib:
        parts.append(f"{opportunity.savings_kib:.0f} KiB")
    return ", ".join(parts) if parts else "—"


def _score_style(score: float | None) -> str:
    """Map a 0-100 performance score to a rich colour."""
    if score is None:
        return "white"
    if score >= 90:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def render_console(report: LighthouseReport, console: Console | None = None) -> None:
    """Print the full report to the terminal using ``rich``."""
    console = console or Console()

    score = report.performance_score
    header = Text.assemble(
        ("Core Web Vitals Report\n", "bold"),
        (f"{report.url or 'unknown URL'}\n", "cyan"),
        ("Performance score: ", "dim"),
        (f"{score:.0f}" if score is not None else "n/a", f"bold {_score_style(score)}"),
    )
    console.print(Panel(header, expand=False))

    # Metrics table.
    table = Table(title="Metrics", header_style="bold", show_lines=False)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_column("Rating")
    table.add_column("CWV", justify="center")

    for metric in report.metrics:
        if metric.rating is None:
            rating_cell = Text("n/a", style="dim")
        else:
            color, label = _RATING_STYLE[metric.rating]
            rating_cell = Text(label, style=color)
        table.add_row(
            metric.label,
            _format_value(metric),
            rating_cell,
            "★" if metric.is_core else "",
        )
    console.print(table)

    # Opportunities table.
    if report.opportunities:
        opp_table = Table(
            title="Top opportunities (estimated savings)",
            header_style="bold",
        )
        opp_table.add_column("#", justify="right")
        opp_table.add_column("Opportunity")
        opp_table.add_column("Est. savings", justify="right")
        for index, opp in enumerate(report.opportunities, start=1):
            opp_table.add_row(str(index), opp.title, _format_savings(opp))
        console.print(opp_table)
    else:
        console.print("[green]No failing opportunities found.[/green]")


def render_markdown(report: LighthouseReport) -> str:
    """Render the report to a Markdown string suitable for a file or PR comment."""
    lines: list[str] = []
    lines.append("# Core Web Vitals Report")
    lines.append("")
    lines.append(f"- **URL:** {report.url or 'unknown'}")
    if report.fetch_time:
        lines.append(f"- **Fetched:** {report.fetch_time}")
    if report.lighthouse_version:
        lines.append(f"- **Lighthouse version:** {report.lighthouse_version}")
    if report.performance_score is not None:
        lines.append(f"- **Performance score:** {report.performance_score:.0f} / 100")
    lines.append("")

    # Metrics table.
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value | Rating | Core Web Vital |")
    lines.append("| --- | --- | --- | --- |")
    for metric in report.metrics:
        rating = _RATING_MARKDOWN[metric.rating] if metric.rating else "n/a"
        core = "Yes" if metric.is_core else ""
        lines.append(f"| {metric.label} | {_format_value(metric)} | {rating} | {core} |")
    lines.append("")

    # Thresholds reference.
    lines.append("## Thresholds")
    lines.append("")
    lines.append("| Metric | Good | Needs improvement | Poor |")
    lines.append("| --- | --- | --- | --- |")
    for spec in THRESHOLDS.values():
        unit = f" {spec.unit}" if spec.unit else ""
        good = f"≤ {spec.good_max:g}{unit}"
        ni = f"{spec.good_max:g}–{spec.ni_max:g}{unit}"
        poor = f"> {spec.ni_max:g}{unit}"
        lines.append(f"| {spec.label} | {good} | {ni} | {poor} |")
    lines.append("")

    # Opportunities / recommendations.
    lines.append("## Recommendations")
    lines.append("")
    if report.opportunities:
        for index, opp in enumerate(report.opportunities, start=1):
            lines.append(f"### {index}. {opp.title}")
            savings = _format_savings(opp)
            if savings != "—":
                lines.append(f"- **Estimated savings:** {savings}")
            if opp.description:
                lines.append(f"- {opp.description.strip()}")
            lines.append("")
    else:
        lines.append("No failing opportunities were found in this report.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
