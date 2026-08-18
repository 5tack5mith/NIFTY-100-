"""Tests for peer group percentile ranking (D18).

Run with: pytest tests/analytics/test_peer.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from peer import compute_peer_percentiles, RADAR_METRICS


def _universe():
    return pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "year": ["2024-03"] * 4,
        "return_on_equity_pct": [10.0, 20.0, 30.0, None],
        "computed_roce_pct": [5.0, 15.0, 25.0, 35.0],
        "net_profit_margin_pct": [1.0, 2.0, 3.0, 4.0],
        "debt_to_equity": [0.1, 0.5, 1.0, 2.0],
        "free_cash_flow_cr": [10, 20, 30, 40],
        "pat_cagr_5yr_pct": [5, 10, 15, 20],
        "revenue_cagr_5yr_pct": [5, 10, 15, 20],
        "eps_cagr_5yr_pct": [5, 10, 15, 20],
    })


def _peer_groups():
    # A, B, C in "Group1"; D alone in "Group2" -- tests that percentiles
    # are computed independently per group, not across the whole universe.
    return pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "peer_group_name": ["Group1", "Group1", "Group1", "Group2"],
    })


def test_percentile_rank_higher_is_better_orders_correctly():
    result = compute_peer_percentiles(_universe(), _peer_groups())
    roce_rows = result[(result["metric"] == "ROCE") & (result["peer_group"] == "Group1")]
    roce_rows = roce_rows.set_index("company_id")
    # A has lowest ROCE (5.0) in the group -> lowest percentile
    # C has highest ROCE (25.0) in the group -> highest percentile
    assert roce_rows.loc["A", "percentile_rank"] < roce_rows.loc["C", "percentile_rank"]


def test_percentile_rank_de_is_inverted():
    result = compute_peer_percentiles(_universe(), _peer_groups())
    de_rows = result[(result["metric"] == "D/E") & (result["peer_group"] == "Group1")].set_index("company_id")
    # A has the LOWEST D/E (0.1, least leverage -- best) -> should get the
    # HIGHEST percentile, since D/E is inverted (lower is better).
    assert de_rows.loc["A", "percentile_rank"] > de_rows.loc["C", "percentile_rank"]


def test_percentile_rank_missing_value_produces_no_row():
    # Company D has no ROE value -- should simply not appear in the ROE
    # rows for its group, rather than showing up with a NaN percentile.
    result = compute_peer_percentiles(_universe(), _peer_groups())
    group2_roe = result[(result["metric"] == "ROE") & (result["company_id"] == "D")]
    assert len(group2_roe) == 0


def test_percentile_rank_bounded_zero_to_one():
    result = compute_peer_percentiles(_universe(), _peer_groups())
    assert (result["percentile_rank"] > 0).all()
    assert (result["percentile_rank"] <= 1).all()


def test_percentile_rank_groups_are_independent():
    # D is alone in Group2 -- ranking against a group of 1 should still
    # produce a valid (100th percentile) row, not crash or produce NaN.
    # D has no ROE value in the fixture (see test_percentile_rank_missing_
    # value_produces_no_row above), so it gets 7 of the 8 metrics, not 8.
    result = compute_peer_percentiles(_universe(), _peer_groups())
    group2_rows = result[result["peer_group"] == "Group2"]
    assert len(group2_rows) == len(RADAR_METRICS) - 1
    assert (group2_rows["percentile_rank"] == 1.0).all()
