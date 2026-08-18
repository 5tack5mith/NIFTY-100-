"""Tests for the screener filter engine (D15/D16).

Run with: pytest tests/screener/test_engine.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "screener"))

from engine import apply_filters


def _universe():
    return pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "return_on_equity_pct": [20.0, 10.0, None, 25.0],
        "debt_to_equity": [0.5, 2.0, 0.3, 6.0],
        "is_financial_sector": [False, False, False, True],
    })


def test_apply_filters_min_threshold():
    universe = _universe()
    result = apply_filters(universe, ["min_roe_pct"], {"min_roe_pct": 15.0})
    assert sorted(result["company_id"]) == ["A", "D"]


def test_apply_filters_nan_always_fails():
    # Company C has no ROE data -- must not pass a min_roe_pct filter just
    # because NaN comparisons don't evaluate to False the way you'd hope.
    universe = _universe()
    result = apply_filters(universe, ["min_roe_pct"], {"min_roe_pct": 0.0})
    assert "C" not in list(result["company_id"])


def test_apply_filters_de_carves_out_financial_sector():
    # Company D has D/E=6.0 (would fail max_de=1.0) but is a financial-
    # sector company -- spec's D/E carve-out means it should pass anyway.
    universe = _universe()
    result = apply_filters(universe, ["max_de"], {"max_de": 1.0})
    assert "D" in list(result["company_id"])
    assert "B" not in list(result["company_id"])  # B: D/E=2.0, non-financial -- correctly excluded


def test_apply_filters_multiple_keys_are_and_combined():
    universe = _universe()
    result = apply_filters(universe, ["min_roe_pct", "max_de"], {"min_roe_pct": 15.0, "max_de": 1.0})
    # A: ROE=20 (pass), D/E=0.5 (pass) -> in
    # D: ROE=25 (pass), D/E=6.0 but financial -> in
    assert sorted(result["company_id"]) == ["A", "D"]
