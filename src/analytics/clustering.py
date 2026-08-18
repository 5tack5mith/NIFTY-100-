"""Sprint 6, Day 36-37: KMeans clustering (Module 10.1-10.3).

Features per spec 10.1: ROE, D/E, Revenue CAGR (5yr), FCF CAGR (5yr), OPM.
StandardScaler + KMeans(n=5), elbow method to validate k=5 is reasonable
(not to pick a different k -- spec fixes n=5), cluster profiling into the
5 named archetypes spec 10.2 lists (High-Quality Growth, Defensive
Dividend, Value Cyclicals, Distressed, Emerging Growth).

CRITICAL DATA-QUALITY NOTE (per the Sprint 6 kickoff instructions): 2 of
the 5 clustering features -- ROE and D/E -- are exactly the scale-sensitive
metrics Sprint 2 found corrupted for BEL/HAL/INDIGO/LT in certain years.
KMeans has no concept of "this input might be garbage" -- it will place a
company with ROE=4744% into whichever cluster centroid is nearest that
absurd value, which tells you nothing about the company's real business
profile. Rather than silently including these companies as if their
cluster assignment means the same thing as everyone else's,
cluster_labels.csv gets an explicit data_quality_caveat column, and the
cluster_name for an affected row is suffixed with a warning rather than
presented as a clean assignment.

Spec 10.2 also names "Correlation matrix heatmap" in the Day 36-37 task
text -- built here too. Outlier detection (10.4) and portfolio statistics
(10.5) are NOT built: neither appears in the Day 36-37 task description or
the Section 17 deliverables checklist (only cluster_labels.csv is a
numbered deliverable, D-19) -- same "day-table + deliverables checklist
over the full module feature list" scoping followed every prior sprint.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
N_CLUSTERS = 5
FEATURE_COLUMNS = ["return_on_equity_pct", "debt_to_equity", "revenue_cagr_5yr_pct", "fcf_cagr_5yr_pct", "net_profit_margin_pct"]
SCALE_SENSITIVE_FEATURES = {"return_on_equity_pct", "debt_to_equity"}


def build_feature_frame(fr_latest: pd.DataFrame, cagr_df: pd.DataFrame) -> pd.DataFrame:
    """One row per company with the 5 clustering features, latest year.

    revenue_cagr_5yr_pct and fcf_cagr_5yr_pct aren't financial_ratios
    columns (see Sprint 2/5 notes on why CAGR isn't persisted) -- passed
    in separately, computed by the caller the same way every other module
    computes them (src/analytics/cagr.py).
    """
    merged = fr_latest.merge(cagr_df, on="company_id", how="left")
    return merged[["company_id", "year"] + FEATURE_COLUMNS]


def impute_and_scale(features: pd.DataFrame) -> tuple:
    """Median imputation, then P5/P95 winsorization, then StandardScaler.

    AC-15 requires ALL 92 companies assigned to a cluster with no nulls --
    dropping any company with a missing feature (e.g. ATGL, which has no
    cash flow data and therefore no FCF CAGR) would violate that outright.
    Median imputation keeps every company in the clustering run; the
    trade-off is that an imputed company's cluster assignment is somewhat
    less meaningful for whichever feature(s) were filled in -- tracked via
    the returned imputed_mask so callers can flag it, same transparency
    principle as the scale-anomaly caveat.

    Winsorization was added after the first clustering run produced one
    71-company cluster and three 1-2 company clusters -- found by actually
    inspecting cluster sizes, not assumed to be fine because the code ran.
    The cause: StandardScaler has no outlier resistance, and a few extreme
    points (BEL/HAL/INDIGO's corrupted ROE in the thousands of percent,
    but ALSO BAJAJHLDNG's genuine 432% NPM -- a real characteristic of an
    investment-holding company with minimal core "sales" -- not a data
    bug) dominate Euclidean distance so completely that KMeans effectively
    becomes outlier detection instead of segmentation. Clipping each
    feature to its 5th/95th percentile before scaling (same P10/P90
    winsorization principle as ranking.py's composite score, just a wider
    band here since clustering needs more of the underlying spread
    preserved than a single composite score does) keeps a handful of
    extreme values -- corrupted or genuinely unusual -- from warping the
    whole partition.
    """
    values = features[FEATURE_COLUMNS].values
    imputed_mask = pd.isna(values)
    imputer = SimpleImputer(strategy="median")
    imputed_values = imputer.fit_transform(values)

    winsorized = imputed_values.copy()
    for col_idx in range(winsorized.shape[1]):
        p5, p95 = np.percentile(winsorized[:, col_idx], [5, 95])
        winsorized[:, col_idx] = np.clip(winsorized[:, col_idx], p5, p95)

    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(winsorized)
    return scaled_values, imputed_mask


def elbow_plot(scaled_values: np.ndarray, save_path: str, k_range=range(2, 9)) -> str:
    inertias = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(scaled_values)
        inertias.append(km.inertia_)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(list(k_range), inertias, marker="o")
    ax.axvline(N_CLUSTERS, color="red", linestyle="--", label=f"k={N_CLUSTERS} (spec-fixed)")
    ax.set_xlabel("k (number of clusters)")
    ax.set_ylabel("Inertia (within-cluster sum of squares)")
    ax.set_title("Elbow Method -- validating k=5")
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def name_clusters(centroids_df: pd.DataFrame) -> dict:
    """Map each cluster_id to one of spec 10.2's 5 named archetypes, based
    on where its centroid sits relative to the other 4 -- not a fixed
    lookup, since which cluster_id KMeans assigns to which archetype
    varies run to run (random_state controls reproducibility of the
    PARTITION, not which cluster gets labelled 0 vs 1 vs 2...).

    This ranking-based approach is a judgment call (spec names the 5
    archetypes but gives no formula for assigning them to centroids):
    - High-Quality Growth: high ROE + high revenue CAGR
    - Defensive Dividend: low D/E + moderate/low revenue CAGR (stable, not growing fast)
    - Value Cyclicals: below-median ROE + below-median growth, but not the worst on either
    - Distressed: lowest ROE and/or lowest FCF CAGR
    - Emerging Growth: highest revenue CAGR but not yet the highest ROE (growing, not yet mature)

    Implemented as a scoring pass rather than rigid rules, since 5
    centroids rarely fall into perfectly separable buckets -- each cluster
    gets the archetype it scores highest on, with earlier-listed archetypes
    (more specific criteria) claimed first so two clusters can't both grab
    "Distressed" and leave another unnamed.
    """
    roe_rank = centroids_df["return_on_equity_pct"].rank(ascending=False)
    de_rank = centroids_df["debt_to_equity"].rank(ascending=True)
    rev_cagr_rank = centroids_df["revenue_cagr_5yr_pct"].rank(ascending=False)
    fcf_cagr_rank = centroids_df["fcf_cagr_5yr_pct"].rank(ascending=False)

    assigned = {}
    remaining = set(centroids_df.index)

    # Distressed: worst combined ROE + FCF CAGR rank.
    distress_score = roe_rank + fcf_cagr_rank
    cid = distress_score.loc[list(remaining)].idxmax()
    assigned[cid] = "Distressed"
    remaining.discard(cid)

    # High-Quality Growth: best combined ROE + revenue CAGR rank.
    hq_score = roe_rank + rev_cagr_rank
    cid = hq_score.loc[list(remaining)].idxmin()
    assigned[cid] = "High-Quality Growth"
    remaining.discard(cid)

    # Emerging Growth: highest revenue CAGR among what's left.
    cid = rev_cagr_rank.loc[list(remaining)].idxmin()
    assigned[cid] = "Emerging Growth"
    remaining.discard(cid)

    # Defensive Dividend: lowest D/E among what's left.
    cid = de_rank.loc[list(remaining)].idxmin()
    assigned[cid] = "Defensive Dividend"
    remaining.discard(cid)

    # Whatever's left is "Value Cyclicals" -- moderate on every axis, by elimination.
    for cid in remaining:
        assigned[cid] = "Value Cyclicals"

    return assigned


def run_clustering(features: pd.DataFrame, flagged_keys: set) -> pd.DataFrame:
    scaled_values, imputed_mask = impute_and_scale(features)

    elbow_path = os.path.join(OUTPUT_DIR, "elbow_plot.png")
    elbow_plot(scaled_values, elbow_path)

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    cluster_ids = kmeans.fit_predict(scaled_values)
    distances = np.linalg.norm(scaled_values - kmeans.cluster_centers_[cluster_ids], axis=1)

    result = features.copy()
    result["cluster_id"] = cluster_ids
    result["distance_from_centroid"] = distances
    result["any_feature_imputed"] = imputed_mask.any(axis=1)

    # Centroid profile in ORIGINAL (unscaled) feature units, using MEDIAN
    # not mean -- same reasoning as the Sprint 4 dashboard's "Average ROE"
    # fix. The clustering itself runs on winsorized values, but this table
    # is for human interpretation and originally used .mean() on raw
    # values, which let BEL/HAL/INDIGO's uncapped ROE (still in the
    # thousands of percent) drag a 9-company cluster's displayed centroid
    # to "ROE ~1096%" even though the actual clustering decision was sound
    # -- found by inspecting which companies were actually IN that
    # cluster, not by trusting the summary number.
    centroids_df = features.assign(cluster_id=cluster_ids).groupby("cluster_id")[FEATURE_COLUMNS].median()
    cluster_name_map = name_clusters(centroids_df)
    result["cluster_name"] = result["cluster_id"].map(cluster_name_map)

    result["data_quality_caveat"] = result.apply(
        lambda r: (r["company_id"], r["year"]) in flagged_keys, axis=1
    )
    # Suffix the displayed name for flagged rows -- ROE/D-E are 2 of the 5
    # inputs, so a flagged company's cluster membership reflects a
    # corrupted input, not necessarily its real business profile.
    result["cluster_name_display"] = result.apply(
        lambda r: f"{r['cluster_name']} [UNRELIABLE -- scale anomaly in ROE/D-E input, see Sprint 2]"
        if r["data_quality_caveat"] else r["cluster_name"],
        axis=1,
    )

    return result, centroids_df


def correlation_heatmap(fr_latest_with_extra: pd.DataFrame, save_path: str) -> str:
    """Pearson correlation of 10 KPIs across all 92 companies' latest year (spec 10.3)."""
    kpi_columns = [
        "net_profit_margin_pct", "operating_profit_margin_pct", "return_on_equity_pct",
        "debt_to_equity", "interest_coverage", "asset_turnover", "free_cash_flow_cr",
        "earnings_per_share", "book_value_per_share", "dividend_payout_ratio_pct",
    ]
    corr = fr_latest_with_extra[kpi_columns].corr(method="pearson")

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(kpi_columns)))
    ax.set_yticks(range(len(kpi_columns)))
    ax.set_xticklabels(kpi_columns, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(kpi_columns, fontsize=7)
    for i in range(len(kpi_columns)):
        for j in range(len(kpi_columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=6)
    fig.colorbar(im, ax=ax, label="Pearson correlation")
    ax.set_title("KPI Correlation Matrix (latest year, all companies)", fontsize=10)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    return save_path


def run() -> tuple:
    import sqlite3
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from cagr import cagr_for_company

    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db"))
    try:
        fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
        pl_all = pd.read_sql("SELECT company_id, year, sales FROM profitandloss ORDER BY company_id, year", conn)
        cf_all = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity FROM cashflow ORDER BY company_id, year", conn)
        companies = pd.read_sql("SELECT id AS company_id FROM companies", conn)
    finally:
        conn.close()

    fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    cagr_rows = []
    for company_id, group in pl_all.groupby("company_id"):
        result = cagr_for_company(group.set_index("year")["sales"], windows=(5,))
        cagr_rows.append({"company_id": company_id, "revenue_cagr_5yr_pct": result["cagr_5yr_pct"]})
    revenue_cagr_df = pd.DataFrame(cagr_rows)

    fcf_rows = []
    for company_id, group in cf_all.groupby("company_id"):
        fcf_series = (group.set_index("year")["operating_activity"] + group.set_index("year")["investing_activity"])
        result = cagr_for_company(fcf_series, windows=(5,))
        fcf_rows.append({"company_id": company_id, "fcf_cagr_5yr_pct": result["cagr_5yr_pct"]})
    fcf_cagr_df = pd.DataFrame(fcf_rows)

    cagr_df = revenue_cagr_df.merge(fcf_cagr_df, on="company_id", how="outer")

    # Ensure EVERY company in `companies` appears in the feature frame, even
    # ones with zero financial_ratios rows -- AC-15 requires all 92
    # assigned, so a company entirely missing from fr_latest still needs a
    # row (with every feature imputed) rather than being silently dropped.
    fr_latest_full = companies.merge(fr_latest, on="company_id", how="left")
    fr_latest_full["year"] = fr_latest_full["year"].fillna("N/A")

    features = build_feature_frame(fr_latest_full, cagr_df)

    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    result, centroids_df = run_clustering(features, flagged_keys)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_cols = ["company_id", "cluster_id", "cluster_name", "cluster_name_display",
                   "distance_from_centroid", "any_feature_imputed", "data_quality_caveat"]
    result[output_cols].to_csv(os.path.join(OUTPUT_DIR, "cluster_labels.csv"), index=False)

    heatmap_path = correlation_heatmap(fr_latest_full, os.path.join(OUTPUT_DIR, "correlation_heatmap.png"))

    return result, centroids_df, heatmap_path


if __name__ == "__main__":
    result, centroids_df, heatmap_path = run()
    print(f"cluster_labels.csv: {len(result)} companies assigned")
    print(f"Null cluster_id count: {result['cluster_id'].isna().sum()}")
    print(f"Companies with an imputed feature: {result['any_feature_imputed'].sum()}")
    print(f"Companies flagged with data-quality caveat: {result['data_quality_caveat'].sum()}")
    print()
    print("Cluster sizes and names:")
    print(result.groupby(["cluster_id", "cluster_name"]).size())
    print()
    print("Centroid profile (original units):")
    print(centroids_df.round(2))
    print(f"\ncorrelation_heatmap.png -> {heatmap_path}")
