"""Cleaning functions that turn raw-loaded DataFrames into DQ-rule-compliant ones.

The spec (Section 14, DQ-01 through DQ-16) assigns each CRITICAL rule a
specific remediation action, not just a warning:
    DQ-02 (duplicate company_id+year)  -> keep the LAST occurrence
    DQ-03 (company_id not in companies) -> reject (drop) the row
    DQ-07 (year unparseable after normalize_year()) -> reject (drop) the row

This module implements those three remediations. It deliberately does NOT
touch the WARNING-level rules (DQ-04 through DQ-16 minus DQ-08) -- those are
meant to be flagged for analyst review, not silently altered, so they stay
untouched here and continue to show up in validation_failures.csv after
cleaning. Silently "fixing" a WARNING would hide a data quality signal that
someone is supposed to look at.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))


def drop_orphan_rows(df: pd.DataFrame, valid_company_ids: set, table_name: str = "") -> tuple:
    """DQ-03 remediation: drop rows whose company_id has no match in companies.xlsx.

    Returns (clean_df, dropped_count) rather than just the DataFrame, because
    every caller needs the count for the load_audit.csv rows_in/rows_out/
    rejected columns the spec requires (Sprint 1 Feature 1.7) -- returning a
    plain DataFrame would force every caller to recompute len(df) diffs.
    """
    mask = df["company_id"].isin(valid_company_ids)
    dropped_count = (~mask).sum()
    if dropped_count:
        dropped_ids = sorted(df.loc[~mask, "company_id"].dropna().unique())
        print(f"  [DQ-03] {table_name}: dropping {dropped_count} orphan rows "
              f"(company_id not in companies.xlsx): {dropped_ids}")
    return df[mask].copy(), dropped_count


def drop_unparseable_year_rows(df: pd.DataFrame, table_name: str = "") -> tuple:
    """DQ-07 remediation: drop rows where normalize_year() returned None.

    Must run before deduplicate_annual_rows() -- see module note in the
    pipeline script. pandas' duplicated() treats NaN/None as equal to other
    NaN/None, so a company with several rows that all have a missing year
    would otherwise look like "one real row plus some duplicates" and only
    one would survive, silently keeping a row that should have been
    rejected outright.
    """
    mask = df["year"].notna()
    dropped_count = (~mask).sum()
    if dropped_count:
        print(f"  [DQ-07] {table_name}: dropping {dropped_count} rows with "
              f"unparseable/missing year")
    return df[mask].copy(), dropped_count


def deduplicate_annual_rows(df: pd.DataFrame, table_name: str = "") -> tuple:
    """DQ-02 remediation: for duplicate (company_id, year) pairs, keep the last row.

    "Keep last" is the spec's own remediation rule (DQ-02), not an arbitrary
    choice -- it assumes the source data lists corrections/restatements after
    the original entry, so the later row in the sheet is the most current
    figure. This is why year-cleaning must run first: duplicated() needs
    real year values to compare, not two different companies' None-year rows
    that would otherwise appear identical.
    """
    dupe_mask = df.duplicated(subset=["company_id", "year"], keep=False)
    before = len(df)
    deduped = df.drop_duplicates(subset=["company_id", "year"], keep="last")
    dropped_count = before - len(deduped)
    if dropped_count:
        dupe_keys = sorted(
            df.loc[dupe_mask, ["company_id", "year"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        )
        print(f"  [DQ-02] {table_name}: dropping {dropped_count} duplicate "
              f"(company_id, year) rows, keeping last occurrence: {dupe_keys}")
    return deduped.copy(), dropped_count


def clean_table(df: pd.DataFrame, table_name: str, valid_company_ids: set = None,
                 has_year: bool = True) -> tuple:
    """Run the full CRITICAL-rule remediation sequence for one table.

    valid_company_ids=None skips the DQ-03 orphan check -- used for
    companies.xlsx itself, which has no company_id column to check against
    itself. has_year=False skips DQ-07/DQ-02 -- used for tables like
    prosandcons.xlsx that have no (company_id, year) composite key.

    Returns (clean_df, audit) where audit is a dict matching the
    load_audit.csv columns the spec requires: rows_in, rows_out, and a
    breakdown of what was rejected by which rule.
    """
    rows_in = len(df)
    clean = df

    rejected_orphan = 0
    if valid_company_ids is not None:
        clean, rejected_orphan = drop_orphan_rows(clean, valid_company_ids, table_name)

    rejected_bad_year = 0
    rejected_duplicate = 0
    if has_year:
        clean, rejected_bad_year = drop_unparseable_year_rows(clean, table_name)
        clean, rejected_duplicate = deduplicate_annual_rows(clean, table_name)

    audit = {
        "table": table_name,
        "rows_in": rows_in,
        "rows_out": len(clean),
        "rejected_orphan_fk": rejected_orphan,
        "rejected_bad_year": rejected_bad_year,
        "rejected_duplicate": rejected_duplicate,
        "rejected_total": rows_in - len(clean),
    }
    return clean, audit


if __name__ == "__main__":
    # Manual smoke test against the real data: python cleaner.py
    from loader import load_companies, load_profitandloss, load_balancesheet, load_cashflow

    RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
    companies = load_companies(os.path.join(RAW_DIR, "companies.xlsx"))
    valid_ids = set(companies["id"])

    for name, loader_fn in [
        ("profitandloss", load_profitandloss),
        ("balancesheet", load_balancesheet),
        ("cashflow", load_cashflow),
    ]:
        df = loader_fn(os.path.join(RAW_DIR, f"{name}.xlsx"))
        clean_df, audit = clean_table(df, name, valid_company_ids=valid_ids, has_year=True)
        print(audit)
