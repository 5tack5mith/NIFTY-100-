"""Financial Screener screen -- spec 5.3.

Reuses Sprint 3's screener engine (src/screener/engine.py) directly rather
than re-implementing filtering logic here -- the dashboard's sliders and
the exported screener_output.xlsx must agree on what counts as "ROE >= 15%",
so there's exactly one implementation of that filter, not a Streamlit copy
that could quietly drift from the Excel-export version.
"""

import importlib.util
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "screener"))
from data_loader import get_connection
from engine import build_screener_universe, apply_filters, load_config

st.set_page_config(page_title="Financial Screener", page_icon="🔍", layout="wide")
st.title("Financial Screener")

config = load_config()
thresholds = config["thresholds"]


@st.cache_data(ttl=600)
def _load_universe():
    conn = get_connection()
    return build_screener_universe(conn)


universe = _load_universe()

st.sidebar.header("Filter thresholds")
st.sidebar.caption("Sliders start at the spec-defined default for each metric. Adjust to widen or narrow results.")

# 10 sliders (spec 5.3: "Sidebar sliders for 10 metrics") -- covers every
# threshold from screener_config.yaml that has a real column in the
# screener universe. (max_de_non_financial and max_capex_intensity_pct are
# excluded here for the same reason engine.py's _THRESHOLD_MAP doesn't
# wire them to a universe column -- see that module's comment.)
slider_specs = [
    ("min_roe_pct", "Min ROE (%)", -20.0, 60.0),
    ("min_roce_pct", "Min ROCE (%)", -20.0, 60.0),
    ("min_npm_pct", "Min Net Profit Margin (%)", -30.0, 50.0),
    ("max_de", "Max Debt/Equity", 0.0, 10.0),
    ("min_fcf_cr", "Min FCF (₹Cr)", -5000.0, 20000.0),
    ("max_pe", "Max P/E", 0.0, 100.0),
    ("max_pb", "Max P/B", 0.0, 20.0),
    ("min_dividend_yield_pct", "Min Dividend Yield (%)", 0.0, 6.0),
    ("min_pat_cagr_5yr_pct", "Min PAT CAGR 5yr (%)", -30.0, 60.0),
    ("min_revenue_cagr_5yr_pct", "Min Revenue CAGR 5yr (%)", -30.0, 60.0),
]

active_filters = {}
for key, label, lo, hi in slider_specs:
    default = float(thresholds.get(key, lo))
    enabled = st.sidebar.checkbox(label, value=False, key=f"enable_{key}")
    value = st.sidebar.slider(label, min_value=lo, max_value=hi, value=default, key=f"slider_{key}", label_visibility="collapsed" if not enabled else "visible")
    if enabled:
        active_filters[key] = value

sector_options = ["All"] + sorted(universe["broad_sector"].dropna().unique().tolist())
selected_sector = st.sidebar.selectbox("Sector", sector_options)

filtered = apply_filters(universe, list(active_filters.keys()), active_filters) if active_filters else universe.copy()
if selected_sector != "All":
    filtered = filtered[filtered["broad_sector"] == selected_sector]

st.write(f"**{len(filtered)} of {len(universe)} companies match.**")

caveat_count = int(filtered["data_quality_caveat"].sum())
if caveat_count > 0:
    st.warning(
        f"⚠️ {caveat_count} of the matched companies carry a data-quality caveat "
        "(see the highlighted rows below) -- their balance-sheet-derived ratios "
        "(ROCE, D/E, Asset Turnover) are flagged as unreliable for the year shown."
    )

display_cols = [
    "company_id", "company_name", "broad_sector", "year",
    "return_on_equity_pct", "computed_roce_pct", "debt_to_equity",
    "free_cash_flow_cr", "pe_ratio", "pb_ratio", "dividend_yield_pct",
    "revenue_cagr_5yr_pct", "pat_cagr_5yr_pct", "data_quality_caveat",
]
display_df = filtered[display_cols].sort_values("return_on_equity_pct", ascending=False)


def _highlight_caveat(row):
    return ["background-color: #FFF3C4" if row["data_quality_caveat"] else "" for _ in row]


st.dataframe(display_df.style.apply(_highlight_caveat, axis=1), use_container_width=True, height=500)

st.download_button(
    "⬇ Download results as CSV",
    data=display_df.to_csv(index=False).encode("utf-8"),
    file_name="screener_results.csv",
    mime="text/csv",
)
