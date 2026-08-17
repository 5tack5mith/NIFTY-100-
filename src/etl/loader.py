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