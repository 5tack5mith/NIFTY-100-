"""Valuation screen -- spec 5's Module 5 mentions integrating this "if time
permits" (D26). Built since src/analytics/valuation.py already exists and
the marginal cost of a screen on top of it is small.

IMPORTANT CONTEXT for whoever reads this: the simulated market_cap.xlsx
data's median P/E (~46x) and P/B (~7.5x) already sit well above the spec's
own "fair" benchmarks (15-25x, <3x) -- so the overvaluation flag below
will legitimately mark the large majority of companies as overvalued. This
isn't a bug in the flag logic; it reflects the simulated dataset's own
central tendency being skewed higher than the spec's stated fair-value
ranges. See src/analytics/valuation.py's module docstring for the full
reasoning.
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "analytics"))
from data_loader import get_connection, render_simulated_data_notice
from valuation import build_valuation_summary

st.set_page_config(page_title="Valuation", page_icon="💰", layout="wide")
st.title("Valuation")

render_simulated_data_notice("P/E, P/B, EV/EBITDA, FCF Yield")

conn = get_connection()
df = build_valuation_summary(conn)

st.info(
    f"**{int(df['overvaluation_flag'].sum())} of {len(df)}** companies flag as overvalued "
    "(2+ of P/E>25x, P/B>3x, EV/EBITDA>18x). This dataset's simulated multiples run higher than "
    "the spec's own 'fair value' benchmarks on average, so a high flag count here reflects the "
    "underlying simulated data, not a screening signal that most of the Nifty 100 is mispriced."
)

sector_options = ["All"] + sorted(df["broad_sector"].dropna().unique().tolist())
selected_sector = st.selectbox("Sector", sector_options)
plot_data = df if selected_sector == "All" else df[df["broad_sector"] == selected_sector]

caveat_count = int(plot_data["data_quality_caveat"].sum())
if caveat_count > 0:
    st.warning(
        f"⚠️ {caveat_count} companies below carry the Sprint 2 data-quality caveat -- their "
        "FCF Yield (which depends on FCF from financial_ratios) may be unreliable for the year shown."
    )


def _highlight(row):
    styles = [""] * len(row)
    if row["data_quality_caveat"]:
        return ["background-color: #FFF3C4"] * len(row)
    if row["overvaluation_flag"]:
        return ["background-color: #FCA5A5"] * len(row)
    return styles


display_cols = [
    "company_id", "company_name", "broad_sector", "year",
    "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield_pct", "fcf_yield_pct",
    "overvaluation_flag", "data_quality_caveat",
]
st.dataframe(
    plot_data[display_cols].sort_values("pe_ratio", ascending=False).style.apply(_highlight, axis=1),
    use_container_width=True, height=500,
)

st.download_button(
    "⬇ Download valuation summary as CSV",
    data=plot_data[display_cols].to_csv(index=False).encode("utf-8"),
    file_name="valuation_summary.csv",
    mime="text/csv",
)
