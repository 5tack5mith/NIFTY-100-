"""Sprint 5, Day 29-30: analysis.xlsx text parser + CAGR cross-validator (Module 9, 9.1 + 9.5).

analysis.xlsx stores growth figures as free text like "10 Years: 21%"
rather than numbers (Sprint 1 finding: 4 rows per covered company, one per
growth-period window, not the 1:1 the spec's ER map originally claimed).
This module turns that text into structured rows, and cross-checks each
parsed value against the Ratio Engine's own computed CAGR for the same
company/period -- catching cases where the pre-computed source figure and
this project's independently-computed formula disagree by more than the
spec's stated threshold.

Scope note: Module 9 also lists 9.3 (business description tagger) and 9.4
(sentiment scorer via NLTK) -- neither appears in the Day 29-30 task
description or the Section 17 deliverables checklist (only
analysis_parsed.csv and pros_cons_generated.csv are named there), so
they're not built here. Flagging this as a scope decision, not an
oversight.
"""

import importlib.util
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analytics"))
from cagr import cagr_for_company

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

# spec 9.1: r'(\d+)\s*Years?:?\s*([\d.]+)%'
_PERIOD_VALUE_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)%")

# Each analysis.xlsx text column maps to a metric_type label, and (where a
# Ratio Engine equivalent exists) the P&L column + CAGR engine needed to
# cross-validate it. stock_price_cagr and roe don't have a clean Ratio
# Engine equivalent to check against here (stock_price_cagr needs
# stock_prices.xlsx, a different table entirely per spec 5.5's own note:
# "Display only -- compute from market_cap dataset"; roe is a point-in-time
# ratio, not a CAGR, so there's no "ROE CAGR" to compare it to) -- those
# two are parsed but not cross-validated, which is a real, documented gap
# rather than a silent one.
_COLUMN_METRIC_MAP = {
    "compounded_sales_growth": ("Revenue Growth", "sales"),
    "compounded_profit_growth": ("Profit Growth", "net_profit"),
    "stock_price_cagr": ("Stock Price CAGR", None),
    "roe": ("ROE", None),
}

CROSS_VALIDATION_THRESHOLD_PCT = 5.0  # spec 9.5: "Flag >5% divergence"


def parse_analysis_text(text: str) -> list:
    """Extract every (period_years, value_pct) pair from one text cell.

    Returns a list because a single cell can theoretically contain more
    than one period mention, even though every real cell observed in this
    dataset has exactly one -- the regex doesn't assume a fixed count.
    """
    if pd.isna(text):
        return []
    matches = _PERIOD_VALUE_PATTERN.findall(str(text))
    return [(int(period), float(value)) for period, value in matches]


def build_analysis_parsed(analysis_df: pd.DataFrame, pl_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in analysis_df.iterrows():
        for column, (metric_type, pl_column) in _COLUMN_METRIC_MAP.items():
            for period_years, value_pct in parse_analysis_text(row.get(column)):
                rows.append({
                    "company_id": row["company_id"],
                    "metric_type": metric_type,
                    "period_years": period_years,
                    "value_pct": value_pct,
                    "source_column": column,
                })
    parsed = pd.DataFrame(rows)
    if parsed.empty:
        return parsed

    parsed["computed_cagr_pct"] = None
    parsed["divergence_pct"] = None
    parsed["cross_validation_flag"] = False

    # Only rows with a real Ratio Engine equivalent (Revenue Growth, Profit
    # Growth) get cross-validated -- iterating per company avoids
    # recomputing the same company's full CAGR series once per row.
    for company_id, group in parsed.groupby("company_id"):
        pl_company = pl_df[pl_df["company_id"] == company_id].sort_values("year")
        for column, (metric_type, pl_column) in _COLUMN_METRIC_MAP.items():
            if pl_column is None:
                continue
            series = pl_company.set_index("year")[pl_column]
            for idx, prow in group[group["metric_type"] == metric_type].iterrows():
                result = cagr_for_company(series, windows=(int(prow["period_years"]),))
                computed = result.get(f"cagr_{int(prow['period_years'])}yr_pct")
                if computed is None:
                    continue
                divergence = abs(prow["value_pct"] - computed)
                parsed.loc[idx, "computed_cagr_pct"] = computed
                parsed.loc[idx, "divergence_pct"] = divergence
                parsed.loc[idx, "cross_validation_flag"] = divergence > CROSS_VALIDATION_THRESHOLD_PCT

    return parsed


def run() -> pd.DataFrame:
    conn_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
    import sqlite3
    conn = sqlite3.connect(conn_path)
    try:
        analysis_df = pd.read_sql("SELECT * FROM analysis", conn)
        pl_df = pd.read_sql("SELECT company_id, year, sales, net_profit FROM profitandloss", conn)
    finally:
        conn.close()

    parsed = build_analysis_parsed(analysis_df, pl_df)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "analysis_parsed.csv")
    parsed.to_csv(output_path, index=False)
    return parsed, output_path


if __name__ == "__main__":
    parsed, path = run()
    print(f"analysis_parsed.csv: {len(parsed)} rows -> {path}")
    if not parsed.empty:
        validated = parsed["computed_cagr_pct"].notna().sum()
        flagged = parsed["cross_validation_flag"].sum()
        print(f"Cross-validated against Ratio Engine: {validated} rows")
        print(f"Flagged (>{CROSS_VALIDATION_THRESHOLD_PCT}% divergence): {flagged} rows")
