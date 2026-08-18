"""Sprint 5, Day 33-35: Company Tearsheet PDF generator (Module 8.1, D-16).

2 pages per company, 92 PDFs, written to reports/tearsheets/<TICKER>_tearsheet.pdf
per the spec's exact filename convention. Page 1: KPI tiles, 10yr revenue &
profit bar, ROE/ROCE trend line. Page 2: BS composition stacked bar, CF
waterfall, capital allocation badge, pros/cons.

Every text cell longer than 200 chars is truncated with an ellipsis before
being placed in a ReportLab table (spec risk R-08: "ReportLab LayoutError
on very long text cells overflowing frames... cells > 200 chars truncated
with ellipsis") -- this is a documented spec mitigation, not a choice made
here, and it exists specifically because pros/cons text (including the
Sprint 5 scale-anomaly caveat suffix, which is itself fairly long) could
otherwise overflow a table cell's frame and crash the whole batch run.
"""

import importlib.util
import os
import sys
import tempfile

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)

sys.path.insert(0, os.path.dirname(__file__))
from chart_helpers import revenue_profit_bar, roe_roce_trend, bs_composition_stacked, cf_waterfall

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
TEARSHEETS_DIR = os.path.join(REPORTS_DIR, "tearsheets")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

MAX_CELL_CHARS = 200  # spec R-08 mitigation


