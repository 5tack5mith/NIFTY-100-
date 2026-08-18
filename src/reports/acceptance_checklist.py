"""D-23 deliverable: docs/acceptance_checklist.pdf

Renders the honest 20-criteria (AC-01 through AC-20) pass reported
verbally at the end of Sprint 6, plus the Sprint 6+ closeout verification
pass. Verdicts here are NOT upgraded for appearance -- a PARTIAL or FAIL
stays exactly what it was found to be, with the reasoning that produced
it, since the entire point of this document is to be an honest record
rather than a rubber-stamped "all pass" checklist.
"""

import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "acceptance_checklist.pdf")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1Custom", fontSize=18, spaceAfter=12, textColor=colors.HexColor("#1e3a8a")))
styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=9.5, spaceAfter=6, leading=13))
styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=7.5, leading=10))

VERDICT_COLORS = {
    "PASS": colors.HexColor("#4ADE80"),
    "PARTIAL": colors.HexColor("#FDE68A"),
    "FAIL": colors.HexColor("#F87171"),
    "UNMEASURED": colors.HexColor("#CBD5E1"),
}

# (id, criterion, verdict, reasoning) -- verbatim from the honest pass
# reported at Sprint 6 closeout, re-verified during the D-01..D-23
# deliverables tracker pass. Not upgraded.
ACCEPTANCE_CRITERIA = [
    ("AC-01", "92 companies present, no extra/missing tickers", "PASS", "SELECT COUNT(*) FROM companies = 92, verified directly."),
    ("AC-02", "≥ 90% of companies have ≥ 10yr P&L/BS/CF records", "PASS", "93.4-95.7% across all three tables."),
    ("AC-03", "All FK relationships intact (PRAGMA foreign_key_check = 0 rows)", "PASS", "0 violations, verified directly."),
    ("AC-04", "financial_ratios ≥ 1,100 rows, all 14 KPI columns populated", "FAIL", "1,070 rows (short by 30) and 13 declared columns, not 14 -- financial_ratios.xlsx's own schema (spec Section 6.4) never declared a 14th column. Each column is 97.5-99.9% populated, not fully null-free."),
    ("AC-05", "Revenue CAGR for 3 companies matches hand-computed value ± 0.1%", "PASS", "Recomputed independently from raw sales figures via SQL, not by calling the engine's own code."),
    ("AC-06", "ROE for 5 companies matches companies.roe_percentage ± 5%", "PASS*", "4/5 within 3 percentage points. TCS is off by 50pp, but the spec itself (Section 5.1) flags companies.roe_percentage=0.52 for TCS as a known anomaly and says to trust the Ratio Engine value instead -- which is what this platform does."),
    ("AC-07", "Quality preset screener produces 10-50 companies", "PASS", "38 companies matched."),
    ("AC-08", "Company Profile screen loads in < 3 seconds", "UNMEASURED", "Qualitatively fast in every manual test across every sprint; no automated click-to-render timing harness available in this environment to produce a rigorous number."),
    ("AC-09", "Screener CSV download is well-formed with correct headers", "PASS", "Round-trips cleanly through a full write/parse cycle; headers match exactly."),
    ("AC-10", "No text overflow or overlapping pages in generated reports", "PARTIAL", "Text-extraction check on 5 random tearsheets confirms correct 2-page structure and real content on every page. Cannot visually confirm absence of overlap/overflow -- no PDF renderer (poppler) available in this environment."),
    ("AC-11", "GET /api/v1/health returns HTTP 200 with db_row_counts for all 10 tables", "PARTIAL", "Returns 200 with row counts for all 12 real tables. The database has 12 tables, not 10 -- same discrepancy documented in db/schema.sql since Sprint 1 (the spec's own \"10 tables\" claim doesn't match its own entity-relationship map, which names 12)."),
    ("AC-12", "GET /api/v1/companies/TCS/ratios returns rows for ≥ 10 years", "PASS", "12 rows returned."),
    ("AC-13", "GET /api/v1/screener?min_roe=15&max_de=1 is consistent with Module 3 output", "PASS", "API and the underlying screener engine agree exactly (49 companies). No sheet in screener_output.xlsx has this exact 2-filter combination pre-computed to diff against directly (the Quality preset adds a 3rd filter, FCF), but the live consistency check confirms the same logic drives both."),
    ("AC-14", "Peer percentile table populated for all 11 peer groups, all members present", "PASS", "11/11 groups; all 56 members present in both peer_groups and peer_percentiles."),
    ("AC-15", "All 92 companies assigned to a cluster (0-4), no nulls", "PASS", "Verified directly: 0 nulls, all 92 assigned."),
    ("AC-16", "pros_cons_generated.csv has ≥ 1 pro and ≥ 1 con for every company", "PASS", "0 companies missing either a pro or a con."),
    ("AC-17", "92 tearsheet PDFs exist, each ≥ 50KB", "PASS", "All 92 present, all above the size threshold."),
    ("AC-18", "pytest shows ≥ 60 tests collected, 0 failures", "PASS", "169 tests passing, well over the threshold."),
    ("AC-19", "validation_failures.csv: every row has company_id, field, issue, severity", "PARTIAL", "1 of 317 rows (a DQ-16 coverage warning for JIOFIN) has a null field value -- DQ-16 measures year-count across a company's whole history, which doesn't naturally map to one column."),
    ("AC-20", "analyst_guide.pdf exists, ≥ 10 pages, covers screener and dashboard", "PASS", "Exactly 10 pages. Both required sections present, plus peer comparison, valuation, API reference, KPI glossary, and a dedicated data-quality-caveats section."),
]


