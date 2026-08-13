"""Tests for the CLI entry point.

Covers the documented invocation contract and the ``--fail-on-poor`` pass/fail
aggregation across Core Web Vitals, using Click's in-memory runner (which is
encoding-agnostic, unlike a real terminal's stdout)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cwvreporter.cli import main

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_lighthouse.json"


def _write_report(tmp_path: Path, audits: dict) -> Path:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"audits": audits}), encoding="utf-8")
    return path


def test_positional_path_renders_console():
    # The README's documented invocation: a positional Lighthouse JSON path.
    result = CliRunner().invoke(main, [str(SAMPLE)])
    assert result.exit_code == 0
    assert "Core Web Vitals Report" in result.output


def test_unknown_input_option_rejected():
    # Guards against the old, wrong README examples (`--input`, `--format`).
    result = CliRunner().invoke(main, ["--input", str(SAMPLE)])
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_stdout_md_emits_markdown():
    result = CliRunner().invoke(main, [str(SAMPLE), "--stdout-md"])
    assert result.exit_code == 0
    assert result.output.startswith("# Core Web Vitals Report")
    assert "## Metrics" in result.output


def test_fail_on_poor_exits_nonzero_when_core_metric_poor(tmp_path):
    # LCP 4520 ms is poor -> a poor Core Web Vital must fail the run.
    path = _write_report(
        tmp_path,
        {
            "largest-contentful-paint": {"numericValue": 4520.0},
            "cumulative-layout-shift": {"numericValue": 0.05},
            "interaction-to-next-paint": {"numericValue": 150.0},
        },
    )
    result = CliRunner().invoke(main, [str(path), "--fail-on-poor"])
    assert result.exit_code == 1
    assert "poor Core Web Vitals detected" in result.output


def test_fail_on_poor_passes_when_no_core_metric_poor(tmp_path):
    # All core metrics good/needs-improvement -> the run must succeed.
    path = _write_report(
        tmp_path,
        {
            "largest-contentful-paint": {"numericValue": 2400.0},  # good
            "cumulative-layout-shift": {"numericValue": 0.2},       # needs-improvement
            "interaction-to-next-paint": {"numericValue": 150.0},   # good
        },
    )
    result = CliRunner().invoke(main, [str(path), "--fail-on-poor"])
    assert result.exit_code == 0


def test_fail_on_poor_ignores_non_core_poor(tmp_path):
    # A poor *supporting* metric (TBT) must not fail the run; only core metrics do.
    path = _write_report(
        tmp_path,
        {
            "largest-contentful-paint": {"numericValue": 2000.0},  # good
            "cumulative-layout-shift": {"numericValue": 0.05},     # good
            "interaction-to-next-paint": {"numericValue": 150.0},  # good
            "total-blocking-time": {"numericValue": 1200.0},       # poor, but not core
        },
    )
    result = CliRunner().invoke(main, [str(path), "--fail-on-poor"])
    assert result.exit_code == 0
