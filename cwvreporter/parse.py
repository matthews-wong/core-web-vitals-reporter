"""Extract Core Web Vitals metrics and failing audits from a Lighthouse JSON.

Lighthouse reports are large and their shape drifts between versions, so every
lookup here is defensive: missing keys yield ``None`` rather than raising. The
public surface is two dataclasses (:class:`Metric`, :class:`Opportunity`),
their container :class:`LighthouseReport`, and :func:`parse_report`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .thresholds import THRESHOLDS, Rating

# Maps our internal metric ids to the Lighthouse audit ids that carry the
# numericValue we care about.
_AUDIT_IDS: dict[str, str] = {
    "lcp": "largest-contentful-paint",
    "cls": "cumulative-layout-shift",
    # INP is reported by newer Lighthouse under this audit; fall back handled below.
    "inp": "interaction-to-next-paint",
    "fcp": "first-contentful-paint",
    "tbt": "total-blocking-time",
    "si": "speed-index",
}

# Older reports expose Experimental INP under a different id; try these in order.
_INP_FALLBACK_IDS: tuple[str, ...] = (
    "interaction-to-next-paint",
    "experimental-interaction-to-next-paint",
)


@dataclass(frozen=True)
class Metric:
    """A single extracted metric and its classification.

    ``value`` is the raw numeric value (milliseconds for timings, unitless for
    CLS). ``display`` is Lighthouse's human-formatted string when available.
    ``rating`` is ``None`` only when the value could not be found.
    """

    metric_id: str
    label: str
    value: float | None
    unit: str
    display: str | None
    rating: Rating | None
    is_core: bool

    @property
    def found(self) -> bool:
        """True when a numeric value was extracted for this metric."""
        return self.value is not None


@dataclass(frozen=True)
class Opportunity:
    """A failing/underperforming audit worth acting on.

    ``savings_ms`` and ``savings_bytes`` are best-effort estimates pulled from
    the audit's ``details.overallSavingsMs`` / ``overallSavingsBytes`` and may
    be ``None``.
    """

    audit_id: str
    title: str
    description: str
    score: float | None
    savings_ms: float | None
    savings_bytes: float | None

    @property
    def savings_kib(self) -> float | None:
        """Byte savings expressed in KiB, or ``None`` if unknown."""
        if self.savings_bytes is None:
            return None
        return self.savings_bytes / 1024


@dataclass
class LighthouseReport:
    """Structured view over the pieces of a Lighthouse report we care about."""

    url: str | None
    fetch_time: str | None
    lighthouse_version: str | None
    performance_score: float | None
    metrics: list[Metric] = field(default_factory=list)
    opportunities: list[Opportunity] = field(default_factory=list)

    def metric(self, metric_id: str) -> Metric | None:
        """Return the extracted metric with ``metric_id``, if present."""
        return next((m for m in self.metrics if m.metric_id == metric_id), None)


def _safe_get(mapping: Any, *keys: str) -> Any:
    """Walk a chain of dict keys, returning ``None`` on any miss."""
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_numeric(audit: dict[str, Any] | None) -> float | None:
    """Pull the numericValue from an audit, tolerating absence/None."""
    if not isinstance(audit, dict):
        return None
    value = audit.get("numericValue")
    return float(value) if isinstance(value, (int, float)) else None


def _find_audit(audits: dict[str, Any], metric_id: str) -> dict[str, Any] | None:
    """Locate the audit object backing ``metric_id``, honouring INP fallbacks."""
    if metric_id == "inp":
        for candidate in _INP_FALLBACK_IDS:
            audit = audits.get(candidate)
            if isinstance(audit, dict) and audit.get("numericValue") is not None:
                return audit
        return None
    return audits.get(_AUDIT_IDS[metric_id])


def _extract_metrics(audits: dict[str, Any]) -> list[Metric]:
    """Build the ordered list of metrics from the audits block."""
    from .thresholds import CORE_METRICS

    metrics: list[Metric] = []
    for metric_id, spec in THRESHOLDS.items():
        audit = _find_audit(audits, metric_id)
        value = _extract_numeric(audit)
        rating = spec.classify(value) if value is not None else None
        display = audit.get("displayValue") if isinstance(audit, dict) else None
        metrics.append(
            Metric(
                metric_id=metric_id,
                label=spec.label,
                value=value,
                unit=spec.unit,
                display=display,
                rating=rating,
                is_core=metric_id in CORE_METRICS,
            )
        )
    return metrics


def _extract_opportunities(audits: dict[str, Any], limit: int) -> list[Opportunity]:
    """Collect failing audits ranked by estimated time savings.

    An audit is considered actionable when it has a numeric score below 1.0 or
    exposes an ``overallSavingsMs``. We rank by estimated ms saved so the most
    impactful fixes float to the top.
    """
    opportunities: list[Opportunity] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict):
            continue
        score = audit.get("score")
        details = audit.get("details") if isinstance(audit.get("details"), dict) else {}
        savings_ms = details.get("overallSavingsMs")
        savings_bytes = details.get("overallSavingsBytes")

        has_savings = isinstance(savings_ms, (int, float)) and savings_ms > 0
        is_failing = isinstance(score, (int, float)) and score < 1.0

        # Skip the metric audits themselves and anything that is passing cleanly.
        if audit_id in _AUDIT_IDS.values():
            continue
        if not (has_savings or is_failing):
            continue

        opportunities.append(
            Opportunity(
                audit_id=audit_id,
                title=str(audit.get("title", audit_id)),
                description=str(audit.get("description", "")),
                score=float(score) if isinstance(score, (int, float)) else None,
                savings_ms=float(savings_ms) if isinstance(savings_ms, (int, float)) else None,
                savings_bytes=(
                    float(savings_bytes) if isinstance(savings_bytes, (int, float)) else None
                ),
            )
        )

    # Rank: largest time savings first, then lowest score, then title.
    opportunities.sort(
        key=lambda o: (
            -(o.savings_ms or 0.0),
            o.score if o.score is not None else 1.0,
            o.title,
        )
    )
    return opportunities[:limit]


def parse_report(data: dict[str, Any], *, max_opportunities: int = 5) -> LighthouseReport:
    """Parse a decoded Lighthouse JSON ``dict`` into a :class:`LighthouseReport`.

    Every field is optional: an empty or partial report yields a report object
    with ``None``/empty values rather than an exception.
    """
    audits = _safe_get(data, "audits") or {}
    if not isinstance(audits, dict):
        audits = {}

    perf_score = _safe_get(data, "categories", "performance", "score")

    return LighthouseReport(
        url=data.get("finalUrl") or data.get("requestedUrl") or _safe_get(data, "finalDisplayedUrl"),
        fetch_time=data.get("fetchTime"),
        lighthouse_version=data.get("lighthouseVersion"),
        performance_score=(
            float(perf_score) * 100 if isinstance(perf_score, (int, float)) else None
        ),
        metrics=_extract_metrics(audits),
        opportunities=_extract_opportunities(audits, max_opportunities),
    )


def load_report(path: str | Path, *, max_opportunities: int = 5) -> LighthouseReport:
    """Read a Lighthouse JSON file from ``path`` and parse it.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        json.JSONDecodeError: if the file is not valid JSON.
    """
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return parse_report(data, max_opportunities=max_opportunities)
