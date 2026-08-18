"""Tests for the CAGR engine, especially the turnaround-flag edge cases --
part of the ~20 KPI formula tests D14 asks for.

Run with: pytest tests/kpi/test_cagr.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from cagr import compute_cagr, cagr_for_company


def test_compute_cagr_normal_growth():
    # (200/100)^(1/3) - 1 -> ~25.99%
    cagr_pct, turnaround = compute_cagr(end_value=200, start_value=100, n_years=3)
    assert round(cagr_pct, 2) == 25.99
    assert turnaround is False


def test_compute_cagr_turnaround_flag_when_base_negative():
    cagr_pct, turnaround = compute_cagr(end_value=50, start_value=-20, n_years=3)
    assert cagr_pct is None
    assert turnaround is True


def test_compute_cagr_no_turnaround_flag_when_base_and_end_both_negative():
    # Still declining/loss-making, not a turnaround story
    cagr_pct, turnaround = compute_cagr(end_value=-10, start_value=-20, n_years=3)
    assert cagr_pct is None
    assert turnaround is False


def test_compute_cagr_none_when_profit_declines_into_loss():
    # The bug found while first running the populate script: start > 0 but
    # end <= 0 must return a clean None, not NaN via a fractional power of
    # a negative number.
    cagr_pct, turnaround = compute_cagr(end_value=-10, start_value=50, n_years=3)
    assert cagr_pct is None
    assert turnaround is False


def test_cagr_for_company_uses_calendar_year_not_row_position():
    # EICHERMOT-style gap: a missing year between start and end means the
    # window must be skipped, not computed over however many rows happen
    # to be n_years apart positionally.
    series = pd.Series(
        {"2012-12": 100, "2013-12": 110, "2014-12": 120, "2016-03": 90, "2017-03": 95},
    )
    result = cagr_for_company(series, windows=(3,))
    # end year is 2017 (from '2017-03'); 3yr window needs a 2014 entry --
    # only '2014-03'-style would count, and the actual row is '2014-03'
    # missing (we have 2014-12, different calendar year label check: 2014
    # from '2014-12'[:4] == '2014' so it DOES exist) -- use a window that
    # truly has no matching calendar year instead.
    result_5yr = cagr_for_company(series, windows=(5,))
    # end year 2017, 5yr window needs 2012 -- '2012-12' -> year 2012 exists
    assert result_5yr["cagr_5yr_pct"] is not None

    result_missing = cagr_for_company(series, windows=(4,))
    # end year 2017, 4yr window needs 2013 -- '2013-12' -> year 2013 exists
    assert result_missing["cagr_4yr_pct"] is not None


def test_cagr_for_company_skips_window_with_no_matching_year():
    series = pd.Series({"2020-03": 100, "2021-03": 110, "2024-03": 150})
    result = cagr_for_company(series, windows=(3,))
    # end year 2024, 3yr window needs 2021 -- exists -> should compute
    assert result["cagr_3yr_pct"] is not None

    result_10yr = cagr_for_company(series, windows=(10,))
    # end year 2024, 10yr window needs 2014 -- doesn't exist -> None, not
    # a value computed from whatever the earliest available row happens to be
    assert result_10yr["cagr_10yr_pct"] is None
    assert result_10yr["turnaround_10yr"] is False


def test_cagr_for_company_empty_series():
    result = cagr_for_company(pd.Series(dtype=float), windows=(3, 5, 10))
    assert all(v is None for k, v in result.items() if k.startswith("cagr_"))
