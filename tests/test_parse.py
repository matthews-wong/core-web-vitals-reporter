"""Tests for metric/audit extraction from a Lighthouse JSON report."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwvreporter.parse import load_report, parse_report
from cwvreporter.thresholds import Rating

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_lighthouse.json"


@pytest.fixture(scope="module")
def report():
    return load_report(SAMPLE)


def test_top_level_fields(report):
    assert report.url == "https://example.com/"
    assert report.lighthouse_version == "11.4.0"
    # categories.performance.score is 0.62 -> scaled to 62.
    assert report.performance_score == pytest.approx(62.0)


def test_all_thresholded_metrics_present(report):
    ids = {m.metric_id for m in report.metrics}
    assert ids == {"lcp", "cls", "inp", "fcp", "tbt", "si"}


def test_metric_values_extracted(report):
    assert report.metric("lcp").value == pytest.approx(4520.0)
    assert report.metric("cls").value == pytest.approx(0.052)
    assert report.metric("inp").value == pytest.approx(348.0)
    assert report.metric("fcp").value == pytest.approx(1620.0)
    assert report.metric("tbt").value == pytest.approx(782.0)
    assert report.metric("si").value == pytest.approx(4180.0)


def test_sample_ratings(report):
    assert report.metric("lcp").rating is Rating.POOR
    assert report.metric("cls").rating is Rating.GOOD
    assert report.metric("inp").rating is Rating.NEEDS_IMPROVEMENT
    assert report.metric("fcp").rating is Rating.GOOD
    assert report.metric("tbt").rating is Rating.POOR
    assert report.metric("si").rating is Rating.NEEDS_IMPROVEMENT


def test_core_metrics_flagged(report):
    core = {m.metric_id for m in report.metrics if m.is_core}
    assert core == {"lcp", "cls", "inp"}


def test_opportunities_ranked_by_savings(report):
    assert report.opportunities, "expected at least one opportunity"
    savings = [o.savings_ms or 0 for o in report.opportunities]
    assert savings == sorted(savings, reverse=True)
    # Highest-savings opportunity in the sample is render-blocking resources.
    assert report.opportunities[0].audit_id == "render-blocking-resources"


def test_metric_audits_excluded_from_opportunities(report):
    audit_ids = {o.audit_id for o in report.opportunities}
    assert "largest-contentful-paint" not in audit_ids
    assert "total-blocking-time" not in audit_ids


def test_passing_audits_excluded(report):
    audit_ids = {o.audit_id for o in report.opportunities}
    assert "color-contrast" not in audit_ids
    assert "viewport" not in audit_ids


def test_savings_kib_conversion(report):
    top = report.opportunities[0]
    assert top.savings_bytes == pytest.approx(96000)
    assert top.savings_kib == pytest.approx(96000 / 1024)


def test_tolerant_of_empty_report():
    report = parse_report({})
    assert report.url is None
    assert report.performance_score is None
    assert report.opportunities == []
    # All metrics present but unfound / unrated.
    assert all(m.value is None and m.rating is None for m in report.metrics)


def test_tolerant_of_partial_audits():
    data = {"audits": {"largest-contentful-paint": {"numericValue": 3000.0}}}
    report = parse_report(data)
    lcp = report.metric("lcp")
    assert lcp.value == pytest.approx(3000.0)
    assert lcp.rating is Rating.NEEDS_IMPROVEMENT
    assert report.metric("inp").found is False


def test_inp_experimental_fallback():
    data = {
        "audits": {
            "experimental-interaction-to-next-paint": {"numericValue": 120.0}
        }
    }
    report = parse_report(data)
    assert report.metric("inp").value == pytest.approx(120.0)
    assert report.metric("inp").rating is Rating.GOOD
