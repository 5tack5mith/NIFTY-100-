"""Peers router -- 2 endpoints: /peers/{group_name}, /companies/{ticker}/peers/compare."""

import sqlite3
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, data_quality_caveat_for

router = APIRouter(prefix="/api/v1", tags=["peers"])

RADAR_AXES = ["ROE", "ROCE", "NPM", "D/E", "FCF", "PAT_CAGR_5yr", "Revenue_CAGR_5yr", "EPS_CAGR_5yr"]


@router.get("/peers/{group_name}")
def get_peer_group(group_name: str, year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    members = pd.read_sql("SELECT company_id, is_benchmark FROM peer_groups WHERE peer_group_name = ?", conn, params=(group_name,))
    if members.empty:
        raise HTTPException(status_code=404, detail=f"Peer group '{group_name}' not found")

    percentiles = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group = ?", conn, params=(group_name,))
    companies = pd.read_sql("SELECT id AS company_id, company_name FROM companies", conn)

    results = []
    for _, member in members.iterrows():
        # peer_percentiles never actually stores NaN (peer.py skips a
        # metric entirely rather than inserting a null value/rank -- see
        # Sprint 3), but guarding here anyway rather than relying on an
        # upstream guarantee this endpoint doesn't control.
        company_percentiles = percentiles[percentiles["company_id"] == member["company_id"]]
        metrics = {
            row["metric"]: {
                "value": None if pd.isna(row["value"]) else row["value"],
                "percentile_rank": None if pd.isna(row["percentile_rank"]) else row["percentile_rank"],
            }
            for _, row in company_percentiles.iterrows()
        }
        company_name_row = companies[companies["company_id"] == member["company_id"]]
        record = {
            "company_id": member["company_id"],
            "company_name": company_name_row.iloc[0]["company_name"] if not company_name_row.empty else None,
            "is_benchmark": bool(member["is_benchmark"]),
            "metrics": metrics,
        }
        year_row = company_percentiles["year"].iloc[0] if not company_percentiles.empty else None
        if year_row:
            caveat = data_quality_caveat_for(member["company_id"], year_row)
            if caveat:
                record["data_quality_caveat"] = caveat
        results.append(record)
    return results


@router.get("/companies/{ticker}/peers/compare")
def compare_to_peers(ticker: str, year: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db)):
    ticker = ticker.upper()
    company_check = conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone()
    if not company_check:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    membership = pd.read_sql("SELECT peer_group_name FROM peer_groups WHERE company_id = ?", conn, params=(ticker,))
    if membership.empty:
        return {"company_id": ticker, "peer_group": None, "message": "No peer group assigned (spec R-10)", "radar_data": None}

    group_name = membership.iloc[0]["peer_group_name"]
    percentiles = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group = ? AND company_id = ?", conn, params=(group_name, ticker))
    group_percentiles = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group = ?", conn, params=(group_name,))

    company_axis = {row["metric"]: row["percentile_rank"] for _, row in percentiles.iterrows()}
    group_avg_axis = group_percentiles.groupby("metric")["percentile_rank"].mean().to_dict()

    result = {
        "company_id": ticker, "peer_group": group_name,
        "radar_data": {axis: {"company": company_axis.get(axis), "group_average": group_avg_axis.get(axis)} for axis in RADAR_AXES},
    }
    if not percentiles.empty:
        caveat = data_quality_caveat_for(ticker, percentiles.iloc[0]["year"])
        if caveat:
            result["data_quality_caveat"] = caveat
    return result
