"""Capital Allocation Map screen -- spec 5.7.

Treemap of 92 companies by capital allocation pattern (8 categories, from
Sprint 2's src/analytics/cashflow_kpis.classify_capital_allocation()).
Click -> drill down to company list, using Streamlit 1.60's native
on_select support on st.plotly_chart (captures the click event directly,
rather than needing a separate component).
"""

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table

st.set_page_config(page_title="Capital Allocation Map", page_icon="🗺️", layout="wide")
st.title("Capital Allocation Map")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output")
capital_allocation = pd.read_csv(os.path.join(OUTPUT_DIR, "capital_allocation.csv"))

# One row per company: latest year's pattern, same "latest row" convention
# used everywhere else in the dashboard -- a treemap needs exactly one
# category per company, not one per company-year.
latest = capital_allocation.sort_values("year").groupby("company_id", as_index=False).tail(1)
companies = load_table("SELECT id AS company_id, company_name FROM companies")
sectors = load_table("SELECT company_id, broad_sector FROM sectors")
latest = latest.merge(companies, on="company_id", how="left").merge(sectors, on="company_id", how="left")

st.caption(f"{len(latest)} companies classified by their latest reported year's cash flow sign pattern.")

fig = px.treemap(
    latest, path=["pattern_label", "broad_sector", "company_id"],
    color="pattern_label",
)
fig.update_layout(height=600)
event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="capital_allocation_treemap")

st.subheader("Company list")
if event and event.get("selection", {}).get("points"):
    clicked_label = event["selection"]["points"][0].get("label")
    # A click on any level of the treemap (pattern, sector, or a single
    # company leaf) all resolve to a label string -- filtering by whichever
    # column contains that label covers all three levels without needing
    # to track which depth was clicked.
    mask = (
        (latest["pattern_label"] == clicked_label)
        | (latest["broad_sector"] == clicked_label)
        | (latest["company_id"] == clicked_label)
    )
    drill_down = latest[mask]
    st.write(f"Showing companies matching **{clicked_label}**:")
else:
    drill_down = latest
    st.caption("Click a treemap segment above to filter this list.")

st.dataframe(
    drill_down[["company_id", "company_name", "broad_sector", "pattern_label", "year"]],
    use_container_width=True,
)

st.subheader("Pattern distribution")
pattern_counts = latest["pattern_label"].value_counts().reset_index()
pattern_counts.columns = ["pattern_label", "count"]
st.bar_chart(pattern_counts.set_index("pattern_label"))
