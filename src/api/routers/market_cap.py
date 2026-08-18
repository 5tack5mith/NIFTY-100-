"""Market cap router -- 1 endpoint: /market-cap/{ticker}."""

import sqlite3
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, df_to_records

router = APIRouter(prefix="/api/v1", tags=["market_cap"])


@router.get("/market-cap/{ticker}")
def get_market_cap(ticker: str, from_year: Optional[int] = None, to_year: Optional[int] = None,
                    conn: sqlite3.Connection = Depends(get_db)):
    ticker = ticker.upper()
    if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone():
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    query = "SELECT year, market_cap_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct FROM market_cap WHERE company_id = ?"
    params = [ticker]
    if from_year:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year:
        query += " AND year <= ?"
        params.append(to_year)
    query += " ORDER BY year"
    df = pd.read_sql(query, conn, params=params)
    # spec R-06: market_cap.xlsx is simulated, not real market data --
    # every response from this endpoint says so explicitly, not just the
    # dashboard tooltip (same treatment, different surface).
    return {"simulated_data_notice": "market_cap.xlsx is SIMULATED data, not real market prices (spec Section 6).",
            "data": df_to_records(df)}
