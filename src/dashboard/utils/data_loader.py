"""Shared data access layer for every dashboard screen -- Sprint 4, Day 22.

Every screen imports from here rather than opening its own SQLite
connection, for two reasons: (1) st.cache_resource/st.cache_data need a
single shared entry point to actually cache anything across screens --
each page re-opening its own connection would defeat the R-09 mitigation
the spec calls for ("SQLite queries are cached with st.cache_data
(TTL=600s)"); (2) the data-quality caveat (BEL/HAL/INDIGO/LT, see Sprint
2/3) and the SIMULATED_DATA_FLAG warning (spec R-06, for stock_prices/
market_cap) both need to be checked the SAME way on every screen that
touches those companies or those tables -- centralising them here is what
makes that actually consistent instead of "however each page happened to
implement it".
"""

import importlib.util
import os

import pandas as pd
import streamlit as st

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def _import_db_loader():
    path = os.path.join(REPO_ROOT, "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource
def get_connection():
    """One cached SQLite connection per Streamlit session, not per page load."""
    db_loader = _import_db_loader()
    return db_loader.get_connection()


@st.cache_data(ttl=600)
def load_table(query: str, params: tuple = ()) -> pd.DataFrame:
    """Cached query helper -- TTL=600s per spec's R-09 mitigation.

    Takes a raw query string rather than a table name because different
    screens need different projections/joins of the same tables (e.g. Home
    wants sector aggregates, Company Profile wants one company's full P&L
    history) -- a single "load_table(name)" helper would just push every
    caller into re-filtering the whole table in pandas after the fact.
    """
    conn = get_connection()
    return pd.read_sql(query, conn, params=params)


@st.cache_data(ttl=600)
def get_data_quality_caveats() -> set:
    """The Sprint 2 scale-anomaly flags (BEL/HAL/INDIGO/LT), as a set of
    (company_id, year) tuples -- same structured artifact the Sprint 3
    screener/peer exports already use (output/scale_anomaly_flags.csv), so
    the dashboard can't drift out of sync with what Sprint 2/3 actually
    found.
    """
    path = os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv")
    if not os.path.exists(path):
        return set()
    df = pd.read_csv(path)
    return set(zip(df["company_id"], df["year"]))


def render_data_quality_caveat(company_id: str, year: str) -> None:
    """Show a warning banner if this company-year is a known scale anomaly.

    Every screen that displays a specific company's balance-sheet-derived
    ratios (ROCE, D/E, Asset Turnover) for a specific year should call this
    right before showing those numbers -- this is the dashboard-side half
    of the "surface the caveat, don't silently rank/display bad numbers"
    requirement from the Sprint 2/3 kickoff instructions.
    """
    if (company_id, year) in get_data_quality_caveats():
        st.warning(
            f"⚠️ **Data quality caveat**: {company_id}'s balance sheet for {year} appears "
            "mis-scaled relative to its P&L (see Sprint 2 findings). ROCE, Asset Turnover, "
            "D/E, and Book Value/Share for this year should not be trusted without source "
            "verification. Other years and other metrics for this company are unaffected."
        )


def render_simulated_data_notice(context: str = "") -> None:
    """Spec R-06: 'Simulated stock_prices / market_cap values cause incorrect
    real conclusions... All simulated datasets are clearly labelled
    SIMULATED in column comments and dashboard tooltips.' Call this on any
    screen that displays market_cap or stock_prices data (valuation
    multiples, price trends) -- both files are spec-confirmed simulated,
    not real market data (Section 6: 'Created from: Simulated...').
    """
    suffix = f" ({context})" if context else ""
    st.caption(f"📊 Market cap / valuation figures{suffix} are SIMULATED data, not real market prices -- see project spec Section 6.")


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    return load_table("SELECT id AS company_id, company_name, about_company, website, roce_percentage, roe_percentage FROM companies ORDER BY company_name")


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    return load_table("SELECT company_id, broad_sector, sub_sector, market_cap_category FROM sectors")
