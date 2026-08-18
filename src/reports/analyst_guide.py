"""Sprint 6, Day 44: analyst_guide.pdf -- how to use the screener and
dashboard. AC-20 requires >=10 pages covering screener + dashboard
sections; this covers those two plus peer comparison, valuation, the API,
and a dedicated data-quality caveats section, since an analyst guide that
doesn't mention the one data issue that's been flagged at every review
point of this project (BEL/HAL/INDIGO/LT) would be a genuinely misleading
document, not just an incomplete one.
"""

import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem
)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "analyst_guide.pdf")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1Custom", fontSize=20, spaceAfter=16, textColor=colors.HexColor("#1e3a8a")))
styles.add(ParagraphStyle(name="H2Custom", fontSize=14, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#1e3a8a")))
styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=10, spaceAfter=8, leading=14))
styles.add(ParagraphStyle(name="Caveat", parent=styles["Normal"], fontSize=10, spaceAfter=8, leading=14,
                          backColor=colors.HexColor("#fff3c4"), borderPadding=6))


def build_story():
    story = []

    story.append(Paragraph("Nifty 100 Financial Intelligence Platform", styles["H1Custom"]))
    story.append(Paragraph("Analyst Guide", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "This guide covers how to use the Screener, Peer Comparison, and other dashboard screens, "
        "plus the REST API, to analyze the 92 companies in this platform. It also documents a known "
        "data-quality issue that affects a small number of companies -- read the Data Quality Caveats "
        "section before drawing conclusions from ROE, ROCE, D/E, or Asset Turnover for any company.",
        styles["Body"]
    ))
    story.append(PageBreak())

    # --- Getting Started ---
    story.append(Paragraph("1. Getting Started", styles["H2Custom"]))
    story.append(Paragraph(
        "The platform has three ways to access data: the Streamlit dashboard (for interactive browsing), "
        "the REST API (for programmatic access), and the raw SQLite database at data/nifty100.db "
        "(for direct SQL queries or exports to Excel/Python).",
        styles["Body"]
    ))
    story.append(Paragraph(
        "To start the dashboard: <font face='Courier'>streamlit run src/dashboard/app.py</font>, "
        "then open http://localhost:8501. To start the API: <font face='Courier'>uvicorn src.api.main:app "
        "--port 8000</font>, then browse http://localhost:8000/docs for interactive API documentation.",
        styles["Body"]
    ))
    story.append(Paragraph(
        "Coverage note: the platform tracks 92 companies, not the full 100 implied by \"Nifty 100\" -- "
        "8 tickers present in the raw source files were found to be genuinely absent from the master "
        "company reference file during data cleaning, and were excluded consistently across every table "
        "rather than left as orphaned records with no company profile.",
        styles["Body"]
    ))

    # --- Dashboard Overview ---
    story.append(Paragraph("2. Dashboard Screens", styles["H2Custom"]))
    dashboard_screens = [
        ("Overview (Home)", "Summary KPIs (median ROE, median P/E), sector distribution, ROE distribution histogram, and a market-health banner. ROE is shown as a median, not a mean -- a handful of companies with unusually extreme ROE values would otherwise distort a simple average (see Section 6)."),
        ("Company Profile", "Search any of the 92 companies by ticker or name. Shows KPI tiles, 10-year P&L/balance sheet/cash flow charts, and pros/cons. If a company's data carries a data-quality caveat for its latest year, a warning banner appears above the KPI tiles -- read it before citing the numbers below it."),
        ("Screener", "Filter companies by ROE, D/E, FCF, P/E, P/B, dividend yield, CAGR thresholds, and sector. Results below the filter sliders are highlighted in yellow if they carry a data-quality caveat. Results can be downloaded as CSV."),
        ("Peer Comparison", "Select one of 11 peer groups to see an 8-axis radar chart (ROE, ROCE, NPM, D/E, FCF, and 3 CAGR metrics) and a side-by-side percentile table. Not every company belongs to a peer group -- coverage is 56 of 92 companies."),
        ("Trend Analysis", "10-year sparkline for any single P&L/balance-sheet metric per company, with year-over-year % change, or an overlay of multiple metrics at once."),
        ("Sector Analysis", "Bubble chart (revenue vs. ROE, sized by market cap) and sector median KPI comparison. Extreme ROE outliers are excluded from the bubble chart display for readability, with a note showing how many were excluded."),
        ("Capital Allocation Map", "Treemap of all companies by their latest year's cash-flow sign pattern (8 categories, e.g. \"Reinvestor\", \"Distress\"). Click any segment to drill into the underlying company list."),
        ("Annual Reports", "Links to BSE-hosted annual report PDFs per company/year, where available. Link presence does not guarantee the link currently resolves -- see Section 5."),
        ("Valuation", "P/E, P/B, EV/EBITDA, dividend yield, and FCF yield per company, with an overvaluation flag. IMPORTANT: market cap and valuation multiples in this dataset are SIMULATED, not real market prices -- see Section 7."),
    ]
    for name, desc in dashboard_screens:
        story.append(Paragraph(f"<b>{name}</b>", styles["Body"]))
        story.append(Paragraph(desc, styles["Body"]))
    story.append(PageBreak())

    # --- Screener Guide ---
    story.append(Paragraph("3. Screener Guide", styles["H2Custom"]))
    story.append(Paragraph(
        "The screener applies threshold filters defined in config/screener_config.yaml to the latest "
        "reported year of every company. Six presets are built in:",
        styles["Body"]
    ))
    preset_table_data = [
        ["Preset", "Criteria"],
        ["Quality", "ROE > 15%, D/E < 1.0, FCF > 0"],
        ["Value", "P/E < 20x, P/B < 3x"],
        ["Growth", "5yr PAT CAGR > 20%"],
        ["Dividend", "Dividend yield > 2%"],
        ["Momentum", "5yr Revenue CAGR > 15%"],
        ["Debt-Free", "Borrowings = 0"],
    ]
    table = Table(preset_table_data, colWidths=[1.3 * inch, 4 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "Debt/Equity filters automatically exclude financial-sector companies (banks, NBFCs, insurers) "
        "from the D/E threshold -- their business model runs on leverage, so a D/E<1 \"quality\" bar "
        "would disqualify every bank rather than say anything meaningful about quality. This carve-out "
        "is applied consistently, not just for the Quality preset.",
        styles["Body"]
    ))
    story.append(Paragraph(
        "Custom filters: any threshold in screener_config.yaml can be adjusted without touching code. "
        "Add a new named preset by adding a new key under the presets: section and selecting which "
        "thresholds it references.",
        styles["Body"]
    ))
    story.append(PageBreak())

    # --- Peer Comparison Guide ---
    story.append(Paragraph("4. Peer Comparison Guide", styles["H2Custom"]))
    story.append(Paragraph(
        "Percentile ranks are computed within each peer group only -- a company's 80th-percentile ROE "
        "among 5 IT Services peers is not comparable to an 80th percentile among 23 Financials peers. "
        "D/E is inverted in percentile scoring (lower D/E scores higher), since less leverage is "
        "generally the more favorable position, unlike every other axis where higher is better.",
        styles["Body"]
    ))
    story.append(Paragraph(
        "\"Toggle between years\" is not available on this screen -- peer percentiles are computed for "
        "each company's latest reported year only, not a historical series. Companies not assigned to "
        "any peer group (36 of 92) still appear on the dashboard's radar charts (reports/radar_charts/), "
        "benchmarked against the full 92-company universe instead of a specific peer group.",
        styles["Body"]
    ))

    # --- Valuation Guide ---
    story.append(Paragraph("5. Valuation Guide", styles["H2Custom"]))
    story.append(Paragraph(
        "Overvaluation is flagged when at least 2 of 3 valuation multiples exceed their spec-defined "
        "\"fair\" upper bound: P/E > 25x, P/B > 3x, EV/EBITDA > 18x. Because this dataset's simulated "
        "market cap data has a median P/E of ~46x and median P/B of ~7.5x -- both already above those "
        "\"fair\" thresholds -- a large majority of companies (roughly 80-90%) will trip this flag. "
        "This reflects the simulated dataset's own central tendency, not a real signal that most of the "
        "Nifty 100 is mispriced. Use the flag as a relative screen within this dataset, not as investment advice.",
        styles["Body"]
    ))
    story.append(PageBreak())

    # --- Data Quality Caveats (the section the Sprint 6 kickoff instructions specifically asked for) ---
    story.append(Paragraph("6. Data Quality Caveats -- Read Before Using ROE, ROCE, D/E, or Asset Turnover", styles["H2Custom"]))
    story.append(Paragraph(
        "Four companies -- <b>BEL, HAL, INDIGO, and LT</b> -- have balance sheet figures (total assets, "
        "equity, reserves, borrowings) that appear scaled roughly 100x too small relative to their P&L "
        "for certain years. This was found by manually cross-checking ROCE values during Sprint 2 and "
        "confirmed against each company's Sales/Total Assets ratio, which reaches into the hundreds "
        "(INDIGO: 354x in FY2013; a normal company like TCS is ~1.5x).",
        styles["Caveat"]
    ))
    story.append(Paragraph(
        "This was NOT corrected in the underlying data -- there was no reliable way to determine the "
        "true scale factor without the original source workbook, and guessing wrong would have injected "
        "fabricated numbers into real financial data. Instead, every affected company-year is flagged:",
        styles["Body"]
    ))
    story.append(ListFlowable([
        ListItem(Paragraph("The exact affected (company, year) pairs are listed in output/scale_anomaly_flags.csv and output/ratio_edge_cases.log.", styles["Body"])),
        ListItem(Paragraph("The dashboard's Company Profile, Screener, Peer Comparison, and Valuation screens all show a warning banner or highlighted row for affected companies.", styles["Body"])),
        ListItem(Paragraph("The API's /companies/{ticker}/ratios, /screener, /sectors/{sector}/companies, and /peers endpoints attach a data_quality_caveat field to affected rows.", styles["Body"])),
        ListItem(Paragraph("cluster_labels.csv marks affected companies' cluster assignment as UNRELIABLE, since ROE and D/E are 2 of the 5 KMeans clustering inputs.", styles["Body"])),
    ], bulletType="bullet"))
    story.append(Paragraph(
        "Not affected: every other company, and every other year for these 4 companies (e.g. HAL's "
        "2013-2015 data is clean; only 2016 onward is flagged). Other metrics not derived from the "
        "balance sheet (e.g. Net Profit Margin, EPS) are unaffected even in flagged years.",
        styles["Body"]
    ))

    # --- Other known limitations ---
    story.append(Paragraph("7. Other Known Limitations", styles["H2Custom"]))
    limitations = [
        "market_cap.xlsx and stock_prices.xlsx are SIMULATED data (per the original project spec), not real market prices -- every valuation multiple and price chart in this platform is a demonstration of the methodology, not real financial information.",
        "Annual report links (documents.xlsx) are shown by presence only -- a link being on file does not guarantee it currently resolves; automated URL validation is available (src/etl/validator.py, DQ-13) but disabled by default since it's slow.",
        "analysis.xlsx and prosandcons.xlsx have partial coverage (~9-17% of companies) -- most companies will show \"no data available\" on those specific fields.",
        "CAGR figures (Revenue, PAT, EPS) are computed on demand from the underlying P&L data, not stored in the database -- they will not appear in raw SQL queries against financial_ratios.",
    ]
    story.append(ListFlowable([ListItem(Paragraph(item, styles["Body"])) for item in limitations], bulletType="bullet"))
    story.append(PageBreak())

    # --- API Quick Reference ---
    story.append(Paragraph("8. API Quick Reference", styles["H2Custom"]))
    story.append(Paragraph(
        "Base URL: http://localhost:8000/api/v1. Interactive documentation (Swagger UI): "
        "http://localhost:8000/docs. All 16 endpoints return JSON.",
        styles["Body"]
    ))
    api_table_data = [
        ["Endpoint", "Purpose"],
        ["GET /companies", "List/search companies, filter by sector"],
        ["GET /companies/{ticker}", "Full company profile + latest KPIs"],
        ["GET /companies/{ticker}/pl|bs|cashflow", "Raw financial statement history"],
        ["GET /companies/{ticker}/ratios", "Computed KPI history, with caveat flags"],
        ["GET /companies/{ticker}/tearsheet", "PDF tearsheet download"],
        ["GET /companies/{ticker}/documents", "Annual report links"],
        ["GET /companies/{ticker}/peers/compare", "Radar data vs. peer group average"],
        ["GET /screener", "Filtered company list by threshold params"],
        ["GET /sectors", "Sector-level median KPIs"],
        ["GET /sectors/{sector}/companies", "Companies in one sector"],
        ["GET /peers/{group_name}", "All members of a peer group with percentiles"],
        ["GET /market-cap/{ticker}", "Valuation multiples (SIMULATED data)"],
        ["GET /portfolio/stats", "P10-P90 percentile table, 10 KPIs"],
        ["GET /health", "Service status, DB row counts, uptime"],
    ]
    table2 = Table(api_table_data, colWidths=[2.3 * inch, 3.2 * inch])
    table2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(table2)

    story.append(PageBreak())

    # --- Common Workflows ---
    story.append(Paragraph("9. Common Analyst Workflows", styles["H2Custom"]))

    story.append(Paragraph("<b>Workflow A -- Find quality companies undervalued relative to the sector</b>", styles["Body"]))
    story.append(ListFlowable([
        ListItem(Paragraph("Open the Screener screen, enable the ROE and D/E sliders, set ROE ≥ 15% and D/E ≤ 1.0.", styles["Body"])),
        ListItem(Paragraph("Sort the results table by P/E ascending (click the column header) to surface the cheapest names within that quality filter.", styles["Body"])),
        ListItem(Paragraph("Cross-check any candidate on the Sector Analysis screen -- compare its P/E against the sector median bar chart before concluding it's cheap in absolute terms.", styles["Body"])),
        ListItem(Paragraph("Open the candidate's Company Profile to check the pros/cons and confirm there's no data-quality caveat banner before relying on its ROE.", styles["Body"])),
    ], bulletType="bullet"))

    story.append(Paragraph("<b>Workflow B -- Compare a company against its direct peers</b>", styles["Body"]))
    story.append(ListFlowable([
        ListItem(Paragraph("Open Peer Comparison, select the company's peer group from the dropdown.", styles["Body"])),
        ListItem(Paragraph("Read the radar chart: axes further from center = higher percentile within the group on that metric. The dashed line at the midpoint represents the group average by definition.", styles["Body"])),
        ListItem(Paragraph("Use the side-by-side table below the chart for exact values rather than estimating from the radar shape.", styles["Body"])),
        ListItem(Paragraph("If the company isn't in the dropdown's member list at all, it has no peer group assigned (56 of 92 companies do) -- use Sector Analysis instead for a broader comparison.", styles["Body"])),
    ], bulletType="bullet"))

    story.append(Paragraph("<b>Workflow C -- Investigate one company in depth via the API</b>", styles["Body"]))
    story.append(ListFlowable([
        ListItem(Paragraph("GET /api/v1/companies/{ticker} for the profile + latest KPIs in one call.", styles["Body"])),
        ListItem(Paragraph("GET /api/v1/companies/{ticker}/ratios for the full multi-year KPI history -- check every row's data_quality_caveat field before using ROCE/D-E/Asset Turnover from any specific year.", styles["Body"])),
        ListItem(Paragraph("GET /api/v1/companies/{ticker}/peers/compare for a machine-readable version of the radar chart data.", styles["Body"])),
        ListItem(Paragraph("GET /api/v1/companies/{ticker}/tearsheet to download the 2-page PDF summary for offline review.", styles["Body"])),
    ], bulletType="bullet"))
    story.append(PageBreak())

    # --- KPI Glossary ---
    story.append(Paragraph("10. KPI Glossary", styles["H2Custom"]))
    story.append(Paragraph(
        "Formulas and interpretation for the KPIs used throughout the platform. \"None\" in the Edge Case "
        "column means the platform stores a null value rather than a computed number when that condition "
        "is met, so the dashboard/API can distinguish \"cannot be computed\" from \"computed as zero\".",
        styles["Body"]
    ))
    glossary_data = [
        ["Metric", "Formula", "Edge Case"],
        ["Net Profit Margin (NPM)", "net_profit / sales × 100", "None if sales = 0"],
        ["Operating Profit Margin (OPM)", "operating_profit / sales × 100", "None if sales = 0"],
        ["Return on Equity (ROE)", "net_profit / (equity + reserves) × 100", "None if equity+reserves ≤ 0"],
        ["Return on Capital (ROCE)", "EBIT / (equity + reserves + borrowings) × 100", "Sector-relative for banks/NBFCs"],
        ["Debt-to-Equity (D/E)", "borrowings / (equity + reserves)", "0 = debt-free; financials excluded from >5 flag"],
        ["Interest Coverage (ICR)", "(op_profit + other_income) / interest", "999 sentinel = debt-free (interest=0)"],
        ["Asset Turnover", "sales / total_assets", "None if total_assets = 0"],
        ["Free Cash Flow (FCF)", "operating_activity + investing_activity", "Negative allowed"],
        ["Revenue/PAT/EPS CAGR", "(end/start)^(1/n) − 1, n∈{3,5,10}yr", "Turnaround flag if base ≤ 0, end > 0"],
        ["Book Value / Share", "(equity+reserves) / (equity_capital/face_value)", "None if face_value missing/zero"],
        ["CFO Quality Score", "operating_activity / net_profit", ">1.0 = high quality; <0.5 = accrual risk"],
        ["CapEx Intensity", "abs(investing_activity) / sales × 100", ">8% = capital intensive"],
        ["FCF Yield", "FCF / market_cap_crore × 100", "Requires market_cap (SIMULATED data)"],
    ]
    table3 = Table(glossary_data, colWidths=[1.5 * inch, 2.3 * inch, 1.9 * inch])
    table3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(table3)
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "Capital allocation patterns (Capital Allocation Map screen): classified by the sign of "
        "(CFO, CFI, CFF) for each company's latest year. \"Reinvestor\" and \"Shareholder Returns\" "
        "share the same (+,-,-) sign pattern and are distinguished by CFO/PAT quality; \"Distress\" is "
        "(-,?,+) -- negative operating cash flow covered by raising external funds. The remaining 5 of "
        "the 8 possible sign combinations are labelled using standard capital-allocation terminology, "
        "since the source specification only names 3 of the 8 explicitly.",
        styles["Body"]
    ))
    story.append(PageBreak())

    # --- Troubleshooting / FAQ ---
    story.append(Paragraph("11. Troubleshooting", styles["H2Custom"]))
    faq = [
        ("A metric shows \"N/A\" for a company I know reports it.",
         "Check whether the underlying source value was actually zero, negative, or missing for that "
         "company-year -- most KPIs here deliberately show None/N/A instead of a computed number in "
         "edge cases (e.g. ROE when equity is negative, NPM when sales is zero) rather than returning a "
         "misleading value. See the KPI Glossary (Section 10) for the specific edge-case rule per metric."),
        ("A company doesn't appear in the Peer Comparison dropdown for a sector I'd expect.",
         "Peer group membership (peer_groups.xlsx) is a separate, manually-curated dataset from sector "
         "classification (sectors.xlsx) and covers only 56 of 92 companies. A company can have a sector "
         "but no peer group, or vice versa is not possible since peer groups reference specific tickers."),
        ("The Valuation screen flags almost every company as overvalued.",
         "This is expected given the simulated market_cap data's central tendency -- see Section 5 "
         "(Valuation Guide) for the full explanation. It is not a bug and not a real market signal."),
        ("A ratio for BEL, HAL, INDIGO, or LT looks implausibly large (e.g. ROE in the thousands of percent).",
         "This is the known scale anomaly documented in Section 6. Check the data_quality_caveat field "
         "(API) or warning banner (dashboard) before using that specific company-year's ROCE, D/E, Asset "
         "Turnover, or Book Value/Share."),
        ("The dashboard or API is slow on first load.",
         "Both cache expensive computations (screener universe, CAGR calculations) after the first "
         "request -- subsequent requests within the cache window (10 minutes) are fast. The very first "
         "request after starting either service will be slower while the cache warms."),
    ]
    for question, answer in faq:
        story.append(Paragraph(f"<b>Q: {question}</b>", styles["Body"]))
        story.append(Paragraph(f"A: {answer}", styles["Body"]))
        story.append(Spacer(1, 0.05 * inch))

    return story


def run() -> str:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=letter,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    doc.build(build_story())
    return OUTPUT_PATH


if __name__ == "__main__":
    path = run()
    print(f"analyst_guide.pdf written to {path}")
