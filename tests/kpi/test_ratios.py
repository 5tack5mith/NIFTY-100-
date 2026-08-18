"""Tests for profitability & returns ratios (NPM, OPM, ROE, ROCE) and the
join helper -- part of the ~20 KPI formula tests D14 asks for.

Run with: pytest tests/kpi/test_ratios.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from ratios import (
    build_annual_frame, net_profit_margin, operating_profit_margin,
    opm_cross_check_flag, return_on_equity, return_on_capital,
    book_value_per_share,
)


def test_net_profit_margin_normal_case():
    assert net_profit_margin(net_profit=20, sales=100) == 20.0


def test_net_profit_margin_negative_allowed():
    assert net_profit_margin(net_profit=-10, sales=100) == -10.0


def test_net_profit_margin_none_when_sales_zero():
    assert net_profit_margin(net_profit=20, sales=0) is None


def test_operating_profit_margin_normal_case():
    assert operating_profit_margin(operating_profit=25, sales=100) == 25.0


def test_opm_cross_check_flag_within_tolerance():
    assert opm_cross_check_flag(computed_opm=25.4, stated_opm_percentage=26.0) is False


def test_opm_cross_check_flag_exceeds_tolerance():
    assert opm_cross_check_flag(computed_opm=25.0, stated_opm_percentage=27.0) is True


def test_return_on_equity_normal_case():
    assert return_on_equity(net_profit=50, equity_capital=100, reserves=400) == 10.0


def test_return_on_equity_none_when_equity_non_positive():
    assert return_on_equity(net_profit=50, equity_capital=100, reserves=-200) is None


def test_return_on_capital_normal_case():
    # EBIT = operating_profit - depreciation = 100 - 20 = 80
    # capital employed = equity + reserves + borrowings = 100 + 300 + 100 = 500
    # ROCE = 80 / 500 * 100 = 16.0
    roce = return_on_capital(
        operating_profit=100, depreciation=20, equity_capital=100,
        reserves=300, borrowings=100, is_financial_sector=False,
    )
    assert roce == 16.0


def test_return_on_capital_none_when_capital_employed_non_positive():
    roce = return_on_capital(
        operating_profit=100, depreciation=20, equity_capital=100,
        reserves=-300, borrowings=100, is_financial_sector=False,
    )
    assert roce is None


def test_book_value_per_share_normal_case():
    # share_count = equity_capital / face_value = 100 / 10 = 10
    # BVPS = (equity_capital + reserves) / share_count = (100 + 400) / 10 = 50
    assert book_value_per_share(equity_capital=100, reserves=400, face_value=10) == 50.0


def test_book_value_per_share_none_when_face_value_missing():
    # Real case found in Sprint 1: companies.face_value has one genuine
    # null (TVSMOTOR) -- this must not crash the ratio engine.
    assert book_value_per_share(equity_capital=100, reserves=400, face_value=None) is None


def test_build_annual_frame_joins_on_company_id_and_year():
    pl = pd.DataFrame({"id": [1, 2], "company_id": ["TCS", "TCS"], "year": ["2023-03", "2024-03"], "sales": [100, 120]})
    bs = pd.DataFrame({"id": [1, 2, 3], "company_id": ["TCS", "TCS", "TCS"], "year": ["2023-03", "2024-03", "2024-09"], "total_assets": [500, 600, 650]})
    cf = pd.DataFrame({"id": [1], "company_id": ["TCS"], "year": ["2023-03"], "operating_activity": [50]})

    frame = build_annual_frame(pl, bs, cf)

    # Only P&L's 2 years should appear -- the BS-only 2024-09 row (no
    # matching P&L year, exactly the real September-snapshot pattern found
    # in Sprint 1) must NOT silently attach to some other year's P&L row.
    assert sorted(frame["year"]) == ["2023-03", "2024-03"]
    assert frame.set_index("year").loc["2023-03", "total_assets"] == 500
    assert frame.set_index("year").loc["2024-03", "total_assets"] == 600
    # cashflow has no 2024-03 row for TCS -- that ratio input should be
    # NaN, not silently dropped or backfilled from another year.
    assert pd.isna(frame.set_index("year").loc["2024-03", "operating_activity"])