def build_story():
    story = []
    story.append(Paragraph("Nifty 100 Financial Intelligence Platform", styles["H1Custom"]))
    story.append(Paragraph("Acceptance Checklist -- 20 Quality Gates", styles["Heading2"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "This is an honest verification record, not a sign-off formality. Each criterion below was "
        "checked against real data/files/running services at the time of writing -- not assumed correct "
        "because the underlying code exists or ran without error. PARTIAL and FAIL verdicts are reported "
        "as found; none were adjusted for appearance. Summary: 15 PASS (2 with a caveat, marked PASS*), "
        "3 PARTIAL, 1 FAIL, 1 UNMEASURED.",
        styles["Body"]
    ))
    story.append(Spacer(1, 0.15 * inch))

    table_data = [["ID", "Criterion", "Verdict", "Notes"]]
    for ac_id, criterion, verdict, notes in ACCEPTANCE_CRITERIA:
        table_data.append([
            ac_id,
            Paragraph(criterion, styles["Cell"]),
            verdict,
            Paragraph(notes, styles["Cell"]),
        ])

    table = Table(table_data, colWidths=[0.5 * inch, 1.7 * inch, 0.65 * inch, 3.65 * inch], repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row_idx, (_, _, verdict, _) in enumerate(ACCEPTANCE_CRITERIA, start=1):
        base_verdict = verdict.rstrip("*")
        color = VERDICT_COLORS.get(base_verdict, colors.white)
        style_commands.append(("BACKGROUND", (2, row_idx), (2, row_idx), color))
    table.setStyle(TableStyle(style_commands))
    story.append(table)

    story.append(PageBreak())
    story.append(Paragraph("Notes on the 3 Deliverables-Tracker Path Mismatches", styles["Heading2"]))
    story.append(Paragraph(
        "During the D-01 through D-23 deliverables verification pass (separate from this 20-criteria "
        "check), 3 files were found to exist with real content but at a different path than the "
        "deliverables tracker states: D-04 (exploratory_queries.sql is at db/, not notebooks/), D-17 "
        "(only 10 sector report PDFs exist, matching the 10 real broad sectors in sectors.xlsx -- the "
        "tracker's \"11\" does not match the real data, same gap documented since Sprint 1's sector "
        "distribution finding), and D-22 (analyst_guide.pdf is at reports/, not docs/). None of these "
        "are missing deliverables -- all exist with substantive, verified content -- but the tracker's "
        "stated paths/counts don't match where the work actually landed.",
        styles["Body"]
    ))
    story.append(Paragraph(
        "Also found during that pass: the \"simulated data must be labeled SIMULATED\" rule is only "
        "partially satisfied -- 2 of 4 dashboard screens that display market_cap-derived data (Sector "
        "Analysis, Valuation) show the notice; 2 (Home, Screener) do not.",
        styles["Body"]
    ))

    return story


def run() -> str:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=letter,
                             topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                             leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    doc.build(build_story())
    return OUTPUT_PATH


if __name__ == "__main__":
    path = run()
    print(f"acceptance_checklist.pdf written to {path}")
