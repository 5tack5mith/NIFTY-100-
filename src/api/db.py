"""Shared DB connection dependency + scale-anomaly caveat helper for every
API router. A fresh connection per request (not a cached shared one) --
same threading lesson learned from the Sprint 4 Streamlit dashboard bug
(sqlite3 connections can't safely cross threads), and Uvicorn can serve
requests from a thread pool, so "one shared connection" would risk the
exact same ProgrammingError found and fixed in db/loader.py's
check_same_thread=False. Opening fresh per request sidesteps the need to
rely on that flag being enough under concurrent load.
"""

import functools
import importlib.util
import os
import sqlite3
import threading
import time

import pandas as pd

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")


def _import_db_loader():
    path = os.path.join(REPO_ROOT, "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_db_loader = _import_db_loader()


def get_db() -> sqlite3.Connection:
    """FastAPI dependency -- yields a fresh connection, closed after the request."""
    conn = _db_loader.get_connection()
    try:
        yield conn
    finally:
        conn.close()


_flagged_keys_cache = None


def get_flagged_keys() -> set:
    """(company_id, year) pairs from the Sprint 2 scale-anomaly findings.

    Cached at module level (not per-request) since this file changes only
    when the Ratio Engine is re-run, not per API call -- reloading it on
    every request would be wasted I/O for a small, rarely-changing file.
    """
    global _flagged_keys_cache
    if _flagged_keys_cache is None:
        path = os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            _flagged_keys_cache = set(zip(df["company_id"], df["year"]))
        else:
            _flagged_keys_cache = set()
    return _flagged_keys_cache


def ttl_cache(ttl_seconds: int = 600):
    """A minimal time-based cache decorator -- FastAPI has no built-in
    equivalent to Streamlit's @st.cache_data(ttl=...), and the Day 43 load
    test (10 concurrent /screener requests) found this gap directly: each
    request independently rebuilt the whole screener universe (querying
    financial_ratios/market_cap and recomputing 5yr CAGR for all 92
    companies via a Python loop) from scratch, ~4.2s per request even
    though nothing about the underlying data had changed between them.
    Deliberately simple (one cached value, ignores arguments) rather than
    a general-purpose memoizer -- this is only applied to a single
    zero-argument builder function, not meant to be a reusable cache
    library.

    A lock guards the actual recomputation: the first version of this
    cache had no lock, and the Day 43 load test (10 concurrent requests
    fired via ThreadPoolExecutor) proved why that matters -- with no lock,
    all 10 threads observe an empty cache at essentially the same instant
    and every single one redoes the expensive rebuild before any of them
    finishes populating it, so response times looked identical to having
    no cache at all. The lock means only the first thread through
    actually computes; everyone else blocks briefly and then reads the
    now-populated cache, instead of duplicating the work.
    """
    def decorator(func):
        cache = {"value": None, "timestamp": 0}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if cache["value"] is None or (now - cache["timestamp"]) > ttl_seconds:
                with lock:
                    # Re-check inside the lock -- another thread may have
                    # already refreshed the cache while this thread was
                    # waiting to acquire it.
                    now = time.time()
                    if cache["value"] is None or (now - cache["timestamp"]) > ttl_seconds:
                        cache["value"] = func(*args, **kwargs)
                        cache["timestamp"] = now
            return cache["value"]

        return wrapper
    return decorator


def df_to_records(df: pd.DataFrame) -> list:
    """DataFrame -> list of JSON-safe dicts.

    Found necessary the first time /companies/{ticker}/ratios was actually
    hit (not just unit-tested with clean fixture data) -- a real
    financial_ratios row has NaN for missing metrics (e.g. interest_coverage
    when data's absent), and pandas' plain .to_dict() leaves those as
    float('nan'), which Python's json module refuses to serialize
    (ValueError: "Out of range float values are not JSON compliant").
    NaN -> None everywhere before handing data to FastAPI's JSON encoder.
    """
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def series_to_dict(series: pd.Series) -> dict:
    """Same NaN -> None fix as df_to_records(), for a single row (.iloc[0])."""
    return {k: (None if pd.isna(v) else v) for k, v in series.to_dict().items()}


def data_quality_caveat_for(company_id: str, year: str) -> dict | None:
    """Returns a caveat dict to attach to a response, or None if the given
    company/year isn't flagged. Every endpoint that returns ROE, ROCE, D/E,
    Asset Turnover, or Book Value/Share for a specific company-year should
    call this and include the result in its response -- per the Sprint 6
    kickoff instructions, this needs to reach API consumers, not just the
    internal CSVs/dashboard.
    """
    if (company_id, year) in get_flagged_keys():
        return {
            "flagged": True,
            "message": (
                "This company's balance sheet for this year appears mis-scaled relative to its P&L "
                "(see Sprint 2 findings). ROCE, Asset Turnover, D/E, and Book Value/Share should not "
                "be trusted without source verification. Other years/metrics are unaffected."
            ),
        }
    return None