def _truncate(text: str, max_chars: int = MAX_CELL_CHARS) -> str:
    text = str(text)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TearsheetTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=4))
    styles.add(ParagraphStyle("TearsheetSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle("CaveatBox", parent=styles["Normal"], fontSize=8, textColor=colors.red, borderColor=colors.red, borderWidth=0.5, borderPadding=4, backColor=colors.Color(1, 0.95, 0.8)))
    styles.add(ParagraphStyle("ProText", parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#166534")))
    styles.add(ParagraphStyle("ConText", parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#991b1b")))
    return styles


def _kpi_table(latest_fr: pd.Series) -> Table:
    # "Rs." not "₹" -- ReportLab's default font (Helvetica) has no glyph
    # for the Rupee sign (U+20B9) and renders it as a black box. matplotlib
    # (used for the charts below) uses a different font stack that DOES
    # support it, which is why the chart axis labels are fine but this
    # table wasn't -- found by actually rendering a tearsheet to an image
    # and looking at it, not by reading the code.
    icr = latest_fr.get("interest_coverage")
    icr_display = "Debt Free" if icr == 999.0 else (f"{icr:.1f}x" if pd.notna(icr) else "N/A")
    roce = latest_fr.get("computed_roce_pct")
    data = [
        ["ROE", "ROCE", "NPM", "D/E", "Int. Coverage", "EPS", "FCF (Rs.Cr)"],
        [
            f"{latest_fr['return_on_equity_pct']:.1f}%" if pd.notna(latest_fr["return_on_equity_pct"]) else "N/A",
            f"{roce:.1f}%" if pd.notna(roce) else "N/A",
            f"{latest_fr['net_profit_margin_pct']:.1f}%" if pd.notna(latest_fr["net_profit_margin_pct"]) else "N/A",
            f"{latest_fr['debt_to_equity']:.2f}" if pd.notna(latest_fr["debt_to_equity"]) else "N/A",
            icr_display,
            f"Rs.{latest_fr['earnings_per_share']:.1f}" if pd.notna(latest_fr["earnings_per_share"]) else "N/A",
            f"{latest_fr['free_cash_flow_cr']:.0f}" if pd.notna(latest_fr["free_cash_flow_cr"]) else "N/A",
        ],
    ]
    table = Table(data, colWidths=[2.4 * cm] * 7)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_tearsheet(company_id: str, company_row: pd.Series, pl_c: pd.DataFrame, bs_c: pd.DataFrame,
                     cf_c: pd.DataFrame, fr_c: pd.DataFrame, pros: list, cons: list,
                     capital_pattern: str, flagged_keys: set, chart_dir: str, save_path: str) -> str:
    styles = _styles()
    doc = SimpleDocTemplate(save_path, pagesize=A4, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    story = []

    latest_fr = fr_c.sort_values("year").iloc[-1]
    latest_year = latest_fr["year"]
    company_flagged = (company_id, latest_year) in flagged_keys

    # --- Page 1 ---
    story.append(Paragraph(f"{company_id} -- {company_row.get('company_name', '')}", styles["TearsheetTitle"]))
    story.append(Paragraph(f"Latest reported year: {latest_year}", styles["TearsheetSub"]))
    story.append(Spacer(1, 0.3 * cm))

    if company_flagged:
        story.append(Paragraph(
            "[!] DATA QUALITY CAVEAT: This company's balance sheet for the latest reported year appears "
            "mis-scaled relative to its P&L (see Sprint 2 findings). ROCE, Asset Turnover, D/E, and "
            "Book Value/Share should not be trusted without source verification.",
            styles["CaveatBox"],
        ))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Key Metrics", styles["SectionHeader"]))
    story.append(_kpi_table(latest_fr))
    story.append(Spacer(1, 0.4 * cm))

    rev_chart_path = os.path.join(chart_dir, f"{company_id}_revenue.png")
    revenue_profit_bar(pl_c, rev_chart_path)
    roe_chart_path = os.path.join(chart_dir, f"{company_id}_roe_roce.png")
    flagged_years_for_company = {year for (cid, year) in flagged_keys if cid == company_id}
    roe_roce_trend(fr_c, roe_chart_path, flagged_years_for_company)

    story.append(Image(rev_chart_path, width=16 * cm, height=8.3 * cm))
    story.append(Image(roe_chart_path, width=16 * cm, height=8.3 * cm))

    story.append(PageBreak())

    # --- Page 2 ---
    story.append(Paragraph(f"{company_id} -- Balance Sheet & Cash Flow Detail", styles["TearsheetTitle"]))
    story.append(Spacer(1, 0.2 * cm))

    bs_chart_path = os.path.join(chart_dir, f"{company_id}_bs.png")
    bs_composition_stacked(bs_c, bs_chart_path)
    cf_chart_path = os.path.join(chart_dir, f"{company_id}_cf.png")
    cf_waterfall(cf_c, cf_chart_path)

    story.append(Image(bs_chart_path, width=16 * cm, height=8.3 * cm))
    story.append(Image(cf_chart_path, width=16 * cm, height=8.3 * cm))

    story.append(Paragraph(f"Capital Allocation Pattern: <b>{capital_pattern}</b>", styles["SectionHeader"]))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("Pros", styles["SectionHeader"]))
    for text in pros[:5]:  # cap at 5 per side so page 2 can't overflow with a very long rule-triggered list
        story.append(Paragraph(f"+ {_truncate(text)}", styles["ProText"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Cons", styles["SectionHeader"]))
    for text in cons[:5]:
        story.append(Paragraph(f"- {_truncate(text)}", styles["ConText"]))

    doc.build(story)
    return save_path


def run(limit: int = None) -> list:
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db"))
    try:
        companies = pd.read_sql("SELECT id AS company_id, company_name FROM companies", conn)
        pl = pd.read_sql("SELECT * FROM profitandloss", conn)
        bs = pd.read_sql("SELECT * FROM balancesheet", conn)
        cf = pd.read_sql("SELECT * FROM cashflow", conn)
        fr = pd.read_sql("SELECT * FROM financial_ratios", conn)
    finally:
        conn.close()

    roce_notes = pd.read_csv(os.path.join(OUTPUT_DIR, "sector_roce_notes.csv"))
    pros_cons = pd.read_csv(os.path.join(OUTPUT_DIR, "pros_cons_generated.csv"))
    capital_alloc = pd.read_csv(os.path.join(OUTPUT_DIR, "capital_allocation.csv"))
    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    os.makedirs(TEARSHEETS_DIR, exist_ok=True)
    written = []

    company_list = companies["company_id"].tolist() if limit is None else companies["company_id"].tolist()[:limit]

    with tempfile.TemporaryDirectory() as chart_dir:
        for company_id in company_list:
            fr_c = fr[fr["company_id"] == company_id]
            pl_c = pl[pl["company_id"] == company_id]
            if fr_c.empty or pl_c.empty:
                continue  # same "no data, skip" policy as cashflow_intelligence.py (e.g. ATGL)

            # computed_roce_pct is per-latest-year only in sector_roce_notes.csv
            # (that file is itself a "latest year per company" snapshot from
            # D13) -- merge it into fr_c's most recent row only, so the KPI
            # tile/trend chart can show it without pretending we have a full
            # historical ROCE series (we don't -- ROCE isn't persisted per
            # year anywhere, see Sprint 2 notes).
            fr_c = fr_c.copy()
            fr_c["computed_roce_pct"] = None
            latest_idx = fr_c.sort_values("year").index[-1]
            roce_row = roce_notes[roce_notes["company_id"] == company_id]
            if not roce_row.empty:
                fr_c.loc[latest_idx, "computed_roce_pct"] = roce_row.iloc[0]["computed_roce_pct"]

            company_row = companies[companies["company_id"] == company_id].iloc[0]
            bs_c = bs[bs["company_id"] == company_id]
            cf_c = cf[cf["company_id"] == company_id]

            pc = pros_cons[pros_cons["company_id"] == company_id]
            pros = pc[pc["type"] == "pro"]["text"].tolist()
            cons = pc[pc["type"] == "con"]["text"].tolist()

            ca_row = capital_alloc[capital_alloc["company_id"] == company_id].sort_values("year")
            capital_pattern = ca_row.iloc[-1]["pattern_label"] if not ca_row.empty else "Unknown"

            save_path = os.path.join(TEARSHEETS_DIR, f"{company_id}_tearsheet.pdf")
            build_tearsheet(company_id, company_row, pl_c, bs_c, cf_c, fr_c, pros, cons,
                             capital_pattern, flagged_keys, chart_dir, save_path)
            written.append(save_path)

    return written


if __name__ == "__main__":
    written = run()
    print(f"Tearsheets written: {len(written)} -> {TEARSHEETS_DIR}")
