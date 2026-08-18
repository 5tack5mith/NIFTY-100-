"""Excel loader for the 7 core Nifty 100 source files.

Every core file uses header=1 (row 0 is junk metadata, row 1 has the
real column names — see project spec Section 5).

Each load_* function:
1. Reads the file with header=1
2. Normalises company_id (ticker) and year columns where present
3. Returns a clean DataFrame

Usage:
    from loader import load_companies, load_profitandloss, ...
    df = load_companies("data/raw/companies.xlsx")
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from normaliser import normalize_ticker, normalize_year


def load_companies(path: str) -> pd.DataFrame:
    """Load companies.xlsx — master company reference (no year column)."""
    df = pd.read_excel(path, header=1)
    df["id"] = df["id"].apply(normalize_ticker)
    return df


def load_profitandloss(path: str) -> pd.DataFrame:
    """Load profitandloss.xlsx — annual P&L statements."""
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df["year"] = df["year"].apply(normalize_year)
    return df


def load_balancesheet(path: str) -> pd.DataFrame:
    """Load balancesheet.xlsx — annual balance sheet."""
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df["year"] = df["year"].apply(normalize_year)
    return df


def load_cashflow(path: str) -> pd.DataFrame:
    """Load cashflow.xlsx — annual cash flow statements."""
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df["year"] = df["year"].apply(normalize_year)
    return df


def load_analysis(path: str) -> pd.DataFrame:
    """Load analysis.xlsx — pre-computed growth metrics (partial coverage).

    No year column to normalise — periods are embedded in text fields
    like 'compounded_sales_growth' (parsed later, in the NLP module).
    """
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_documents(path: str) -> pd.DataFrame:
    """Load documents.xlsx — annual report link repository.

    Note: year column here is capitalised 'Year' (int, calendar year,
    not a financial-year string) — spec Section 5.6 flags this explicitly.
    It's already a clean int, so no normalize_year() call needed.
    """
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_prosandcons(path: str) -> pd.DataFrame:
    """Load prosandcons.xlsx — qualitative pros/cons (partial coverage)."""
    df = pd.read_excel(path, header=1)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_sectors(path: str) -> pd.DataFrame:
    """Load sectors.xlsx (supplementary) -- 1:1 sector mapping for all 92 companies."""
    df = pd.read_excel(path, header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_stock_prices(path: str) -> pd.DataFrame:
    """Load stock_prices.xlsx (supplementary) -- simulated monthly OHLCV.

    date is already a clean 'YYYY-MM-DD' string in the source file -- it's
    a calendar date, not a financial-year label, so normalize_year() (which
    only understands FY-style formats like 'Mar-23') doesn't apply here.
    """
    df = pd.read_excel(path, header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_market_cap(path: str) -> pd.DataFrame:
    """Load market_cap.xlsx (supplementary) -- simulated annual valuation multiples.

    year is a plain calendar-year int (2019-2024) here, not the 'Mon-YY'
    financial-year label the core files use -- already clean, no
    normalize_year() needed.
    """
    df = pd.read_excel(path, header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


def load_financial_ratios(path: str) -> pd.DataFrame:
    """Load financial_ratios.xlsx (supplementary) -- pre-computed KPI table.

    Unlike market_cap, this file's year column IS in a normalize_year()-
    compatible format ('Mar 2014', 'Dec 2012') -- easy to miss since it
    looks similar to market_cap's plain int year at a glance, but it's a
    financial-year label, not a calendar year, so it goes through the same
    normaliser as the core P&L/BS/CF tables.
    """
    df = pd.read_excel(path, header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df["year"] = df["year"].apply(normalize_year)
    return df


def load_peer_groups(path: str) -> pd.DataFrame:
    """Load peer_groups.xlsx (supplementary) -- many-to-many company/group membership."""
    df = pd.read_excel(path, header=0)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    return df


if __name__ == "__main__":
    # Quick manual smoke test when run directly: python loader.py
    RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

    loaders = {
        "companies.xlsx": load_companies,
        "profitandloss.xlsx": load_profitandloss,
        "balancesheet.xlsx": load_balancesheet,
        "cashflow.xlsx": load_cashflow,
        "analysis.xlsx": load_analysis,
        "documents.xlsx": load_documents,
        "prosandcons.xlsx": load_prosandcons,
    }

    for filename, loader_fn in loaders.items():
        filepath = os.path.join(RAW_DIR, filename)
        if not os.path.exists(filepath):
            print(f"SKIP: {filename} not found at {filepath}")
            continue
        df = loader_fn(filepath)
        print(f"{filename}: {len(df)} rows, {len(df.columns)} columns")
        print(f"  columns: {list(df.columns)}")
        print()