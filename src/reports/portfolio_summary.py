"""Sprint 5, Day 33-35: Portfolio Summary PDF generator (Module 8.2, D-18).

ONE PDF, all 92 companies, one page each -- reports/portfolio/portfolio_summary_<YYYYMMDD>.pdf
per spec's filename convention. Company name, sector, top 6 KPIs, trend
arrow (up/down/flat) for 3yr direction.

Trend arrows apply per-KPI (not one overall arrow) -- spec doesn't specify
whether "trend arrow for 3yr direction" means one arrow for the whole
company or one per metric; per-metric is more informative and is what's
built here, flagged as a judgment call. Arrows are purely directional
(higher number = up arrow), not a "good/bad" qualitative judgment -- a
rising D/E gets an up arrow even though more debt isn't obviously "good",
since baking in a value judgment per metric would be a bigger, less
obviously correct design decision than just showing direction.

CAVEAT HANDLING: a trend arrow for a scale-sensitive KPI (ROE, ROCE, D/E)
is replaced with a warning glyph, not a directional arrow, if EITHER the
latest year or the 3-years-prior year for that company is in the Sprint 2
scale-anomaly list. A literal "up arrow" comparing a normal year's ROE to
a corrupted year's 3800% ROE would be actively misleading -- exactly the
scenario the Sprint 5 kickoff instructions called out by name.
"""

import datetime
import os
import sys

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
PORTFOLIO_DIR = os.path.join(REPORTS_DIR, "portfolio")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

SCALE_SENSITIVE_KPIS = {"return_on_equity_pct", "debt_to_equity"}  # ROCE handled separately -- see below
TREND_UP_THRESHOLD_PCT = 5.0   # relative change beyond which direction is called "up"/"down"; between is "flat"


def _trend_arrow(latest_value, prior_value) -> str:
    if latest_value is None or prior_value is None or pd.isna(latest_value) or pd.isna(prior_value) or prior_value == 0:
        return "?"
    change_pct = ((latest_value - prior_value) / abs(prior_value)) * 100
    if change_pct > TREND_UP_THRESHOLD_PCT:
        return "↑"
    if change_pct < -TREND_UP_THRESHOLD_PCT:
        return "↓"
    return "→"


def _kpi_with_trend(kpi_column: str, latest_row: pd.Series, prior_row: pd.Series,
                     company_id: str, latest_year: str, prior_year: str, flagged_keys: set, fmt: str = "{:.1f}%") -> str:
    latest_value = latest_row.get(kpi_column)
    prior_value = prior_row.get(kpi_column) if prior_row is not None else None
    is_scale_sensitive = kpi_column in SCALE_SENSITIVE_KPIS
    is_flagged = (company_id, latest_year) in flagged_keys or (prior_row is not None and (company_id, prior_year) in flagged_keys)

    value_str = fmt.format(latest_value) if pd.notna(latest_value) else "N/A"
    if is_scale_sensitive and is_flagged:
        return f"{value_str} [!]"
    arrow = _trend_arrow(latest_value, prior_value) if prior_row is not None else ""
    return f"{value_str} {arrow}".strip()


