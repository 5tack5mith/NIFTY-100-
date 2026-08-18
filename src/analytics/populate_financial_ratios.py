"""Sprint 2, Days 12-13: populate the financial_ratios table + ROCE sector review.

This is the Ratio Engine's production entry point -- loads the cleaned
Sprint 1 tables, joins them explicitly on (company_id, year) [see
ratios.build_annual_frame() for why that join matters], computes every
metric the financial_ratios table's schema actually declares, and writes
the result into db/../data/nifty100.db, replacing whatever
financial_ratios.xlsx (the Sprint 1 supplementary file) had loaded there.

Also produces the three artifacts the spec asks for from these two days:
- capital_allocation.csv (D-06 deliverable)
- sector_roce_notes.csv (D13 deliverable)
- output/ratio_edge_cases.log (every CAGR turnaround, debt-free
  substitution, and division-by-zero-driven None, so an analyst can see
  exactly which company-years hit an edge case instead of a clean number)

Run with: python src/analytics/populate_financial_ratios.py
"""

import importlib.util
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etl"))

from pipeline import run_pipeline
from ratios import (
    build_annual_frame, net_profit_margin, operating_profit_margin,
    opm_cross_check_flag, return_on_equity, return_on_capital,
    interest_coverage, debt_to_equity, asset_turnover,
    book_value_per_share, DEBT_FREE_SENTINEL,
)
from cagr import cagr_for_company
from cashflow_kpis import (
    free_cash_flow, capex_intensity, cfo_quality_score, fcf_conversion_rate,
    classify_capital_allocation,
)


