"""Trend Analysis screen -- spec 5.5.

Select company + metric -> 10yr sparkline + YoY% change annotation.
Multi-metric overlay mode.
"""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table, get_companies

st.set_page_config(page_title="Trend Analysis", page_icon="📈", layout="wide")
st.title("Trend Analysis")

companies = get_companies()
ticker = st.selectbox(
    "Company", options=companies["company_id"],
    format_func=lambda cid: f"{cid} -- {companies.set_index('company_id').loc[cid, 'company_name']}",
)

# Metrics from P&L + balance sheet (spec 5.5 data source), not
# financial_ratios -- keeping this screen anchored to raw source figures
# rather than derived ratios, per the spec's stated data source for this
# specific screen.
metric_options = {
    "Sales (₹Cr)": ("profitandloss", "sales"),
    "Net Profit (₹Cr)": ("profitandloss", "net_profit"),
    "EPS (₹)": ("profitandloss", "eps"),
    "Total Assets (₹Cr)": ("balancesheet", "total_assets"),
    "Borrowings (₹Cr)": ("balancesheet", "borrowings"),
    "Reserves (₹Cr)": ("balancesheet", "reserves"),
}

overlay_mode = st.checkbox("Multi-metric overlay mode")
if overlay_mode:
    selected_metrics = st.multiselect("Metrics to overlay", list(metric_options.keys()), default=["Sales (₹Cr)", "Net Profit (₹Cr)"])
else:
    selected_metrics = [st.selectbox("Metric", list(metric_options.keys()))]

if not selected_metrics:
    st.info("Select at least one metric.")
    st.stop()

fig = go.Figure()
for metric_label in selected_metrics:
    table, column = metric_options[metric_label]
    df = load_table(f"SELECT year, {column} FROM {table} WHERE company_id = ? ORDER BY year", (ticker,))
    df = df.tail(10)  # 10yr window per spec
    fig.add_trace(go.Scatter(x=df["year"], y=df[column], mode="lines+markers", name=metric_label))

fig.update_layout(height=450, xaxis_title="Fiscal Year", yaxis_title="Value")
st.plotly_chart(fig, use_container_width=True)

if not overlay_mode:
    table, column = metric_options[selected_metrics[0]]
    df = load_table(f"SELECT year, {column} FROM {table} WHERE company_id = ? ORDER BY year", (ticker,))
    df = df.tail(10)
    df["yoy_pct_change"] = df[column].pct_change() * 100
    st.subheader("Year-over-Year % Change")
    st.dataframe(
        df[["year", column, "yoy_pct_change"]].style.format({column: "{:.1f}", "yoy_pct_change": "{:+.1f}%"}, na_rep="N/A"),
        use_container_width=True,
    )
