"""Sprint 5, Day 33-35: Sector Report PDF generator (Module 8.3, D-17).

One PDF per broad_sector (11 total), written to
reports/sector/<SECTOR>_report_<YYYYMMDD>.pdf per spec's filename
convention. Sector header, sector median KPI table, company list with
best/worst ROE highlighted.
"""

import datetime
import os
import re
import sys

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports")
SECTOR_DIR = os.path.join(REPORTS_DIR, "sector")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")


def _safe_filename(sector_name: str) -> str:
    """Sector names contain spaces and '&' (e.g. 'Consumer Discretionary',
    'Communication Services') -- not safe as bare filename characters on
    Windows/most filesystems, so this collapses anything non-alphanumeric
    to underscores.
    """
    return re.sub(r"[^A-Za-z0-9]+", "_", sector_name).strip("_")


def build_sector_report(sector_name: str, sector_companies: pd.DataFrame,
                         flagged_keys: set, save_path: str) -> str:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("SectorTitle", parent=styles["Heading1"], fontSize=18))
    styles.add(ParagraphStyle("SectorSub", parent=styles["Normal"], fontSize=9, textColor=colors.grey))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontSize=12, spaceBefore=10))

    doc = SimpleDocTemplate(save_path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    story = [
        Paragraph(sector_name, styles["SectorTitle"]),
        Paragraph(f"{len(sector_companies)} companies · Nifty 100 Financial Intelligence Platform", styles["SectorSub"]),
        Spacer(1, 0.4 * cm),
    ]

    medians = sector_companies[["return_on_equity_pct", "net_profit_margin_pct", "debt_to_equity", "free_cash_flow_cr"]].median()
    story.append(Paragraph("Sector Median KPIs", styles["SectionHeader"]))
    median_table = Table([
        ["Median ROE", "Median NPM", "Median D/E", "Median FCF (Rs.Cr)"],
        [f"{medians['return_on_equity_pct']:.1f}%", f"{medians['net_profit_margin_pct']:.1f}%",
         f"{medians['debt_to_equity']:.2f}", f"{medians['free_cash_flow_cr']:.0f}"],
    ], colWidths=[4 * cm] * 4)
    median_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(median_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Companies (best/worst ROE highlighted)", styles["SectionHeader"]))
    sorted_companies = sector_companies.sort_values("return_on_equity_pct", ascending=False)
    best_id = sorted_companies.iloc[0]["company_id"] if not sorted_companies.empty else None
    worst_id = sorted_companies.iloc[-1]["company_id"] if not sorted_companies.empty else None

    table_data = [["Ticker", "Company", "ROE", "NPM", "D/E", "FCF (Rs.Cr)", "Year"]]
    for _, row in sorted_companies.iterrows():
        caveat_marker = " [!]" if (row["company_id"], row["year"]) in flagged_keys else ""
        table_data.append([
            row["company_id"] + caveat_marker,
            (row.get("company_name", "") or "")[:28],
            f"{row['return_on_equity_pct']:.1f}%" if pd.notna(row["return_on_equity_pct"]) else "N/A",
            f"{row['net_profit_margin_pct']:.1f}%" if pd.notna(row["net_profit_margin_pct"]) else "N/A",
            f"{row['debt_to_equity']:.2f}" if pd.notna(row["debt_to_equity"]) else "N/A",
            f"{row['free_cash_flow_cr']:.0f}" if pd.notna(row["free_cash_flow_cr"]) else "N/A",
            row["year"],
        ])
    company_table = Table(table_data, colWidths=[2 * cm, 5 * cm, 1.8 * cm, 1.8 * cm, 1.6 * cm, 2.2 * cm, 1.8 * cm])
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
    ]
    for i, row in enumerate(sorted_companies.itertuples(), start=1):
        if row.company_id == best_id:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#bbf7d0")))
        elif row.company_id == worst_id:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fecaca")))
    company_table.setStyle(TableStyle(style_commands))
    story.append(company_table)

    if any((cid, yr) in flagged_keys for cid, yr in zip(sector_companies["company_id"], sector_companies["year"])):
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "[!] = this company's ROE/ROCE/D-E figures for the year shown carry a data-quality caveat "
            "(see Sprint 2 findings) -- treat with caution.", styles["SectorSub"],
        ))

    doc.build(story)
    return save_path


def run() -> list:
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db"))
    try:
        companies = pd.read_sql("SELECT id AS company_id, company_name FROM companies", conn)
        sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
        fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    finally:
        conn.close()

    fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
    merged = fr_latest.merge(companies, on="company_id", how="left").merge(sectors, on="company_id", how="left")

    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    os.makedirs(SECTOR_DIR, exist_ok=True)
    date_stamp = datetime.date.today().strftime("%Y%m%d")
    written = []
    for sector_name in sorted(merged["broad_sector"].dropna().unique()):
        sector_companies = merged[merged["broad_sector"] == sector_name]
        filename = f"{_safe_filename(sector_name)}_report_{date_stamp}.pdf"
        save_path = os.path.join(SECTOR_DIR, filename)
        build_sector_report(sector_name, sector_companies, flagged_keys, save_path)
        written.append(save_path)

    return written


if __name__ == "__main__":
    written = run()
    print(f"Sector reports written: {len(written)} -> {SECTOR_DIR}")
