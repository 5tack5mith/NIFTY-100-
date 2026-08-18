"""Sprint 2 CAGR Engine -- Revenue, PAT, EPS growth over 3/5/10yr windows.

CAGR = (end_value / start_value)^(1/n) - 1, per spec Section 13. The
tricky part isn't the formula -- it's the edge cases, all of which come
from one root problem: CAGR is only mathematically well-behaved when the
starting value is positive. A negative starting value with a positive
ending value is a real "turnaround" story (a loss-making year followed by
recovery), not a bug, but `(end/start)^(1/n)` on a negative base with a
fractional exponent produces a complex number in general -- nonsense for a
financial metric. The spec's answer is the "turnaround flag" (R-07 in the
risk register): set a boolean flag instead of computing a number when the
base year is negative or zero, so nothing downstream ever tries to sort or
threshold-filter on a fabricated growth rate.
"""

import pandas as pd


def compute_cagr(end_value, start_value, n_years: int) -> tuple:
    """Returns (cagr_pct, turnaround_flag).

    cagr_pct is None whenever a real percentage can't be computed --
    either because a value is missing, or because start_value <= 0 (the
    turnaround case). turnaround_flag is True specifically when
    start_value <= 0 and end_value > 0 -- a genuine "went from loss/zero to
    profit" story that the CAGR number itself can't represent, but that a
    screener or dashboard should still be able to surface as "turnaround"
    rather than just "no data".
    """
    if pd.isna(end_value) or pd.isna(start_value) or n_years <= 0:
        return None, False

    if start_value <= 0:
        turnaround = end_value > 0
        return None, turnaround

    if end_value <= 0:
        # Symmetric case to the turnaround check above: a positive base
        # that ends at zero/negative (profit -> loss). (end/start) is
        # negative here, and raising a negative number to a fractional
        # power (1/n_years) is undefined for real numbers -- numpy returns
        # NaN with a RuntimeWarning rather than raising, which would have
        # silently produced a garbage CAGR value if this branch weren't
        # here. The spec only names "turnaround" (loss -> profit) as a
        # flaggable pattern, not this direction, so there's no equivalent
        # flag to set here -- just a clean None instead of a NaN.
        return None, False

    cagr_pct = ((end_value / start_value) ** (1 / n_years) - 1) * 100
    return cagr_pct, False


def cagr_for_company(annual_series: pd.Series, windows=(3, 5, 10)) -> dict:
    """Compute CAGR for one company's single metric (e.g. sales) across all
    requested windows, using the latest available year as the end point.

    annual_series must be indexed by year string ('YYYY-MM'), already
    sorted ascending -- the caller (populate_financial_ratios.py) is
    responsible for building this per-company, per-metric series from the
    joined annual frame, since this function shouldn't need to know about
    company_id or which column it's operating on.

    A window is skipped (both values None/False) rather than computed with
    a "nearest available year" substitute if the exact N-years-back row
    doesn't exist -- e.g. a company with only 8 years of history has no
    valid 10yr CAGR, full stop, rather than a CAGR computed over some other
    number of years mislabelled as "10yr". Silently substituting a
    different window would make the column lie about what it measures.
    """
    if annual_series.empty:
        return {f"cagr_{w}yr_pct": None for w in windows} | {f"turnaround_{w}yr": False for w in windows}

    # Look up the start year by its actual calendar year, not by counting
    # rows back -- real companies in this dataset have gap years (e.g.
    # EICHERMOT is missing FY2015 entirely, see Sprint 1 findings), so "10
    # rows back" and "10 calendar years back" are not the same thing.
    # Indexing by the parsed year integer (not the 'YYYY-MM' string) is
    # what lets a plain dict .get() correctly report "no row for that
    # calendar year" instead of grabbing whatever row happens to be N
    # positions away.
    by_year = {int(year_label[:4]): value for year_label, value in annual_series.items()}
    end_year_label = annual_series.index[-1]
    end_year = int(end_year_label[:4])
    end_value = annual_series.iloc[-1]

    result = {}
    for window in windows:
        start_value = by_year.get(end_year - window)
        if start_value is None:
            result[f"cagr_{window}yr_pct"] = None
            result[f"turnaround_{window}yr"] = False
            continue
        cagr_pct, turnaround = compute_cagr(end_value, start_value, window)
        result[f"cagr_{window}yr_pct"] = cagr_pct
        result[f"turnaround_{window}yr"] = turnaround

    return result
