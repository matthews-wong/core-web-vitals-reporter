"""core-web-vitals-reporter.

A small, fully offline CLI that turns a Lighthouse JSON report into a focused
Core Web Vitals report: it extracts the key metrics, classifies each against
the published CWV thresholds, and surfaces the top failing opportunities.
"""

__version__ = "0.1.0"
