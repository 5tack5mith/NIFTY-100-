"""D09 deliverable: tests for leverage & efficiency ratios (D/E, ICR, Asset Turnover).

Run with: pytest tests/kpi/test_leverage.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from ratios import debt_to_equity, interest_coverage, asset_turnover, DEBT_FREE_SENTINEL


def test_debt_to_equity_normal_case():
    assert debt_to_equity(borrowings=100, equity_capital=50, reserves=150) == 0.5


def test_debt_to_equity_debt_free_returns_zero():
    assert debt_to_equity(borrowings=0, equity_capital=50, reserves=150) == 0.0


def test_debt_to_equity_none_when_equity_non_positive():
    # equity_capital + reserves <= 0 -- no meaningful ratio to compute
    assert debt_to_equity(borrowings=100, equity_capital=50, reserves=-200) is None


def test_debt_to_equity_none_when_borrowings_missing():
    assert debt_to_equity(borrowings=None, equity_capital=50, reserves=150) is None


def test_interest_coverage_normal_case():
    # (op_profit + other_income) / interest = (100 + 20) / 30 = 4.0
    assert interest_coverage(operating_profit=100, other_income=20, interest=30) == 4.0


def test_interest_coverage_debt_free_substitution():
    assert interest_coverage(operating_profit=100, other_income=20, interest=0) == DEBT_FREE_SENTINEL


def test_interest_coverage_missing_interest_treated_as_debt_free():
    assert interest_coverage(operating_profit=100, other_income=20, interest=None) == DEBT_FREE_SENTINEL


def test_interest_coverage_missing_other_income_treated_as_zero():
    assert interest_coverage(operating_profit=100, other_income=None, interest=25) == 4.0


def test_interest_coverage_none_when_operating_profit_missing():
    assert interest_coverage(operating_profit=None, other_income=20, interest=30) is None


def test_asset_turnover_normal_case():
    assert asset_turnover(sales=200, total_assets=100) == 2.0


def test_asset_turnover_none_when_total_assets_zero():
    assert asset_turnover(sales=200, total_assets=0) is None


def test_asset_turnover_none_when_sales_missing():
    assert asset_turnover(sales=None, total_assets=100) is None
