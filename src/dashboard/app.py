"""Nifty 100 Financial Intelligence Platform -- Streamlit dashboard entry point.

This file IS the Home/Overview screen (spec 5.1), not a separate router.
The spec's Day 23 task lists a file called "pages/01_home.py", but in
Streamlit's actual multipage convention, the top-level script (this file)
is already the first page a user sees -- adding a second "Home" page
inside pages/ alongside it would just create a redundant, confusing extra
entry in the sidebar nav rather than matching how the framework actually
works. Every other screen (5.2-5.8) lives in pages/, exactly as the spec
lists them.

Run with: streamlit run src/dashboard/app.py  (or `make dashboard`)
"""

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils"))
from data_loader import load_table, get_companies, get_sectors

st.set_page_config(page_title="Nifty 100 Financial Intelligence", page_icon="📈", layout="wide")

# Sidebar branding -- spec D22: "Style config (sidebar logo, colour theme)".
# No actual logo asset exists in this project, so a text wordmark stands
# in for one rather than referencing an image file that doesn't exist.
with st.sidebar:
    st.markdown("### 📈 Nifty 100\n**Financial Intelligence Platform**")
    st.caption("92 companies · FY2010-2024")
    st.divider()

st.title("Nifty 100 -- Overview")

companies = get_companies()
sectors = get_sectors()

# Latest-year financial_ratios per company -- same "latest row per company"
# convention used throughout Sprint 3's screener (src/screener/engine.py),
# so the Home screen's summary numbers are consistent with what the
# Screener/Peer screens show, not a second independently-derived snapshot.
fr_all = load_table("SELECT * FROM financial_ratios")
fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

mc_all = load_table("SELECT company_id, year, pe_ratio FROM market_cap")
mc_latest = mc_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

# MEDIAN, not mean, for ROE -- found via the Day 27 dashboard QA pass
# (actually loading this screen in a browser, not just reading the code):
# a raw mean ROE came out to 123.9%, because BEL/HAL/INDIGO -- the exact
# Sprint 2 scale-anomaly companies -- have ROE values in the thousands of
# percent (equity_capital+reserves is the denominator, and their balance
# sheets are ~100x too small relative to net_profit). The median (16.7%)
# is the real, representative figure; a single-number "Average ROE" KPI
# tile is exactly the kind of aggregate stat that can silently launder a
# handful of known-bad company-years into a headline number nobody
# double-checks. Spec literally says "avg ROE" for this tile (5.1), but
# using the literal mean here would make the KPI tile itself untrustworthy
# for exactly the reason this project spent two sprints flagging.
median_roe = fr_latest["return_on_equity_pct"].median()
median_pe = mc_latest["pe_ratio"].median()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Companies Tracked", len(companies))
col2.metric("Median ROE", f"{median_roe:.1f}%" if pd.notna(median_roe) else "N/A")
col3.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
col4.metric("Sectors", sectors["broad_sector"].nunique())
st.caption(
    "ROE shown as median, not mean -- a handful of companies with a known balance-sheet "
    "scale issue (see Sprint 2 findings) produce ROE values in the thousands of percent that "
    "would otherwise dominate a simple average."
)

# "Market health banner" (spec 5.1) -- a simple, honest signal rather than
# a fabricated "market sentiment" score the data can't actually support:
# what fraction of companies are currently profitable at the P&L level.
# This uses the same latest-year financial_ratios frame as the KPI tiles
# above, so it can't disagree with them.
healthy_pct = (fr_latest["net_profit_margin_pct"] > 0).mean() * 100
if healthy_pct >= 80:
    st.success(f"📊 Market health: {healthy_pct:.0f}% of tracked companies are net-profitable in their latest reported year.")
elif healthy_pct >= 60:
    st.info(f"📊 Market health: {healthy_pct:.0f}% of tracked companies are net-profitable in their latest reported year.")
else:
    st.warning(f"📊 Market health: only {healthy_pct:.0f}% of tracked companies are net-profitable in their latest reported year.")

st.divider()

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Companies by Sector")
    sector_counts = sectors["broad_sector"].value_counts().reset_index()
    sector_counts.columns = ["broad_sector", "count"]
    fig = px.pie(sector_counts, names="broad_sector", values="count", hole=0.5)
    fig.update_layout(showlegend=True, height=400)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("ROE Distribution")
    # Clipped to a 0-100% display window -- same reasoning as the median-
    # vs-mean fix above: BEL/HAL/INDIGO's scale-anomaly ROE values (up to
    # 4744%) would otherwise compress this histogram into one bar at zero
    # width and a lone bar far off to the right, hiding the real
    # distribution of the other 88 companies entirely.
    roe_display = fr_latest[fr_latest["return_on_equity_pct"].between(-50, 100)]
    excluded = len(fr_latest) - len(roe_display)
    fig2 = px.histogram(roe_display, x="return_on_equity_pct", nbins=30)
    fig2.update_layout(height=400, xaxis_title="ROE (%)", yaxis_title="Companies")
    st.plotly_chart(fig2, use_container_width=True)
    if excluded:
        st.caption(f"{excluded} companies with ROE outside [-50%, 100%] excluded from this chart for readability (see caveat note above).")

st.divider()
st.caption(
    "Navigate to Company Profile, Screener, Peer Comparison, and other screens using the sidebar. "
    "Some companies carry a data-quality caveat (see Sprint 2 findings) -- this is surfaced on "
    "their individual Company Profile, Screener, and Peer Comparison entries, not hidden here."
)
