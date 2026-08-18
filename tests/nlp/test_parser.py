"""Tests for the analysis.xlsx text parser (Module 9.1 + 9.5).

Run with: pytest tests/nlp/test_parser.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "nlp"))

from parser import parse_analysis_text, build_analysis_parsed, CROSS_VALIDATION_THRESHOLD_PCT


def test_parse_analysis_text_standard_format():
    assert parse_analysis_text("10 Years: 21%") == [(10, 21.0)]


def test_parse_analysis_text_no_colon():
    assert parse_analysis_text("5 Years 6%") == [(5, 6.0)]


def test_parse_analysis_text_singular_year():
    assert parse_analysis_text("1 Year: 13%") == [(1, 13.0)]


def test_parse_analysis_text_decimal_value():
    assert parse_analysis_text("3 Years: 4.5%") == [(3, 4.5)]


def test_parse_analysis_text_extra_whitespace():
    assert parse_analysis_text("10  Years:   15%") == [(10, 15.0)]


def test_parse_analysis_text_none_input():
    assert parse_analysis_text(None) == []


def test_parse_analysis_text_unparseable():
    assert parse_analysis_text("N/A") == []


def test_build_analysis_parsed_flags_large_divergence():
    analysis_df = pd.DataFrame({
        "company_id": ["TCS"],
        "compounded_sales_growth": ["3 Years: 50%"],  # wildly off from real growth
        "compounded_profit_growth": [None],
        "stock_price_cagr": [None],
        "roe": [None],
    })
    pl_df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "TCS", "TCS"],
        "year": ["2021-03", "2022-03", "2023-03", "2024-03"],
        "sales": [100, 105, 110, 115],  # ~5% CAGR, not 50%
        "net_profit": [10, 11, 12, 13],
    })
    parsed = build_analysis_parsed(analysis_df, pl_df)
    row = parsed[parsed["metric_type"] == "Revenue Growth"].iloc[0]
    assert row["divergence_pct"] > CROSS_VALIDATION_THRESHOLD_PCT
    assert row["cross_validation_flag"] is True or row["cross_validation_flag"] == True


def test_build_analysis_parsed_no_flag_when_close():
    analysis_df = pd.DataFrame({
        "company_id": ["TCS"],
        "compounded_sales_growth": ["3 Years: 5%"],
        "compounded_profit_growth": [None],
        "stock_price_cagr": [None],
        "roe": [None],
    })
    pl_df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "TCS", "TCS"],
        "year": ["2021-03", "2022-03", "2023-03", "2024-03"],
        "sales": [100, 105, 110, 115],
        "net_profit": [10, 11, 12, 13],
    })
    parsed = build_analysis_parsed(analysis_df, pl_df)
    row = parsed[parsed["metric_type"] == "Revenue Growth"].iloc[0]
    assert row["cross_validation_flag"] is False or row["cross_validation_flag"] == False


def test_build_analysis_parsed_stock_price_and_roe_not_cross_validated():
    # These two metric types have no Ratio Engine equivalent wired up
    # (see module docstring) -- computed_cagr_pct should stay None/NaN.
    analysis_df = pd.DataFrame({
        "company_id": ["TCS"],
        "compounded_sales_growth": [None],
        "compounded_profit_growth": [None],
        "stock_price_cagr": ["5 Years: 20%"],
        "roe": ["5 Years: 15%"],
    })
    pl_df = pd.DataFrame({"company_id": [], "year": [], "sales": [], "net_profit": []})
    parsed = build_analysis_parsed(analysis_df, pl_df)
    assert parsed["computed_cagr_pct"].isna().all()
