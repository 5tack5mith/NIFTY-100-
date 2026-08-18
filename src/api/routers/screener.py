"""Screener endpoint -- reuses src/screener/engine.py directly (same
reasoning as the dashboard's Screener page: exactly one implementation of
"what counts as ROE >= 15%", not a second copy that could drift).
"""

import os
import sqlite3
import sys
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, data_quality_caveat_for, ttl_cache
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "screener"))
from engine import build_screener_universe, apply_filters, load_config

router = APIRouter(prefix="/api/v1", tags=["screener"])


@ttl_cache(ttl_seconds=600)
def _cached_screener_universe(conn: sqlite3.Connection):
    """Cached at the API layer, not inside build_screener_universe() itself
    -- that function is shared with the dashboard, peer.py, and
    radar_charts.py, none of which call it repeatedly within a short
    window the way concurrent API requests do. Caching it unconditionally
    for every caller would be over-engineering; caching it here, where the
    Day 43 load test actually found the bottleneck, is scoped to the
    problem that was measured.
    """
    return build_screener_universe(conn)


@router.get("/screener")
def run_screener(min_roe: Optional[float] = None, max_de: Optional[float] = None,
                  min_fcf: Optional[float] = None, sector: Optional[str] = None,
                  min_rev_cagr_5yr: Optional[float] = None, min_pat_cagr_5yr: Optional[float] = None,
                  max_pe: Optional[float] = None, conn: sqlite3.Connection = Depends(get_db)):
    universe = _cached_screener_universe(conn)

    thresholds = {}
    filter_keys = []
    param_map = {
        "min_roe": ("min_roe_pct", min_roe), "max_de": ("max_de", max_de),
        "min_fcf": ("min_fcf_cr", min_fcf), "min_rev_cagr_5yr": ("min_revenue_cagr_5yr_pct", min_rev_cagr_5yr),
        "min_pat_cagr_5yr": ("min_pat_cagr_5yr_pct", min_pat_cagr_5yr), "max_pe": ("max_pe", max_pe),
    }
    for _, (key, value) in param_map.items():
        if value is not None:
            filter_keys.append(key)
            thresholds[key] = value

    filtered = apply_filters(universe, filter_keys, thresholds) if filter_keys else universe
    if sector:
        filtered = filtered[filtered["broad_sector"] == sector]

    results = []
    for _, row in filtered.iterrows():
        # NaN -> None by hand here (same fix as db.df_to_records()) --
        # this record is built field-by-field rather than via a whole-
        # DataFrame helper, so each value needs its own guard.
        def _v(col):
            val = row[col]
            return None if pd.isna(val) else val

        record = {
            "company_id": row["company_id"], "company_name": row["company_name"],
            "broad_sector": row["broad_sector"], "year": row["year"],
            "return_on_equity_pct": _v("return_on_equity_pct"), "debt_to_equity": _v("debt_to_equity"),
            "free_cash_flow_cr": _v("free_cash_flow_cr"), "pe_ratio": _v("pe_ratio"),
            "revenue_cagr_5yr_pct": _v("revenue_cagr_5yr_pct"), "pat_cagr_5yr_pct": _v("pat_cagr_5yr_pct"),
        }
        caveat = data_quality_caveat_for(row["company_id"], row["year"])
        if caveat:
            record["data_quality_caveat"] = caveat
        results.append(record)
    return {"count": len(results), "results": results}
