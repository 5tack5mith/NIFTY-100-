"""Health router -- 1 endpoint: /health."""

import sqlite3
import time

from fastapi import APIRouter, Depends

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db

router = APIRouter(prefix="/api/v1", tags=["health"])

_SERVER_START_TIME = time.time()

# The spec's 10-table figure (Section 9, "SQLite database (10 tables)")
# doesn't match the schema actually built in Sprint 1 -- 12 tables exist
# (see db/schema.sql's own comment on this exact discrepancy, found while
# building it). db_row_counts reports all 12 real tables rather than
# artificially limiting to 10, since that's what actually exists to report on.
ALL_TABLES = [
    "companies", "profitandloss", "balancesheet", "cashflow", "analysis",
    "documents", "prosandcons", "sectors", "stock_prices", "market_cap",
    "financial_ratios", "peer_groups",
]


@router.get("/health")
def health(conn: sqlite3.Connection = Depends(get_db)):
    db_row_counts = {}
    for table in ALL_TABLES:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            db_row_counts[table] = count
        except sqlite3.OperationalError:
            db_row_counts[table] = None  # table missing -- surfaced, not hidden

    return {
        "status": "ok",
        "db_row_counts": db_row_counts,
        "uptime_seconds": round(time.time() - _SERVER_START_TIME, 1),
        "version": "1.0.0",
    }
