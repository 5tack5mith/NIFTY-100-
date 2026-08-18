"""Tests for the ranking engine's scoring math (D17).

Run with: pytest tests/screener/test_ranking.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "screener"))

from ranking import winsorized_score, add_rankings


def test_winsorized_score_higher_is_better():
    series = pd.Series([10, 20, 30, 40, 50])
    scores = winsorized_score(series)
    # Monotonic: higher raw value -> higher score
    assert scores.is_monotonic_increasing


def test_winsorized_score_lower_is_better_inverts():
    series = pd.Series([10, 20, 30, 40, 50])
    scores = winsorized_score(series, lower_is_better=True)
    assert scores.is_monotonic_decreasing


def test_winsorized_score_clips_outliers():
    # A single extreme value should be CLIPPED to the P90 boundary, not
    # scored as some literal multiple of everyone else -- i.e. its score
    # should tie with whatever else sits at/above the P90 cutoff, rather
    # than dominating the scale on its own.
    #
    # Note on sample size: with only 10 points, a single 10000 pulls the
    # *90th percentile itself* far upward via interpolation (P90 lands
    # around 1016, since the top decile straddles [18, 10000]) -- which
    # then crushes even the second-highest value's score toward zero. This
    # is a real, small-sample limitation of P10/P90 winsorisation (not a
    # bug): it protects the middle of a reasonably sized distribution
    # (like this project's 92 companies), not necessarily its immediate
    # neighbours in a 10-point sample. Using enough points that several
    # values already sit at/near the P90 boundary avoids conflating that
    # known small-sample effect with an actual implementation bug.
    series = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 10000])
    scores = winsorized_score(series)
    p90 = series.quantile(0.90)
    # Every value at or above the P90 boundary (20 and 10000) should be
    # clipped to the same maximum score.
    at_or_above_p90 = scores[series >= p90]
    assert (at_or_above_p90 == at_or_above_p90.max()).all()


def test_winsorized_score_all_identical_gives_midpoint():
    series = pd.Series([5.0, 5.0, 5.0])
    scores = winsorized_score(series)
    assert (scores == 50.0).all()


def test_winsorized_score_preserves_nan():
    series = pd.Series([10, 20, None, 40])
    scores = winsorized_score(series)
    assert pd.isna(scores.iloc[2])


def test_add_rankings_sector_relative_differs_from_overall():
    df = pd.DataFrame({
        "broad_sector": ["IT", "IT", "Financials", "Financials", "Financials"],
        "composite_score": [90, 80, 70, 60, 50],
    })
    ranked = add_rankings(df)
    # Overall rank: 90 is #1 globally
    assert ranked.loc[ranked["composite_score"] == 90, "overall_rank"].iloc[0] == 1
    # Sector rank: within IT, 80 is #2 in-sector even though it'd be #2
    # overall too here -- check a case where the two diverge:
    # the Financials company with score 70 is #3 overall but #1 within its
    # own sector.
    row = ranked[ranked["composite_score"] == 70].iloc[0]
    assert row["overall_rank"] == 3
    assert row["sector_rank"] == 1
