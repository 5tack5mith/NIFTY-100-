"""Company Profile screen -- spec 5.2.

Ticker search, company card, KPI tiles (6 metrics), P&L/BS/CF charts,
pros/cons badges. This is the screen most likely to show a
BEL/HAL/INDIGO/LT scale-anomaly year, since it's where a user drills into
one company's raw history -- the caveat banner here is the most important
of the three dashboard surfaces (Home doesn't show individual companies;
Screener/Peer are covered too, but a user who searches straight for "HAL"
never touches those).
"""

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table, get_companies, render_data_quality_caveat

st.set_page_config(page_title="Company Profile", page_icon="🏢", layout="wide")
st.title("Company Profile")

companies = get_companies()
ticker = st.selectbox(
    "Search by ticker or company name",
    options=companies["company_id"],
    format_func=lambda cid: f"{cid} -- {companies.set_index('company_id').loc[cid, 'company_name']}",
)

company = companies.set_index("company_id").loc[ticker]
pl = load_table("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", (ticker,))
bs = load_table("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", (ticker,))
cf = load_table("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", (ticker,))
fr = load_table("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", (ticker,))
pros_cons = load_table("SELECT pros, cons FROM prosandcons WHERE company_id = ?", (ticker,))

st.header(f"{ticker} -- {company['company_name']}")
if pd.notna(company.get("about_company")):
    st.write(company["about_company"])
if pd.notna(company.get("website")):
    st.caption(f"🔗 {company['website']}")

if not fr.empty:
    latest = fr.iloc[-1]
    # The caveat banner, checked against THIS company's latest year --
    # exactly the scenario flagged in the Sprint 4 kickoff: a user landing
    # on HAL's profile page should see this before the KPI tiles below,
    # not just find it buried in a Sprint 3 Excel export.
    render_data_quality_caveat(ticker, latest["year"])

    st.subheader(f"Key Metrics ({latest['year']})")
    tile_cols = st.columns(6)
    tile_cols[0].metric("ROE", f"{latest['return_on_equity_pct']:.1f}%" if pd.notna(latest['return_on_equity_pct']) else "N/A")
    tile_cols[1].metric("NPM", f"{latest['net_profit_margin_pct']:.1f}%" if pd.notna(latest['net_profit_margin_pct']) else "N/A")
    tile_cols[2].metric("D/E", f"{latest['debt_to_equity']:.2f}" if pd.notna(latest['debt_to_equity']) else "N/A")
    icr_display = "Debt Free" if latest['interest_coverage'] == 999.0 else (
        f"{latest['interest_coverage']:.1f}x" if pd.notna(latest['interest_coverage']) else "N/A"
    )
    tile_cols[3].metric("Interest Coverage", icr_display)
    tile_cols[4].metric("EPS", f"₹{latest['earnings_per_share']:.1f}" if pd.notna(latest['earnings_per_share']) else "N/A")
    tile_cols[5].metric("FCF (₹Cr)", f"{latest['free_cash_flow_cr']:.0f}" if pd.notna(latest['free_cash_flow_cr']) else "N/A")
else:
    st.info("No financial_ratios data available for this company.")

st.divider()

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.subheader("Sales & Net Profit (10yr)")
    pl_recent = pl.tail(10)
    fig = px.bar(pl_recent, x="year", y=["sales", "net_profit"], barmode="group")
    fig.update_layout(height=350, xaxis_title="Fiscal Year", yaxis_title="₹ Crore")
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Balance Sheet: Assets vs Liabilities (10yr)")
    bs_recent = bs.tail(10)
    fig2 = px.bar(bs_recent, x="year", y=["total_assets", "total_liabilities"], barmode="group")
    fig2.update_layout(height=350, xaxis_title="Fiscal Year", yaxis_title="₹ Crore")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Cash Flow Breakdown (10yr)")
cf_recent = cf.tail(10)
fig3 = px.bar(cf_recent, x="year", y=["operating_activity", "investing_activity", "financing_activity"], barmode="relative")
fig3.update_layout(height=350, xaxis_title="Fiscal Year", yaxis_title="₹ Crore")
st.plotly_chart(fig3, use_container_width=True)

st.divider()
st.subheader("Pros & Cons")
if pros_cons.empty:
    st.caption("No pros/cons data available for this company yet (Sprint 5 will auto-generate these for all 92 companies).")
else:
    pc_col1, pc_col2 = st.columns(2)
    with pc_col1:
        for pro in pros_cons["pros"].dropna():
            st.success(f"✓ {pro}")
    with pc_col2:
        for con in pros_cons["cons"].dropna():
            st.error(f"✗ {con}")
