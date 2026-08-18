"""Peer Comparison screen -- spec 5.4.

Group selector -> radar chart + side-by-side table. Uses an interactive
Plotly radar (go.Scatterpolar) here rather than the static matplotlib PNGs
from Sprint 3's src/reports/radar_charts.py -- those PNGs are a batch
deliverable (92 files, D-10), while this screen is meant to be explored
interactively (spec: "Toggle between years").

Scope note on "Toggle between years": peer_percentiles (built in Sprint 3,
src/analytics/peer.py) only stores each company's LATEST-year percentile
per metric -- there's no historical percentile series to toggle through.
Making that work would mean re-running the percentile computation for
every historical year, which src/analytics/peer.py doesn't currently do.
Not built here -- flagged as a real gap against the spec rather than faked
with a dropdown that silently shows the same data regardless of the year
selected.
"""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table, render_data_quality_caveat

st.set_page_config(page_title="Peer Comparison", page_icon="🥊", layout="wide")
st.title("Peer Comparison")

peer_groups = load_table("SELECT company_id, peer_group_name, is_benchmark FROM peer_groups")
group_names = sorted(peer_groups["peer_group_name"].unique())

if not group_names:
    st.info("No peer groups loaded.")
    st.stop()

selected_group = st.selectbox("Peer group", group_names)
members = peer_groups[peer_groups["peer_group_name"] == selected_group]
member_ids = members["company_id"].tolist()

percentiles = load_table(
    f"SELECT * FROM peer_percentiles WHERE peer_group = ?", (selected_group,)
)
companies = load_table("SELECT id AS company_id, company_name FROM companies")

st.caption(
    f"{len(member_ids)} companies in this group. \"Toggle between years\" is not available -- "
    "peer percentiles are computed for each company's latest reported year only (see module docstring)."
)

for company_id in member_ids:
    latest_year_row = load_table(
        "SELECT year FROM financial_ratios WHERE company_id = ? ORDER BY year DESC LIMIT 1", (company_id,)
    )
    if not latest_year_row.empty:
        render_data_quality_caveat(company_id, latest_year_row.iloc[0]["year"])

fig = go.Figure()
metric_order = ["ROE", "ROCE", "NPM", "D/E", "FCF", "PAT_CAGR_5yr", "Revenue_CAGR_5yr", "EPS_CAGR_5yr"]
for company_id in member_ids:
    company_data = percentiles[percentiles["company_id"] == company_id].set_index("metric")
    values = [company_data.loc[m, "percentile_rank"] if m in company_data.index else 0 for m in metric_order]
    is_benchmark = members.set_index("company_id").loc[company_id, "is_benchmark"]
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]], theta=metric_order + [metric_order[0]],
        name=f"{company_id}{' (benchmark)' if is_benchmark else ''}",
        line=dict(width=3 if is_benchmark else 1.5),
    ))
fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), height=550, showlegend=True)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Side-by-side comparison")
pivot = percentiles.pivot(index="company_id", columns="metric", values="value")
pivot = pivot.reindex(columns=metric_order)
pivot = pivot.merge(companies, on="company_id", how="left")
pivot = pivot.merge(members[["company_id", "is_benchmark"]], on="company_id", how="left")
pivot = pivot.set_index("company_name").sort_values("is_benchmark", ascending=False)
st.dataframe(pivot.drop(columns=["company_id"]), use_container_width=True)
