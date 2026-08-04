"""Core Web Vitals thresholds and the classification logic.

The threshold values match Google's published Core Web Vitals guidance
(web.dev / PageSpeed Insights). Boundaries are inclusive of the "good" and
"needs-improvement" upper bounds:

    good:               metric <= good_max
    needs-improvement:  good_max < metric <= ni_max
    poor:               metric > ni_max

All time-based metrics are expressed in milliseconds; CLS is unitless.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Rating(str, Enum):
    """Classification bucket for a single metric."""

    GOOD = "good"
    NEEDS_IMPROVEMENT = "needs-improvement"
    POOR = "poor"


@dataclass(frozen=True)
class Threshold:
    """A metric's good/needs-improvement boundaries.

    ``good_max`` is the inclusive upper bound of the "good" band and ``ni_max``
    is the inclusive upper bound of the "needs-improvement" band. ``unit`` and
    ``label`` are carried along purely for presentation.
    """

    label: str
    good_max: float
    ni_max: float
    unit: str

    def classify(self, value: float) -> Rating:
        """Classify a raw metric value into a :class:`Rating`."""
        if value <= self.good_max:
            return Rating.GOOD
        if value <= self.ni_max:
            return Rating.NEEDS_IMPROVEMENT
        return Rating.POOR


# Thresholds keyed by the internal metric id used throughout the package.
# Sources: https://web.dev/articles/lcp, /cls, /inp, /fcp, /tbt, and the
# Lighthouse performance scoring guide for Speed Index.
THRESHOLDS: dict[str, Threshold] = {
    # Core Web Vitals
    "lcp": Threshold("Largest Contentful Paint", good_max=2500, ni_max=4000, unit="ms"),
    "cls": Threshold("Cumulative Layout Shift", good_max=0.1, ni_max=0.25, unit=""),
    "inp": Threshold("Interaction to Next Paint", good_max=200, ni_max=500, unit="ms"),
    # Supporting lab metrics
    "fcp": Threshold("First Contentful Paint", good_max=1800, ni_max=3000, unit="ms"),
    "tbt": Threshold("Total Blocking Time", good_max=200, ni_max=600, unit="ms"),
    "si": Threshold("Speed Index", good_max=3400, ni_max=5800, unit="ms"),
}

# The three metrics that are Core Web Vitals proper.
CORE_METRICS: tuple[str, ...] = ("lcp", "cls", "inp")


def classify(metric_id: str, value: float) -> Rating:
    """Classify ``value`` for the metric identified by ``metric_id``.

    Raises:
        KeyError: if ``metric_id`` is not a known metric.
    """
    return THRESHOLDS[metric_id].classify(value)
