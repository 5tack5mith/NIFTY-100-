"""Sprint 1 ETL pipeline: load -> clean -> validate -> write outputs.

This is the single production entry point for the core-file load. It exists
because loader.py, cleaner.py and validator.py were each testable in
isolation but nothing tied them together in the right order -- running
validator.py directly (as its __main__ block still allows, for quick
ad-hoc checks) validates the RAW data, which is not what the Day 3 exit
criteria asks for. The exit criteria is "zero CRITICAL violations after
cleaning", so cleaning has to happen in between load and validate, every
time, not as a manual extra step.

Run with: python pipeline.py
Produces: output/load_audit.csv, output/validation_failures.csv
"""

import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from loader import (
    load_companies, load_profitandloss, load_balancesheet,
    load_cashflow, load_documents, load_analysis, load_prosandcons,
    load_sectors, load_stock_prices, load_market_cap,
    load_financial_ratios, load_peer_groups,
)
from cleaner import clean_table
from validator import run_all_checks

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
SUPPORTING_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "supporting")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")


def run_pipeline(check_urls: bool = False) -> dict:
    """Load + clean all 7 core files, validate, write audit/failure CSVs.

    Returns a dict of {table_name: cleaned_dataframe, "validation_results":
    df} rather than just the validation DataFrame, so db/loader.py (Day 4)
    can reuse the exact same cleaned tables instead of duplicating the
    load-and-clean sequence -- there should be exactly one place that
    decides what "clean" means for each table.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start = time.time()
    audits = []

    # companies.xlsx has no company_id column to FK-check against itself,
    # and no year column -- so it skips both cleaning steps (has_year=False,
    # valid_company_ids=None means drop_orphan_rows is never called).
    companies = load_companies(os.path.join(RAW_DIR, "companies.xlsx"))
    companies, audit = clean_table(companies, "companies", has_year=False)
    audits.append(audit)

    # The set of valid tickers, computed once after companies.xlsx is loaded
    # (not cleaned further, since DQ-01 duplicate company PKs are a "halt
    # and investigate" condition per spec, not something we auto-fix) --
    # every child table's DQ-03 orphan check depends on this.
    valid_ids = set(companies["id"])

    pl = load_profitandloss(os.path.join(RAW_DIR, "profitandloss.xlsx"))
    pl, audit = clean_table(pl, "profitandloss", valid_company_ids=valid_ids, has_year=True)
    audits.append(audit)

    bs = load_balancesheet(os.path.join(RAW_DIR, "balancesheet.xlsx"))
    bs, audit = clean_table(bs, "balancesheet", valid_company_ids=valid_ids, has_year=True)
    audits.append(audit)

    cf = load_cashflow(os.path.join(RAW_DIR, "cashflow.xlsx"))
    cf, audit = clean_table(cf, "cashflow", valid_company_ids=valid_ids, has_year=True)
    audits.append(audit)

    # documents.xlsx keys on (company_id, Year) but DQ-02/DQ-07 are scoped by
    # the spec to P&L/BS/CF only (Section 14) -- so it only gets the DQ-03
    # orphan check, not dedup or year-format cleaning.
    documents = load_documents(os.path.join(RAW_DIR, "documents.xlsx"))
    documents, audit = clean_table(documents, "documents", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    # analysis.xlsx and prosandcons.xlsx also carry a company_id column, so
    # DQ-03 (FK integrity) still applies to them even though they're not
    # part of run_all_checks()'s CRITICAL-count summary below -- that
    # summary only covers the tables run_all_checks() was written to check
    # (pl/bs/cf/documents/companies). Cleaning these two here keeps every
    # table in the eventual SQLite load orphan-free, not just the ones the
    # validator currently reports on.
    analysis = load_analysis(os.path.join(RAW_DIR, "analysis.xlsx"))
    analysis, audit = clean_table(analysis, "analysis", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    prosandcons = load_prosandcons(os.path.join(RAW_DIR, "prosandcons.xlsx"))
    prosandcons, audit = clean_table(prosandcons, "prosandcons", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    # --- Day 5: the 5 supplementary files (data/supporting/) ---
    # Same valid_ids set from companies.xlsx -- these files are independent
    # datasets, but they all still FK to the same 92-company universe, so
    # there's exactly one "who's a valid company" answer for the whole load.
    sectors = load_sectors(os.path.join(SUPPORTING_DIR, "sectors.xlsx"))
    sectors, audit = clean_table(sectors, "sectors", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    stock_prices = load_stock_prices(os.path.join(SUPPORTING_DIR, "stock_prices.xlsx"))
    stock_prices, audit = clean_table(stock_prices, "stock_prices", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    market_cap = load_market_cap(os.path.join(SUPPORTING_DIR, "market_cap.xlsx"))
    market_cap, audit = clean_table(market_cap, "market_cap", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    # financial_ratios.xlsx is the one supplementary file that DOES need the
    # full has_year=True treatment: it has a financial-year-labelled 'year'
    # column (needs normalize_year(), applied in load_financial_ratios) and
    # its own real (company_id, year) duplicates in the raw file -- found
    # the same way the P&L/BS/CF duplicates were, by trying to load it
    # against the PRIMARY KEY declared in db/schema.sql and seeing it fail.
    financial_ratios = load_financial_ratios(os.path.join(SUPPORTING_DIR, "financial_ratios.xlsx"))
    financial_ratios, audit = clean_table(financial_ratios, "financial_ratios", valid_company_ids=valid_ids, has_year=True)
    audits.append(audit)

    peer_groups = load_peer_groups(os.path.join(SUPPORTING_DIR, "peer_groups.xlsx"))
    peer_groups, audit = clean_table(peer_groups, "peer_groups", valid_company_ids=valid_ids, has_year=False)
    audits.append(audit)

    runtime_s = round(time.time() - start, 2)
    audit_df = pd.DataFrame(audits)
    audit_df["timestamp"] = pd.Timestamp.now().isoformat()
    audit_df["runtime_s"] = runtime_s
    audit_df.to_csv(os.path.join(OUTPUT_DIR, "load_audit.csv"), index=False)

    results = run_all_checks(companies, pl, bs, cf, documents, check_urls=check_urls)
    results.to_csv(os.path.join(OUTPUT_DIR, "validation_failures.csv"), index=False)

    return {
        "companies": companies,
        "profitandloss": pl,
        "balancesheet": bs,
        "cashflow": cf,
        "documents": documents,
        "analysis": analysis,
        "prosandcons": prosandcons,
        "sectors": sectors,
        "stock_prices": stock_prices,
        "market_cap": market_cap,
        "financial_ratios": financial_ratios,
        "peer_groups": peer_groups,
        "validation_results": results,
    }


if __name__ == "__main__":
    tables = run_pipeline(check_urls=False)
    results = tables["validation_results"]

    print(f"Total violations found: {len(results)}")
    if len(results) > 0:
        print()
        print("By rule and severity:")
        print(results.groupby(["rule", "severity"]).size())
        print()
    critical_count = len(results[results["severity"] == "CRITICAL"]) if len(results) else 0
    print(f"CRITICAL violations: {critical_count}")
    if critical_count == 0:
        print("Day 3 exit criteria met: zero CRITICAL violations after cleaning.")
    else:
        print("CRITICAL violations remain -- Day 3 exit criteria NOT met.")
    print(f"\nload_audit.csv and validation_failures.csv written to {OUTPUT_DIR}")
