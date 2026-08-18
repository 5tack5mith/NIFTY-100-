"""Matplotlib chart generators shared by tearsheet.py, sector_report.py, and
portfolio_summary.py -- each returns a saved PNG path rather than a figure
object, since ReportLab's Image flowable needs a file path (or file-like
object) to embed, not a matplotlib Figure directly.

Every chart that plots ROE, ROCE, D/E, or Asset Turnover accepts a
`flagged_years` set and marks any flagged data point distinctly (red X
instead of the normal line marker) plus an in-chart footnote -- the PDF
equivalent of the caveat banners already on the dashboard/screener/peer
exports (see Sprint 5 kickoff instructions: tearsheet trend arrows and
charts need the same treatment, not just the text-based pros/cons).
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CHART_DPI = 150


def _empty_chart_placeholder(save_path: str, title: str, message: str) -> str:
    """A plain 'no data available' panel instead of a chart -- found
    necessary when the full 92-company tearsheet batch hit ATGL, which has
    zero cashflow.xlsx records at all (cashflow.xlsx is only ~91% covered
    per spec Section 7.2, so a company with NO cash flow rows was always
    possible; it just hadn't shown up until running the actual batch,
    since every function developed and manually tested before this used
    companies with full history). Every chart function in this module
    routes through here on empty input rather than crashing on
    `.iloc[-1]` of an empty DataFrame.
    """
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=9, color="grey", transform=ax.transAxes)
    ax.set_title(title, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(save_path, dpi=CHART_DPI)
    plt.close(fig)
    return save_path


def revenue_profit_bar(pl_company: pd.DataFrame, save_path: str) -> str:
    if pl_company.empty:
        return _empty_chart_placeholder(save_path, "Revenue & Net Profit (10yr)", "No P&L data available")
    recent = pl_company.sort_values("year").tail(10)
    fig, ax = plt.subplots(figsize=(5, 2.6))
    x = range(len(recent))
    width = 0.38
    ax.bar([i - width / 2 for i in x], recent["sales"], width, label="Sales", color="#2563eb")
    ax.bar([i + width / 2 for i in x], recent["net_profit"], width, label="Net Profit", color="#16a34a")
    ax.set_xticks(list(x))
    ax.set_xticklabels(recent["year"], rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("₹ Crore", fontsize=7)
    ax.set_title("Revenue & Net Profit (10yr)", fontsize=8)
    ax.legend(fontsize=6)
    ax.tick_params(labelsize=6)
    fig.tight_layout()
    fig.savefig(save_path, dpi=CHART_DPI)
    plt.close(fig)
    return save_path


def roe_roce_trend(fr_company: pd.DataFrame, save_path: str, flagged_years: set) -> str:
    """ROE trend line over up to 10 years, plus the latest year's ROCE as a
    single annotated point -- not a second line. ROCE isn't persisted per
    year anywhere (see Sprint 2 notes: only sector_roce_notes.csv holds
    one latest-year value per company), so a "ROCE trend" line would be a
    single dot with nothing to connect it to. Found this by actually
    rendering a tearsheet and looking at it -- the first version titled
    this chart "ROE / ROCE Trend (10yr)" with an invisible ROCE line.
    """
    if fr_company.empty:
        return _empty_chart_placeholder(save_path, "ROE Trend (10yr) + Latest ROCE", "No financial_ratios data available")
    recent = fr_company.sort_values("year").tail(10)
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ax.plot(recent["year"], recent["return_on_equity_pct"], marker="o", markersize=3, label="ROE", color="#2563eb")

    latest_roce = recent["computed_roce_pct"].dropna()
    if not latest_roce.empty:
        roce_year = recent.loc[latest_roce.index[-1], "year"]
        roce_value = latest_roce.iloc[-1]
        ax.scatter([roce_year], [roce_value], color="#d97706", marker="D", s=40, zorder=5, label=f"ROCE ({roce_year})")

    flagged_rows = recent[recent["year"].isin(flagged_years)]
    if not flagged_rows.empty:
        ax.scatter(flagged_rows["year"], flagged_rows["return_on_equity_pct"], color="red", marker="x", s=60, zorder=6, label="Flagged year")

    ax.set_ylabel("%", fontsize=7)
    ax.set_title("ROE Trend (10yr) + Latest ROCE", fontsize=8)
    ax.legend(fontsize=6)
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=6)
    if not flagged_rows.empty:
        fig.text(0.02, 0.02, "Red X = data-quality caveat year (see Sprint 2 findings)", fontsize=5, color="red")
    fig.tight_layout()
    fig.savefig(save_path, dpi=CHART_DPI)
    plt.close(fig)
    return save_path


def bs_composition_stacked(bs_company: pd.DataFrame, save_path: str) -> str:
    if bs_company.empty:
        return _empty_chart_placeholder(save_path, "Balance Sheet Composition (10yr)", "No balance sheet data available")
    recent = bs_company.sort_values("year").tail(10)
    fig, ax = plt.subplots(figsize=(5, 2.6))
    components = ["equity_capital", "reserves", "borrowings", "other_liabilities"]
    colors = ["#2563eb", "#60a5fa", "#dc2626", "#f97316"]
    bottom = pd.Series(0, index=recent.index, dtype=float)
    for comp, color in zip(components, colors):
        values = recent[comp].fillna(0)
        ax.bar(recent["year"], values, bottom=bottom, label=comp.replace("_", " ").title(), color=color)
        bottom = bottom + values
    ax.set_ylabel("₹ Crore", fontsize=7)
    ax.set_title("Balance Sheet Composition (10yr)", fontsize=8)
    ax.legend(fontsize=5, loc="upper left")
    ax.tick_params(axis="x", labelsize=6, rotation=45)
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    fig.savefig(save_path, dpi=CHART_DPI)
    plt.close(fig)
    return save_path


def cf_waterfall(cf_company: pd.DataFrame, save_path: str) -> str:
    """Latest year's CFO -> CFI -> CFF -> Net Cash Flow, as a simple
    waterfall (not ReportLab's own chart primitives -- matplotlib bars
    with manually-computed running totals is more portable and matches
    every other chart in this module).
    """
    if cf_company.empty:
        return _empty_chart_placeholder(save_path, "Cash Flow Waterfall", "No cash flow data available")
    latest = cf_company.sort_values("year").iloc[-1]
    labels = ["CFO", "CFI", "CFF", "Net"]
    values = [latest["operating_activity"], latest["investing_activity"], latest["financing_activity"], latest["net_cash_flow"]]
    values = [v if pd.notna(v) else 0 for v in values]
    running = [0, values[0], values[0] + values[1], 0]  # last bar (Net) starts from 0, not stacked
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in values[:3]] + ["#2563eb"]

    fig, ax = plt.subplots(figsize=(5, 2.6))
    for i, (label, value, base, color) in enumerate(zip(labels, values, running, colors)):
        ax.bar(label, value, bottom=base if label != "Net" else 0, color=color)
    ax.set_ylabel("₹ Crore", fontsize=7)
    ax.set_title(f"Cash Flow Waterfall ({latest['year']})", fontsize=8)
    ax.tick_params(labelsize=6)
    ax.axhline(0, color="black", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(save_path, dpi=CHART_DPI)
    plt.close(fig)
    return save_path
