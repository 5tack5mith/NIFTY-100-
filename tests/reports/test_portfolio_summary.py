"""Tests for the portfolio summary's trend-arrow logic, including the
scale-anomaly caveat substitution.

Run with: pytest tests/reports/test_portfolio_summary.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "reports"))

from portfolio_summary import _trend_arrow, _kpi_with_trend


def test_trend_arrow_up():
    assert _trend_arrow(120, 100) == "↑"


def test_trend_arrow_down():
    assert _trend_arrow(80, 100) == "↓"


def test_trend_arrow_flat_within_threshold():
    assert _trend_arrow(102, 100) == "→"  # +2%, under the 5% threshold


def test_trend_arrow_unknown_when_missing_data():
    assert _trend_arrow(None, 100) == "?"
    assert _trend_arrow(100, None) == "?"


def test_kpi_with_trend_shows_caveat_not_arrow_when_flagged():
    latest = pd.Series({"return_on_equity_pct": 3816.6})
    prior = pd.Series({"return_on_equity_pct": 15.0})
    flagged = {("HAL", "2024-03")}
    result = _kpi_with_trend("return_on_equity_pct", latest, prior, "HAL", "2024-03", "2021-03", flagged)
    assert "[!]" in result
    assert "↑" not in result


def test_kpi_with_trend_shows_arrow_when_not_flagged():
    latest = pd.Series({"return_on_equity_pct": 20.0})
    prior = pd.Series({"return_on_equity_pct": 15.0})
    result = _kpi_with_trend("return_on_equity_pct", latest, prior, "TCS", "2024-03", "2021-03", flagged_keys=set())
    assert "↑" in result
    assert "[!]" not in result


def test_kpi_with_trend_caveat_when_prior_year_flagged_not_latest():
    # The caveat should trigger even if only the PRIOR year is flagged --
    # comparing a clean latest year against a corrupted prior year is just
    # as misleading as the reverse.
    latest = pd.Series({"return_on_equity_pct": 20.0})
    prior = pd.Series({"return_on_equity_pct": 3000.0})
    flagged = {("LT", "2018-03")}
    result = _kpi_with_trend("return_on_equity_pct", latest, prior, "LT", "2024-03", "2018-03", flagged)
    assert "[!]" in result


def test_kpi_with_trend_non_scale_sensitive_metric_never_gets_caveat():
    latest = pd.Series({"free_cash_flow_cr": 100})
    prior = pd.Series({"free_cash_flow_cr": 50})
    flagged = {("HAL", "2024-03")}
    result = _kpi_with_trend("free_cash_flow_cr", latest, prior, "HAL", "2024-03", "2021-03", flagged, fmt="{:.0f}")
    assert "[!]" not in result
    assert "↑" in result