def build_portfolio_summary(companies_data: list, flagged_keys: set, save_path: str) -> str:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("PortfolioTitle", parent=styles["Heading1"], fontSize=16))
    styles.add(ParagraphStyle("PortfolioSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey))

    doc = SimpleDocTemplate(save_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []

    for i, data in enumerate(companies_data):
        story.append(Paragraph(f"{data['company_id']} -- {data['company_name']}", styles["PortfolioTitle"]))
        story.append(Paragraph(f"{data['broad_sector']} · Latest year: {data['latest_year']}", styles["PortfolioSub"]))
        story.append(Spacer(1, 0.5 * cm))

        table_data = [
            ["KPI", "ROE", "ROCE", "NPM", "D/E", "FCF (Rs.Cr)", "EPS"],
            ["Value & 3yr trend"] + data["kpi_display"],
        ]
        table = Table(table_data, colWidths=[3.2 * cm] + [2.2 * cm] * 6)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(table)

        if data["has_caveat"]:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                "[!] = data-quality caveat for this metric/year (see Sprint 2 findings) -- shown instead "
                "of a trend arrow to avoid implying a misleading direction.", styles["PortfolioSub"],
            ))

        if i < len(companies_data) - 1:
            story.append(PageBreak())

    doc.build(story)
    return save_path


def run() -> str:
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db"))
    try:
        companies = pd.read_sql("SELECT id AS company_id, company_name FROM companies", conn)
        sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
        fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    finally:
        conn.close()

    roce_notes = pd.read_csv(os.path.join(OUTPUT_DIR, "sector_roce_notes.csv"))
    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    companies_data = []
    for company_id in companies["company_id"]:
        fr_c = fr_all[fr_all["company_id"] == company_id].sort_values("year")
        if fr_c.empty:
            continue
        latest_row = fr_c.iloc[-1]
        latest_year = latest_row["year"]
        latest_calendar_year = int(latest_year[:4])

        # 3yr-prior row: matched by calendar year, same reasoning as
        # cagr.py's by_year lookup (gap years exist in this dataset --
        # positional "3 rows back" would be wrong for a company with a
        # missing year, e.g. EICHERMOT).
        prior_candidates = fr_c[fr_c["year"].str[:4].astype(int) == latest_calendar_year - 3]
        prior_row = prior_candidates.iloc[0] if not prior_candidates.empty else None
        prior_year = prior_row["year"] if prior_row is not None else None

        roce_row = roce_notes[roce_notes["company_id"] == company_id]
        latest_roce = roce_row.iloc[0]["computed_roce_pct"] if not roce_row.empty else None
        latest_row_with_roce = latest_row.copy()
        latest_row_with_roce["computed_roce_pct"] = latest_roce

        roce_flagged = (company_id, latest_year) in flagged_keys
        roce_display = f"{latest_roce:.1f}% [!]" if (pd.notna(latest_roce) and roce_flagged) else (
            f"{latest_roce:.1f}%" if pd.notna(latest_roce) else "N/A"
        )

        kpi_display = [
            _kpi_with_trend("return_on_equity_pct", latest_row, prior_row, company_id, latest_year, prior_year, flagged_keys),
            roce_display,  # no 3yr trend for ROCE -- not persisted per year, same limitation as the tearsheet chart
            _kpi_with_trend("net_profit_margin_pct", latest_row, prior_row, company_id, latest_year, prior_year, flagged_keys),
            _kpi_with_trend("debt_to_equity", latest_row, prior_row, company_id, latest_year, prior_year, flagged_keys, fmt="{:.2f}"),
            _kpi_with_trend("free_cash_flow_cr", latest_row, prior_row, company_id, latest_year, prior_year, flagged_keys, fmt="{:.0f}"),
            _kpi_with_trend("earnings_per_share", latest_row, prior_row, company_id, latest_year, prior_year, flagged_keys, fmt="Rs.{:.1f}"),
        ]

        company_row = companies[companies["company_id"] == company_id].iloc[0]
        sector_row = sectors[sectors["company_id"] == company_id]
        broad_sector = sector_row.iloc[0]["broad_sector"] if not sector_row.empty else "N/A"

        companies_data.append({
            "company_id": company_id, "company_name": company_row["company_name"],
            "broad_sector": broad_sector, "latest_year": latest_year,
            "kpi_display": kpi_display, "has_caveat": "[!]" in " ".join(kpi_display) or "[!]" in roce_display,
        })

    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    date_stamp = datetime.date.today().strftime("%Y%m%d")
    save_path = os.path.join(PORTFOLIO_DIR, f"portfolio_summary_{date_stamp}.pdf")
    build_portfolio_summary(companies_data, flagged_keys, save_path)
    return save_path


if __name__ == "__main__":
    path = run()
    print(f"Portfolio summary written -> {path}")