def _import_db_loader():
    """Load db/loader.py by explicit file path, not by adding db/ to sys.path.

    db/loader.py and src/etl/loader.py have the same bare module name
    ('loader'). If both directories were added to sys.path and imported by
    name, Python's sys.modules cache would key both imports to whichever
    one loaded first -- silently handing this script the wrong module
    (Excel loaders instead of the SQLite connection helper, or vice versa)
    with no error. Loading by explicit path under a distinct internal name
    sidesteps the collision entirely.
    """
    db_loader_path = os.path.join(os.path.dirname(__file__), "..", "..", "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", db_loader_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


db_loader = _import_db_loader()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")


def compute_row_metrics(row: pd.Series, is_financial_sector: bool) -> dict:
    """Compute every financial_ratios column value for one (company_id, year) row."""
    npm = net_profit_margin(row.get("net_profit"), row.get("sales"))
    opm = operating_profit_margin(row.get("operating_profit"), row.get("sales"))
    opm_flag = opm_cross_check_flag(opm, row.get("opm_percentage"))
    roe = return_on_equity(row.get("net_profit"), row.get("equity_capital"), row.get("reserves"))
    roce = return_on_capital(
        row.get("operating_profit"), row.get("depreciation"),
        row.get("equity_capital"), row.get("reserves"), row.get("borrowings"),
        is_financial_sector,
    )
    de = debt_to_equity(row.get("borrowings"), row.get("equity_capital"), row.get("reserves"))
    icr = interest_coverage(row.get("operating_profit"), row.get("other_income"), row.get("interest"))
    at = asset_turnover(row.get("sales"), row.get("total_assets"))
    bvps = book_value_per_share(row.get("equity_capital"), row.get("reserves"), row.get("face_value"))
    fcf = free_cash_flow(row.get("operating_activity"), row.get("investing_activity"))
    capex_cr = abs(row["investing_activity"]) if pd.notna(row.get("investing_activity")) else None

    return {
        "company_id": row["company_id"],
        "year": row["year"],
        "net_profit_margin_pct": npm,
        "operating_profit_margin_pct": opm,
        "_opm_cross_check_flag": opm_flag,  # internal-only, not a DB column -- used for the edge-case log
        "return_on_equity_pct": roe,
        "_roce_pct": roce,  # internal-only -- ROCE isn't a financial_ratios column (see Sprint 2 kickoff note)
        "debt_to_equity": de,
        "interest_coverage": icr,
        "asset_turnover": at,
        "free_cash_flow_cr": fcf,
        "capex_cr": capex_cr,
        "earnings_per_share": row.get("eps"),                     # direct source pass-through, spec 6.4
        "book_value_per_share": bvps,
        "dividend_payout_ratio_pct": row.get("dividend_payout"),  # direct source pass-through, spec 6.4
        "total_debt_cr": row.get("borrowings"),                   # direct source pass-through, spec 6.4
        "cash_from_operations_cr": row.get("operating_activity"), # direct source pass-through, spec 6.4
    }


def run() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tables = run_pipeline(check_urls=False)
    pl, bs, cf = tables["profitandloss"], tables["balancesheet"], tables["cashflow"]
    companies, sectors = tables["companies"], tables["sectors"]

    frame = build_annual_frame(pl, bs, cf)
    # face_value (for book value/share) comes from companies, not any of the
    # 3 annual tables -- join it in as company-level context, same as sector.
    frame = frame.merge(companies[["id", "face_value", "roce_percentage"]],
                         left_on="company_id", right_on="id", how="left").drop(columns=["id"])
    frame = frame.merge(sectors[["company_id", "broad_sector"]], on="company_id", how="left")
    frame["is_financial_sector"] = frame["broad_sector"] == "Financials"

    edge_cases = []  # collected for ratio_edge_cases.log
    financial_ratios_rows = []
    roce_rows = []  # for sector_roce_notes.csv
    scale_anomaly_rows = []  # structured version of the SUSPECTED_SCALE_ANOMALY
    # log lines, for Sprint 3's screener/ranking code to consume programmatically --
    # parsing the free-text .log file downstream would be fragile and would
    # couple the screener to this module's exact log message format.

    for _, row in frame.iterrows():
        metrics = compute_row_metrics(row, row["is_financial_sector"])

        if metrics["_opm_cross_check_flag"]:
            edge_cases.append(
                f"OPM_CROSS_CHECK_MISMATCH company_id={row['company_id']} year={row['year']} "
                f"computed={metrics['operating_profit_margin_pct']:.2f} stated={row.get('opm_percentage')}"
            )
        if metrics["interest_coverage"] == DEBT_FREE_SENTINEL:
            edge_cases.append(
                f"DEBT_FREE_SUBSTITUTION company_id={row['company_id']} year={row['year']} "
                f"interest=0 -> ICR set to sentinel {DEBT_FREE_SENTINEL}"
            )
        for field in ["net_profit_margin_pct", "return_on_equity_pct", "debt_to_equity", "asset_turnover"]:
            if metrics[field] is None:
                edge_cases.append(
                    f"NONE_RESULT field={field} company_id={row['company_id']} year={row['year']}"
                )

        # BEL/HAL/INDIGO/LT scale anomaly, found while manually cross-checking
        # ROCE anomalies for D13: their balance sheet figures (total_assets,
        # equity, reserves) look scaled ~100x too small relative to their
        # P&L for several years -- e.g. HAL FY24 has total_assets=450 vs
        # sales=30,381 (67x asset turnover; TCS, a normal company, is ~1.5x).
        # Not corrected here -- no reliable source to verify the true scale
        # factor against, and guessing wrong would inject fabricated numbers
        # into real financial data. Values are left as-is in
        # financial_ratios (per team decision) but every affected row is
        # flagged here so nothing downstream treats these BS-dependent
        # ratios as trustworthy without a human looking at them first.
        if pd.notna(row.get("sales")) and pd.notna(row.get("total_assets")) and row["total_assets"] > 0:
            implied_asset_turnover = row["sales"] / row["total_assets"]
            if implied_asset_turnover > 20:
                edge_cases.append(
                    f"SUSPECTED_SCALE_ANOMALY company_id={row['company_id']} year={row['year']} "
                    f"sales/total_assets={implied_asset_turnover:.1f}x (>20x, implausible -- "
                    f"balance sheet likely mis-scaled relative to P&L; ROCE/AssetTurnover/D-E/ROE "
                    f"for this row should not be trusted without source verification)"
                )
                scale_anomaly_rows.append({
                    "company_id": row["company_id"],
                    "year": row["year"],
                    "implied_asset_turnover": implied_asset_turnover,
                })

        # CFO Quality Score, CapEx Intensity %, FCF Conversion Rate (D11) --
        # none of these have a financial_ratios column (same situation as
        # ROCE and CAGR: the spec's schema for that table just doesn't
        # declare one), so they're computed and edge-case logged here
        # rather than silently left unused.
        cfo_quality = cfo_quality_score(row.get("operating_activity"), row.get("net_profit"))
        if cfo_quality is not None and cfo_quality < 0.5:
            edge_cases.append(
                f"CFO_QUALITY_ACCRUAL_RISK company_id={row['company_id']} year={row['year']} "
                f"CFO/PAT={cfo_quality:.2f} (<0.5 threshold)"
            )
        capex_pct = capex_intensity(row.get("investing_activity"), row.get("sales"))
        if capex_pct is not None and capex_pct > 8:
            edge_cases.append(
                f"CAPEX_INTENSITY_HIGH company_id={row['company_id']} year={row['year']} "
                f"capex_intensity={capex_pct:.1f}% (>8% threshold, spec: 'capital intensive')"
            )
        fcf_conv = fcf_conversion_rate(metrics["free_cash_flow_cr"], row.get("operating_profit"))
        if fcf_conv is not None and fcf_conv < 30:
            edge_cases.append(
                f"FCF_CONVERSION_HEAVY company_id={row['company_id']} year={row['year']} "
                f"conversion={fcf_conv:.1f}% (<30% threshold, spec: 'heavy')"
            )

        roce_rows.append({
            "company_id": row["company_id"],
            "year": row["year"],
            "broad_sector": row["broad_sector"],
            "is_financial_sector": row["is_financial_sector"],
            "computed_roce_pct": metrics["_roce_pct"],
        })

        db_row = {k: v for k, v in metrics.items() if not k.startswith("_")}
        financial_ratios_rows.append(db_row)

    financial_ratios_df = pd.DataFrame(financial_ratios_rows)

    # --- Capital allocation classification (D11 -> capital_allocation.csv) ---
    cf_for_alloc = frame[["company_id", "year", "operating_activity", "investing_activity",
                           "financing_activity", "net_profit"]].dropna(
        subset=["operating_activity", "investing_activity", "financing_activity"]
    )
    capital_allocation_rows = []
    for _, r in cf_for_alloc.iterrows():
        pattern = classify_capital_allocation(
            r["operating_activity"], r["investing_activity"], r["financing_activity"], r["net_profit"]
        )
        capital_allocation_rows.append({
            "company_id": r["company_id"],
            "year": r["year"],
            "CFO_sign": "+" if r["operating_activity"] >= 0 else "-",
            "CFI_sign": "+" if r["investing_activity"] >= 0 else "-",
            "CFF_sign": "+" if r["financing_activity"] >= 0 else "-",
            "pattern_label": pattern,
        })
    capital_allocation_df = pd.DataFrame(capital_allocation_rows)
    capital_allocation_df.to_csv(os.path.join(OUTPUT_DIR, "capital_allocation.csv"), index=False)

    # --- ROCE / sector-relative review (D13 -> sector_roce_notes.csv) ---
    roce_df = pd.DataFrame(roce_rows)
    # Cross-check against companies.roce_percentage using each company's
    # MOST RECENT year -- companies.roce_percentage is a static snapshot
    # (spec 5.1: "ROCE % (pre-computed)"), not a per-year series, so
    # comparing every year against one static number would be comparing
    # apples to a single orange; only the latest computed year is a fair
    # like-for-like comparison.
    latest_roce = roce_df.sort_values("year").groupby("company_id").tail(1)
    latest_roce = latest_roce.merge(
        companies[["id", "roce_percentage"]], left_on="company_id", right_on="id", how="left"
    ).drop(columns=["id"])
    latest_roce["diff_from_companies_field"] = (
        latest_roce["computed_roce_pct"] - latest_roce["roce_percentage"]
    )
    # Anomaly threshold: >10 percentage points apart is a real
    # discrepancy worth an analyst's attention, not normal formula
    # rounding noise -- an arbitrary but documented choice, since the spec
    # doesn't give a numeric threshold for this specific cross-check
    # (unlike DQ-05's explicit 1% for OPM).
    latest_roce["anomaly_flag"] = latest_roce["diff_from_companies_field"].abs() > 10
    latest_roce.to_csv(os.path.join(OUTPUT_DIR, "sector_roce_notes.csv"), index=False)

    anomaly_count = latest_roce["anomaly_flag"].sum()
    financial_sector_count = latest_roce["is_financial_sector"].sum()

    # --- CAGR (D10) -- computed and edge-case logged, not persisted yet;
    # see the module docstring for why no DB column exists for this. ---
    cagr_turnaround_count = 0
    for metric_col, metric_name in [("sales", "Revenue"), ("net_profit", "PAT"), ("eps", "EPS")]:
        for company_id, group in pl.sort_values("year").groupby("company_id"):
            series = group.set_index("year")[metric_col]
            result = cagr_for_company(series)
            for window in (3, 5, 10):
                if result[f"turnaround_{window}yr"]:
                    cagr_turnaround_count += 1
                    edge_cases.append(
                        f"CAGR_TURNAROUND metric={metric_name} company_id={company_id} "
                        f"window={window}yr base<=0, end>0"
                    )

    pd.DataFrame(scale_anomaly_rows).to_csv(
        os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"), index=False
    )

    # --- Write ratio_edge_cases.log ---
    log_path = os.path.join(OUTPUT_DIR, "ratio_edge_cases.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Ratio Engine edge case log -- {len(edge_cases)} total events\n")
        f.write(f"CAGR turnaround flags: {cagr_turnaround_count}\n")
        f.write(f"ROCE cross-check anomalies (>10pp vs companies.roce_percentage): {anomaly_count}\n")
        f.write(f"Financial-sector companies (ROCE via sector-relative review): {financial_sector_count}\n")
        f.write("\n" + "\n".join(edge_cases) + "\n")

    # --- Write to SQLite: replace financial_ratios table contents ---
    conn = db_loader.get_connection()
    try:
        conn.execute("DELETE FROM financial_ratios")
        financial_ratios_df.to_sql("financial_ratios", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    print(f"financial_ratios table repopulated: {len(financial_ratios_df)} rows")
    print(f"capital_allocation.csv: {len(capital_allocation_df)} rows")
    print(f"sector_roce_notes.csv: {len(latest_roce)} rows, {anomaly_count} anomalies flagged")
    print(f"ratio_edge_cases.log: {len(edge_cases)} edge cases logged")


if __name__ == "__main__":
    run()
