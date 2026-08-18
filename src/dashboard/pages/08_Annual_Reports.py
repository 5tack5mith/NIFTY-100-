"""Annual Reports screen -- spec 5.8.

Company -> year -> clickable BSE PDF link. Badge for missing reports.
documents.xlsx has ~82% company coverage (spec 7.2) and link-rot is
expected over time (spec risk R-02) -- DQ-13 (URL validity) is a WARNING-
level check that isn't run by default (network calls are slow; see
validator.py's check_urls flag), so "missing" here means "no row in
documents for this company/year", not "we verified the link 200s".
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
from data_loader import load_table, get_companies

st.set_page_config(page_title="Annual Reports", page_icon="📄", layout="wide")
st.title("Annual Reports")

companies = get_companies()
ticker = st.selectbox(
    "Company", options=companies["company_id"],
    format_func=lambda cid: f"{cid} -- {companies.set_index('company_id').loc[cid, 'company_name']}",
)

docs = load_table("SELECT year, annual_report FROM documents WHERE company_id = ? ORDER BY year DESC", (ticker,))

if docs.empty:
    st.warning(f"⚠️ No annual report links on file for {ticker} (this company is in the ~18% of the universe with no documents.xlsx coverage -- spec Section 7.2).")
else:
    for _, row in docs.iterrows():
        col1, col2 = st.columns([1, 4])
        col1.write(f"**{row['year']}**")
        if pd.notna(row["annual_report"]):
            col2.markdown(f"[📄 View Annual Report]({row['annual_report']})")
        else:
            col2.markdown("🚫 *Link unavailable*")

st.divider()
st.caption(
    "Link status here reflects whether a URL is on file, not whether it currently resolves -- "
    "the project's DQ-13 check (URL validity via HTTP HEAD) is disabled by default since it's a "
    "slow, non-critical WARNING-level check (see src/etl/validator.py)."
)
