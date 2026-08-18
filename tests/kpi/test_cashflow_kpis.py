"""Tests for cash flow KPIs and the capital allocation classifier -- part of
the ~20 KPI formula tests D14 asks for.

Run with: pytest tests/kpi/test_cashflow_kpis.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cashflow_kpis import (
    free_cash_flow, capex_intensity, cfo_quality_score,
    fcf_conversion_rate, classify_capital_allocation,
)


def test_free_cash_flow_normal_case():
    assert free_cash_flow(operating_activity=100, investing_activity=-40) == 60


def test_free_cash_flow_negative_allowed():
    assert free_cash_flow(operating_activity=10, investing_activity=-40) == -30


def test_capex_intensity_normal_case():
    assert capex_intensity(investing_activity=-8, sales=100) == 8.0


def test_capex_intensity_none_when_sales_zero():
    assert capex_intensity(investing_activity=-8, sales=0) is None


def test_cfo_quality_score_high_quality():
    assert cfo_quality_score(operating_activity=120, net_profit=100) == 1.2


def test_cfo_quality_score_none_when_net_profit_zero():
    assert cfo_quality_score(operating_activity=120, net_profit=0) is None


def test_fcf_conversion_rate_normal_case():
    assert fcf_conversion_rate(fcf=60, operating_profit=100) == 60.0


def test_fcf_conversion_rate_none_when_operating_profit_zero():
    assert fcf_conversion_rate(fcf=60, operating_profit=0) is None


def test_classify_capital_allocation_reinvestor():
    # CFO>0, CFI<0, CFF<0, and CFO/PAT > 1.0 -> Reinvestor
    label = classify_capital_allocation(cfo=150, cfi=-50, cff=-30, net_profit=100)
    assert label == "Reinvestor"


def test_classify_capital_allocation_shareholder_returns():
    # Same sign pattern as Reinvestor but CFO/PAT <= 1.0
    label = classify_capital_allocation(cfo=80, cfi=-50, cff=-30, net_profit=100)
    assert label == "Shareholder Returns"


def test_classify_capital_allocation_distress():
    # CFO<0, CFF>0 -- raising funds to cover an operating shortfall
    label = classify_capital_allocation(cfo=-20, cfi=-10, cff=40)
    assert label == "Distress"


def test_classify_capital_allocation_cash_burn():
    label = classify_capital_allocation(cfo=-20, cfi=-10, cff=-5)
    assert label == "Cash Burn"


def test_classify_capital_allocation_all_eight_sign_combinations_are_classified():
    # Every one of the 2^3 = 8 possible sign combinations must resolve to
    # a real label, never fall through to "Unknown"/"Unclassified" --
    # this is the check that would catch a gap in the hand-enumerated
    # if/elif chain in classify_capital_allocation().
    for cfo in (100, -100):
        for cfi in (100, -100):
            for cff in (100, -100):
                label = classify_capital_allocation(cfo, cfi, cff, net_profit=50)
                assert label not in ("Unknown", "Unclassified"), (cfo, cfi, cff, label)
