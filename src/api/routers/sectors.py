"""Sectors router -- 2 endpoints: /sectors, /sectors/{sector}/companies."""

import sqlite3
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, data_quality_caveat_for, df_to_records

router = APIRouter(prefix="/api/v1", tags=["sectors"])


@router.get("/sectors")
def list_sectors(conn: sqlite3.Connection = Depends(get_db)):
    fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    mc_all = pd.read_sql("SELECT company_id, year, pe_ratio FROM market_cap", conn)
    mc_latest = mc_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    merged = sectors.merge(fr_latest, on="company_id", how="left").merge(mc_latest, on="company_id", how="left")
    summary = merged.groupby("broad_sector").agg(
        company_count=("company_id", "count"),
        median_roe=("return_on_equity_pct", "median"),
        median_pe=("pe_ratio", "median"),
        median_de=("debt_to_equity", "median"),
    ).reset_index().rename(columns={"broad_sector": "sector_name"})
    return df_to_records(summary)


@router.get("/sectors/{sector}/companies")
def get_sector_companies(sector: str, year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    sectors_df = pd.read_sql("SELECT company_id, broad_sector FROM sectors WHERE broad_sector = ?", conn, params=(sector,))
    if sectors_df.empty:
        raise HTTPException(status_code=404, detail=f"Sector '{sector}' not found")

    companies = pd.read_sql("SELECT id AS company_id, company_name FROM companies", conn)
    fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    if year:
        fr = fr_all[fr_all["year"] == year]
    else:
        fr = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    merged = sectors_df.merge(companies, on="company_id", how="left").merge(fr, on="company_id", how="left")

    top_8_kpi_cols = [
        "net_profit_margin_pct", "operating_profit_margin_pct", "return_on_equity_pct", "debt_to_equity",
        "interest_coverage", "asset_turnover", "free_cash_flow_cr", "earnings_per_share",
    ]
    results = []
    for _, row in merged.iterrows():
        # NaN -> None for every value here, same JSON-serialization fix as
        # df_to_records()/series_to_dict() -- this loop builds records
        # manually (per-KPI, with a caveat check per row) rather than via
        # those helpers, so it needs the same guard applied by hand.
        raw_year = row.get("year")
        record = {"company_id": row["company_id"], "company_name": row["company_name"],
                   "year": None if pd.isna(raw_year) else raw_year}
        for col in top_8_kpi_cols:
            value = row.get(col)
            record[col] = None if pd.isna(value) else value
        if pd.notna(row.get("year")):
            caveat = data_quality_caveat_for(row["company_id"], row["year"])
            if caveat:
                record["data_quality_caveat"] = caveat
        results.append(record)
    return results
