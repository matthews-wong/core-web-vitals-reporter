"""Tests for the Core Web Vitals thresholds and classify() boundaries."""

from __future__ import annotations

import pytest

from cwvreporter.thresholds import CORE_METRICS, THRESHOLDS, Rating, classify


def test_published_threshold_values():
    # These must match Google's published Core Web Vitals guidance.
    assert (THRESHOLDS["lcp"].good_max, THRESHOLDS["lcp"].ni_max) == (2500, 4000)
    assert (THRESHOLDS["cls"].good_max, THRESHOLDS["cls"].ni_max) == (0.1, 0.25)
    assert (THRESHOLDS["inp"].good_max, THRESHOLDS["inp"].ni_max) == (200, 500)
    assert (THRESHOLDS["fcp"].good_max, THRESHOLDS["fcp"].ni_max) == (1800, 3000)
    assert (THRESHOLDS["tbt"].good_max, THRESHOLDS["tbt"].ni_max) == (200, 600)
    assert (THRESHOLDS["si"].good_max, THRESHOLDS["si"].ni_max) == (3400, 5800)


def test_core_metrics_membership():
    assert CORE_METRICS == ("lcp", "cls", "inp")


@pytest.mark.parametrize(
    "metric_id, value, expected",
    [
        # LCP boundaries (ms): good <= 2500, NI <= 4000, else poor.
        ("lcp", 2500, Rating.GOOD),
        ("lcp", 2500.01, Rating.NEEDS_IMPROVEMENT),
        ("lcp", 4000, Rating.NEEDS_IMPROVEMENT),
        ("lcp", 4000.01, Rating.POOR),
        # CLS boundaries (unitless): good <= 0.1, NI <= 0.25, else poor.
        ("cls", 0.1, Rating.GOOD),
        ("cls", 0.10001, Rating.NEEDS_IMPROVEMENT),
        ("cls", 0.25, Rating.NEEDS_IMPROVEMENT),
        ("cls", 0.25001, Rating.POOR),
        # INP boundaries (ms): good <= 200, NI <= 500, else poor.
        ("inp", 200, Rating.GOOD),
        ("inp", 200.01, Rating.NEEDS_IMPROVEMENT),
        ("inp", 500, Rating.NEEDS_IMPROVEMENT),
        ("inp", 500.01, Rating.POOR),
        # FCP boundaries (ms): good <= 1800, NI <= 3000, else poor.
        ("fcp", 1800, Rating.GOOD),
        ("fcp", 1800.01, Rating.NEEDS_IMPROVEMENT),
        ("fcp", 3000, Rating.NEEDS_IMPROVEMENT),
        ("fcp", 3000.01, Rating.POOR),
        # TBT boundaries (ms): good <= 200, NI <= 600, else poor.
        ("tbt", 200, Rating.GOOD),
        ("tbt", 200.01, Rating.NEEDS_IMPROVEMENT),
        ("tbt", 600, Rating.NEEDS_IMPROVEMENT),
        ("tbt", 600.01, Rating.POOR),
        # Speed Index boundaries (ms): good <= 3400, NI <= 5800, else poor.
        ("si", 3400, Rating.GOOD),
        ("si", 3400.01, Rating.NEEDS_IMPROVEMENT),
        ("si", 5800, Rating.NEEDS_IMPROVEMENT),
        ("si", 5800.01, Rating.POOR),
    ],
)
def test_boundary_classification(metric_id, value, expected):
    assert classify(metric_id, value) is expected


def test_zero_is_good():
    for metric_id in THRESHOLDS:
        assert classify(metric_id, 0) is Rating.GOOD


def test_large_value_is_poor():
    for metric_id in THRESHOLDS:
        assert classify(metric_id, 10_000_000) is Rating.POOR


def test_classify_unknown_metric_raises():
    with pytest.raises(KeyError):
        classify("does-not-exist", 1.0)
