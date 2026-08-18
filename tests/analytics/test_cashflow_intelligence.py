"""Tests for the Cash Flow Intelligence module (Module 7).

Run with: pytest tests/analytics/test_cashflow_intelligence.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cashflow_intelligence import (
    cfo_quality_label, capex_intensity_label, fcf_conversion_label,
    detect_deleveraging, detect_distress,
)


def test_cfo_quality_label_high_quality():
    assert cfo_quality_label(1.5) == "High Quality Earnings"


def test_cfo_quality_label_accrual_risk():
    assert cfo_quality_label(0.3) == "Accrual Risk"


def test_cfo_quality_label_moderate():
    assert cfo_quality_label(0.7) == "Moderate"


def test_cfo_quality_label_none():
    assert cfo_quality_label(None) == "Insufficient Data"


def test_capex_intensity_label_asset_light():
    assert capex_intensity_label(2.0) == "Asset-Light"


def test_capex_intensity_label_capital_intensive():
    assert capex_intensity_label(10.0) == "Capital Intensive"


def test_fcf_conversion_label_efficient():
    assert fcf_conversion_label(70.0) == "Efficient"


def test_fcf_conversion_label_capex_heavy():
    assert fcf_conversion_label(20.0) == "CapEx Heavy"


def test_detect_deleveraging_true_case():
    cf = pd.DataFrame({"year": ["2023-03", "2024-03"], "financing_activity": [-5, -10]})
    bs = pd.DataFrame({"year": ["2023-03", "2024-03"], "borrowings": [100, 80]})
    assert detect_deleveraging(cf, bs) == True


def test_detect_deleveraging_false_when_borrowings_increased():
    cf = pd.DataFrame({"year": ["2023-03", "2024-03"], "financing_activity": [-5, -10]})
    bs = pd.DataFrame({"year": ["2023-03", "2024-03"], "borrowings": [80, 100]})
    assert detect_deleveraging(cf, bs) == False


def test_detect_deleveraging_false_when_cff_positive():
    cf = pd.DataFrame({"year": ["2023-03", "2024-03"], "financing_activity": [5, 10]})
    bs = pd.DataFrame({"year": ["2023-03", "2024-03"], "borrowings": [100, 80]})
    assert detect_deleveraging(cf, bs) == False


def test_detect_deleveraging_false_with_insufficient_history():
    cf = pd.DataFrame({"year": ["2024-03"], "financing_activity": [-10]})
    bs = pd.DataFrame({"year": ["2024-03"], "borrowings": [80]})
    assert detect_deleveraging(cf, bs) == False


def test_detect_distress_true_case():
    cf = pd.DataFrame({"year": ["2024-03"], "operating_activity": [-20], "financing_activity": [30]})
    assert detect_distress(cf) == True


def test_detect_distress_false_when_cfo_positive():
    cf = pd.DataFrame({"year": ["2024-03"], "operating_activity": [20], "financing_activity": [30]})
    assert detect_distress(cf) == False
