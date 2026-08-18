"""Companies router -- 8 of the 16 spec endpoints (Section 15):
/companies, /companies/{ticker}, /companies/{ticker}/pl|bs|cashflow|ratios|
tearsheet|documents.
"""

import os
import sqlite3
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, data_quality_caveat_for, df_to_records, series_to_dict

router = APIRouter(prefix="/api/v1", tags=["companies"])

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
TEARSHEETS_DIR = os.path.join(REPO_ROOT, "reports", "tearsheets")


def _company_exists(conn: sqlite3.Connection, ticker: str) -> bool:
    row = conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker.upper(),)).fetchone()
    return row is not None


def _require_company(conn: sqlite3.Connection, ticker: str) -> str:
    ticker = ticker.upper()
    if not _company_exists(conn, ticker):
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    return ticker


@router.get("/companies")
def list_companies(sector: Optional[str] = None, market_cap_category: Optional[str] = None,
                    search: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    query = """
        SELECT c.id, c.company_name, s.broad_sector, s.sub_sector, c.roe_percentage, c.roce_percentage
        FROM companies c LEFT JOIN sectors s ON c.id = s.company_id
        WHERE 1=1
    """
    params = []
    if sector:
        query += " AND s.broad_sector = ?"
        params.append(sector)
    if market_cap_category:
        query += " AND s.market_cap_category = ?"
        params.append(market_cap_category)
    if search:
        query += " AND (c.id LIKE ? OR c.company_name LIKE ?)"
        params += [f"%{search.upper()}%", f"%{search}%"]

    df = pd.read_sql(query, conn, params=params)
    return df_to_records(df)


@router.get("/companies/{ticker}")
def get_company(ticker: str, year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = _require_company(conn, ticker)
    company = series_to_dict(pd.read_sql("SELECT * FROM companies WHERE id = ?", conn, params=(ticker,)).iloc[0])
    sector_row = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id = ?", conn, params=(ticker,))

    if year:
        fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?", conn, params=(ticker, year))
    else:
        fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year DESC LIMIT 1", conn, params=(ticker,))

    result = {"company": company, "sector": series_to_dict(sector_row.iloc[0]) if not sector_row.empty else None,
              "latest_kpis": series_to_dict(fr.iloc[0]) if not fr.empty else None}
    if not fr.empty:
        caveat = data_quality_caveat_for(ticker, fr.iloc[0]["year"])
        if caveat:
            result["data_quality_caveat"] = caveat
    return result


def _year_range_query(table: str, ticker: str, from_year: Optional[str], to_year: Optional[str], conn):
    query = f"SELECT * FROM {table} WHERE company_id = ?"
    params = [ticker]
    if from_year:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year:
        query += " AND year <= ?"
        params.append(to_year)
    query += " ORDER BY year"
    return pd.read_sql(query, conn, params=params)


@router.get("/companies/{ticker}/pl")
def get_pl(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = _require_company(conn, ticker)
    df = _year_range_query("profitandloss", ticker, from_year, to_year, conn)
    return df_to_records(df)


@router.get("/companies/{ticker}/bs")
def get_bs(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = _require_company(conn, ticker)
    df = _year_range_query("balancesheet", ticker, from_year, to_year, conn)
    return df_to_records(df)


@router.get("/companies/{ticker}/cashflow")
def get_cashflow(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = _require_company(conn, ticker)
    df = _year_range_query("cashflow", ticker, from_year, to_year, conn)
    return df_to_records(df)


@router.get("/companies/{ticker}/ratios")
def get_ratios(ticker: str, year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    """financial_ratios rows. Every row's ROCE, D/E, Asset Turnover, and
    Book Value/Share should carry the Sprint 2 caveat when that company-
    year is flagged -- this is the endpoint most directly named by the
    Sprint 6 kickoff instructions ("Any FastAPI endpoint that returns
    these companies' ratios should carry the same flag/caveat").
    """
    ticker = _require_company(conn, ticker)
    if year:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year = ? ORDER BY year", conn, params=(ticker, year))
    else:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", conn, params=(ticker,))

    # ROCE isn't a financial_ratios column (see Sprint 2 notes) -- only
    # attachable for the latest year, since that's the only year
    # sector_roce_notes.csv covers per company.
    roce_path = os.path.join(REPO_ROOT, "output", "sector_roce_notes.csv")
    roce_notes = pd.read_csv(roce_path) if os.path.exists(roce_path) else pd.DataFrame()

    records = []
    for _, row in df.iterrows():
        record = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        caveat = data_quality_caveat_for(ticker, row["year"])
        if caveat:
            record["data_quality_caveat"] = caveat
        if not roce_notes.empty:
            roce_row = roce_notes[(roce_notes["company_id"] == ticker) & (roce_notes["year"] == row["year"])]
            if not roce_row.empty:
                record["computed_roce_pct"] = roce_row.iloc[0]["computed_roce_pct"]
        records.append(record)
    return records


@router.get("/companies/{ticker}/tearsheet")
def get_tearsheet(ticker: str, conn: sqlite3.Connection = Depends(get_db)):
    """Binary PDF stream (spec: 'Triggers download')."""
    ticker = _require_company(conn, ticker)
    pdf_path = os.path.join(TEARSHEETS_DIR, f"{ticker}_tearsheet.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail=f"Tearsheet not generated for '{ticker}'")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf")


@router.get("/companies/{ticker}/documents")
def get_documents(ticker: str, from_year: Optional[int] = None, to_year: Optional[int] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = _require_company(conn, ticker)
    query = "SELECT year, annual_report FROM documents WHERE company_id = ?"
    params = [ticker]
    if from_year:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year:
        query += " AND year <= ?"
        params.append(to_year)
    query += " ORDER BY year DESC"
    df = pd.read_sql(query, conn, params=params)
    # is_url_valid: presence-only, same documented limitation as the
    # dashboard's Annual Reports screen -- DQ-13 (actual HTTP HEAD check)
    # is disabled by default for being slow/non-critical (validator.py).
    df["is_url_valid"] = df["annual_report"].notna()
    return df_to_records(df)
