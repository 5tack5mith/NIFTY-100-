"""Portfolio router -- 1 endpoint: /portfolio/stats."""

import sqlite3
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db

router = APIRouter(prefix="/api/v1", tags=["portfolio"])

STATS_KPIS = [
    "return_on_equity_pct", "debt_to_equity", "net_profit_margin_pct", "asset_turnover",
    "free_cash_flow_cr", "interest_coverage", "earnings_per_share", "book_value_per_share",
    "dividend_payout_ratio_pct", "total_debt_cr",
]


@router.get("/portfolio/stats")
def get_portfolio_stats(year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    """P10-P90 percentile table for 10 KPIs across all 92 companies (spec)."""
    fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    if year:
        fr = fr_all[fr_all["year"] == year]
    else:
        fr = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    # interest_coverage's 999.0 debt-free sentinel (see Sprint 2) would
    # skew a percentile table badly if left in -- excluded from this
    # specific KPI's stats, same way it's excluded from ranking.py's
    # winsorization by virtue of being a clear outlier value.
    fr_for_stats = fr.copy()
    fr_for_stats.loc[fr_for_stats["interest_coverage"] == 999.0, "interest_coverage"] = None

    rows = []
    for kpi in STATS_KPIS:
        series = fr_for_stats[kpi].dropna()
        if series.empty:
            continue
        rows.append({
            "metric": kpi,
            "P10": series.quantile(0.10), "P25": series.quantile(0.25), "P50": series.quantile(0.50),
            "P75": series.quantile(0.75), "P90": series.quantile(0.90),
            "mean": series.mean(), "std": series.std(),
        })
    return rows
