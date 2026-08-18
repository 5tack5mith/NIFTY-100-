"""Tests for KMeans clustering (Module 10.1-10.2) -- especially the
winsorization fix (a single extreme outlier must not dominate cluster
assignment) and the scale-anomaly caveat treatment.

Run with: pytest tests/analytics/test_clustering.py -v
"""

import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "analytics"))

from clustering import impute_and_scale, name_clusters, run_clustering, FEATURE_COLUMNS


def _features(n=20, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "company_id": [f"C{i}" for i in range(n)],
        "year": ["2024-03"] * n,
        "return_on_equity_pct": rng.normal(15, 5, n),
        "debt_to_equity": rng.normal(0.8, 0.3, n).clip(min=0),
        "revenue_cagr_5yr_pct": rng.normal(10, 5, n),
        "fcf_cagr_5yr_pct": rng.normal(8, 5, n),
        "net_profit_margin_pct": rng.normal(12, 4, n),
    })


def test_impute_and_scale_fills_missing_values():
    features = _features(10)
    features.loc[3, "return_on_equity_pct"] = None
    scaled, imputed_mask = impute_and_scale(features)
    assert not np.isnan(scaled).any()
    assert imputed_mask[3, 0] == True


def test_impute_and_scale_clips_extreme_outlier():
    # One wild outlier (BEL/HAL-style) shouldn't dominate the scaled
    # feature space -- after winsorization + StandardScaler, its z-score
    # magnitude should be bounded, not in the hundreds.
    features = _features(20)
    features.loc[0, "return_on_equity_pct"] = 5000.0  # BEL-scale corruption
    scaled, _ = impute_and_scale(features)
    roe_col_idx = FEATURE_COLUMNS.index("return_on_equity_pct")
    assert abs(scaled[0, roe_col_idx]) < 10  # a raw StandardScaler (no winsorization) would put this at 50+


def test_name_clusters_assigns_all_five_archetypes_uniquely():
    centroids = pd.DataFrame({
        "return_on_equity_pct": [30, 5, 12, 18, 10],
        "debt_to_equity": [1.0, 2.0, 0.1, 1.5, 3.0],
        "revenue_cagr_5yr_pct": [25, -5, 5, 30, 8],
        "fcf_cagr_5yr_pct": [20, -10, 5, 15, 3],
        "net_profit_margin_pct": [18, 2, 10, 12, 8],
    }, index=[0, 1, 2, 3, 4])
    names = name_clusters(centroids)
    assert len(names) == 5
    assert len(set(names.values())) == 5  # every archetype used exactly once
    assert set(names.values()) == {"High-Quality Growth", "Defensive Dividend", "Value Cyclicals", "Distressed", "Emerging Growth"}


def test_run_clustering_flags_scale_sensitive_outlier():
    features = _features(20)
    features.loc[0, "company_id"] = "HAL"
    features.loc[0, "year"] = "2024-03"
    features.loc[0, "return_on_equity_pct"] = 3800.0
    flagged_keys = {("HAL", "2024-03")}

    result, centroids_df = run_clustering(features, flagged_keys)
    hal_row = result[result["company_id"] == "HAL"].iloc[0]
    assert hal_row["data_quality_caveat"] == True
    assert "UNRELIABLE" in hal_row["cluster_name_display"]

    # A company NOT in the flagged set must never get the caveat, even if
    # it happens to land in the same cluster as HAL.
    other_row = result[result["company_id"] != "HAL"].iloc[0]
    assert other_row["data_quality_caveat"] == False
    assert "UNRELIABLE" not in other_row["cluster_name_display"]


def test_run_clustering_assigns_every_company_no_nulls():
    features = _features(30)
    features.loc[5, "fcf_cagr_5yr_pct"] = None  # missing feature, like ATGL
    result, _ = run_clustering(features, flagged_keys=set())
    assert result["cluster_id"].isna().sum() == 0
    assert len(result) == 30
