"""Sector Analysis screen -- spec 5.6.

Sector selector -> bubble chart (revenue vs ROE, size=market cap). Sector
median KPI bar chart.
"""

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table, render_simulated_data_notice

st.set_page_config(page_title="Sector Analysis", page_icon="🏭", layout="wide")
st.title("Sector Analysis")

sectors = load_table("SELECT company_id, broad_sector FROM sectors")
fr_all = load_table("SELECT * FROM financial_ratios")
fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
pl_latest = load_table("SELECT company_id, year, sales FROM profitandloss").sort_values("year").groupby("company_id", as_index=False).tail(1)
mc_all = load_table("SELECT company_id, year, market_cap_crore FROM market_cap")
mc_latest = mc_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
companies = load_table("SELECT id AS company_id, company_name FROM companies")

merged = sectors.merge(fr_latest, on="company_id", how="left")
merged = merged.merge(pl_latest[["company_id", "sales"]], on="company_id", how="left")
merged = merged.merge(mc_latest[["company_id", "market_cap_crore"]], on="company_id", how="left")
merged = merged.merge(companies, on="company_id", how="left")

sector_options = ["All"] + sorted(sectors["broad_sector"].dropna().unique().tolist())
selected_sector = st.selectbox("Sector", sector_options)
plot_data = merged if selected_sector == "All" else merged[merged["broad_sector"] == selected_sector]

render_simulated_data_notice("market cap / bubble size")

st.subheader("Revenue vs ROE (bubble size = market cap)")
# Same fix as the Home screen's ROE histogram (found during Day 27 QA):
# BEL/HAL/INDIGO's scale-anomaly ROE values (up to 4744%) stretch the
# y-axis so far that the other ~88 companies' real spread (-20% to 60%)
# collapses into an invisible sliver near zero. A scatter plot doesn't
# fabricate anything the way a histogram bar-width would, but it's still
# unreadable -- clipped for display, same as the histogram.
scatter_data = plot_data.dropna(subset=["sales", "return_on_equity_pct"])
excluded = len(scatter_data[~scatter_data["return_on_equity_pct"].between(-50, 100)])
scatter_data = scatter_data[scatter_data["return_on_equity_pct"].between(-50, 100)]
if excluded:
    st.caption(f"{excluded} companies with ROE outside [-50%, 100%] excluded from this chart for readability (see Sprint 2 data-quality findings).")
fig = px.scatter(
    scatter_data,
    x="sales", y="return_on_equity_pct", size="market_cap_crore",
    color="broad_sector" if selected_sector == "All" else None,
    hover_name="company_name", size_max=50,
)
fig.update_layout(height=500, xaxis_title="Sales (₹Cr, log scale)", yaxis_title="ROE (%)", xaxis_type="log")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Sector Median KPIs")
sector_medians = merged.groupby("broad_sector").agg(
    median_roe=("return_on_equity_pct", "median"),
    median_npm=("net_profit_margin_pct", "median"),
    median_de=("debt_to_equity", "median"),
    company_count=("company_id", "count"),
).reset_index().sort_values("median_roe", ascending=False)

fig2 = px.bar(sector_medians, x="broad_sector", y="median_roe", hover_data=["company_count"])
fig2.update_layout(height=400, xaxis_title="", yaxis_title="Median ROE (%)")
st.plotly_chart(fig2, use_container_width=True)

st.dataframe(sector_medians, use_container_width=True)
