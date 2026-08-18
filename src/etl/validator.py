"""Data Quality Validator — 16 rules (DQ-01 through DQ-16).

Every check_* function takes one or more DataFrames and returns a list of
violation dicts, all sharing the same shape so they can be combined into
one validation_failures.csv regardless of which rule found the issue:

    {"rule": "DQ-01", "company_id": ..., "year": ..., "field": ...,
     "issue": ..., "severity": "CRITICAL" | "WARNING" | "INFO"}

Run with: python validator.py  (after loader.py has produced DataFrames)
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))


def _violation(rule, severity, issue, company_id=None, year=None, field=None):
    """Build one violation record in the shared shape."""
    return {
        "rule": rule,
        "severity": severity,
        "company_id": company_id,
        "year": year,
        "field": field,
        "issue": issue,
    }


# ---------------------------------------------------------------------------
# DQ-01: Company primary key uniqueness
# ---------------------------------------------------------------------------

def check_dq01_company_pk_uniqueness(companies_df: pd.DataFrame) -> list:
    """len(companies) must equal companies.id.nunique() -- CRITICAL."""
    violations = []
    duplicated = companies_df[companies_df["id"].duplicated(keep=False)]
    for company_id in duplicated["id"].unique():
        violations.append(_violation(
            "DQ-01", "CRITICAL",
            "Duplicate company_id in companies table",
            company_id=company_id, field="id",
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-02: (company_id, year) primary key uniqueness in time-series tables
# ---------------------------------------------------------------------------

def check_dq02_annual_pk_uniqueness(df: pd.DataFrame, table_name: str) -> list:
    """No duplicate (company_id, year) pairs -- CRITICAL."""
    violations = []
    dupe_mask = df.duplicated(subset=["company_id", "year"], keep=False)
    for _, row in df[dupe_mask].iterrows():
        violations.append(_violation(
            "DQ-02", "CRITICAL",
            f"Duplicate (company_id, year) in {table_name}",
            company_id=row["company_id"], year=row["year"],
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-03: Foreign key integrity
# ---------------------------------------------------------------------------

def check_dq03_fk_integrity(child_df: pd.DataFrame, companies_df: pd.DataFrame,
                              table_name: str) -> list:
    """Every company_id in a child table must exist in companies.id -- CRITICAL."""
    violations = []
    valid_ids = set(companies_df["id"])
    orphans = child_df[~child_df["company_id"].isin(valid_ids)]
    for _, row in orphans.iterrows():
        violations.append(_violation(
            "DQ-03", "CRITICAL",
            f"company_id in {table_name} has no matching row in companies",
            company_id=row["company_id"],
            year=row.get("year"),
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-04: Balance sheet balance check
# ---------------------------------------------------------------------------

def check_dq04_balance_sheet_balance(balancesheet_df: pd.DataFrame) -> list:
    """|total_assets - total_liabilities| / total_assets < 0.01 -- WARNING."""
    violations = []
    for _, row in balancesheet_df.iterrows():
        assets = row["total_assets"]
        liabilities = row["total_liabilities"]
        if pd.isna(assets) or pd.isna(liabilities) or assets == 0:
            continue
        diff_pct = abs(assets - liabilities) / assets
        if diff_pct >= 0.01:
            violations.append(_violation(
                "DQ-04", "WARNING",
                f"Balance sheet imbalance: assets={assets}, liabilities={liabilities} "
                f"({diff_pct:.2%} diff)",
                company_id=row["company_id"], year=row["year"],
                field="total_assets/total_liabilities",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-05: OPM cross-check
# ---------------------------------------------------------------------------

def check_dq05_opm_cross_check(pl_df: pd.DataFrame) -> list:
    """|opm_percentage - (op_profit/sales*100)| < 1.0 -- WARNING."""
    violations = []
    for _, row in pl_df.iterrows():
        sales = row["sales"]
        op_profit = row["operating_profit"]
        stated_opm = row["opm_percentage"]
        if pd.isna(sales) or sales == 0 or pd.isna(stated_opm) or pd.isna(op_profit):
            continue
        computed_opm = (op_profit / sales) * 100
        if abs(stated_opm - computed_opm) >= 1.0:
            violations.append(_violation(
                "DQ-05", "WARNING",
                f"OPM mismatch: stated={stated_opm}, computed={computed_opm:.2f}",
                company_id=row["company_id"], year=row["year"],
                field="opm_percentage",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-06: Positive sales
# ---------------------------------------------------------------------------

def check_dq06_positive_sales(pl_df: pd.DataFrame) -> list:
    """sales > 0 for all non-bank companies -- WARNING."""
    violations = []
    non_positive = pl_df[pl_df["sales"] <= 0]
    for _, row in non_positive.iterrows():
        violations.append(_violation(
            "DQ-06", "WARNING",
            f"Non-positive sales: {row['sales']}",
            company_id=row["company_id"], year=row["year"], field="sales",
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-07: Year format check (post-normalisation)
# ---------------------------------------------------------------------------

def check_dq07_year_format(df: pd.DataFrame, table_name: str) -> list:
    """All year values must match YYYY-MM after normalize_year() -- CRITICAL."""
    import re
    violations = []
    pattern = re.compile(r"^\d{4}-\d{2}$")
    for _, row in df.iterrows():
        year_val = row["year"]
        if year_val is None or not pattern.match(str(year_val)):
            violations.append(_violation(
                "DQ-07", "CRITICAL",
                f"Unparseable/invalid year format in {table_name}: {year_val!r}",
                company_id=row.get("company_id"), field="year",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-08: Ticker format check (post-normalisation)
# ---------------------------------------------------------------------------

def check_dq08_ticker_format(df: pd.DataFrame, table_name: str,
                               id_column: str = "company_id") -> list:
    """Ticker length 2-12 chars after normalize_ticker() -- CRITICAL."""
    violations = []
    for _, row in df.iterrows():
        ticker = row[id_column]
        if ticker is None or not (2 <= len(str(ticker)) <= 12):
            violations.append(_violation(
                "DQ-08", "CRITICAL",
                f"Invalid ticker length in {table_name}: {ticker!r}",
                company_id=ticker, field=id_column,
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-09: Net cash flow check
# ---------------------------------------------------------------------------

def check_dq09_net_cash_check(cashflow_df: pd.DataFrame) -> list:
    """|net_cash_flow - (CFO+CFI+CFF)| <= 10 Cr tolerance -- WARNING."""
    violations = []
    for _, row in cashflow_df.iterrows():
        cfo = row["operating_activity"]
        cfi = row["investing_activity"]
        cff = row["financing_activity"]
        stated_net = row["net_cash_flow"]
        if any(pd.isna(v) for v in [cfo, cfi, cff, stated_net]):
            continue
        computed_net = cfo + cfi + cff
        if abs(stated_net - computed_net) > 10:
            violations.append(_violation(
                "DQ-09", "WARNING",
                f"Net cash flow mismatch: stated={stated_net}, "
                f"computed={computed_net}",
                company_id=row["company_id"], year=row["year"],
                field="net_cash_flow",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-10: Non-negative fixed assets
# ---------------------------------------------------------------------------

def check_dq10_non_negative_fixed_assets(balancesheet_df: pd.DataFrame) -> list:
    """fixed_assets >= 0 -- WARNING."""
    violations = []
    negative = balancesheet_df[balancesheet_df["fixed_assets"] < 0]
    for _, row in negative.iterrows():
        violations.append(_violation(
            "DQ-10", "WARNING",
            f"Negative fixed_assets: {row['fixed_assets']}",
            company_id=row["company_id"], year=row["year"], field="fixed_assets",
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-11: Tax rate range
# ---------------------------------------------------------------------------

def check_dq11_tax_rate_range(pl_df: pd.DataFrame) -> list:
    """0 <= tax_percentage <= 60 -- WARNING."""
    violations = []
    out_of_range = pl_df[
        (pl_df["tax_percentage"] < 0) | (pl_df["tax_percentage"] > 60)
    ]
    for _, row in out_of_range.iterrows():
        violations.append(_violation(
            "DQ-11", "WARNING",
            f"Tax rate out of range: {row['tax_percentage']}",
            company_id=row["company_id"], year=row["year"],
            field="tax_percentage",
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-12: Dividend payout cap
# ---------------------------------------------------------------------------

def check_dq12_dividend_payout_cap(pl_df: pd.DataFrame) -> list:
    """dividend_payout <= 200% -- WARNING."""
    violations = []
    over_cap = pl_df[pl_df["dividend_payout"] > 200]
    for _, row in over_cap.iterrows():
        violations.append(_violation(
            "DQ-12", "WARNING",
            f"Dividend payout exceeds 200%: {row['dividend_payout']}",
            company_id=row["company_id"], year=row["year"],
            field="dividend_payout",
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-13: URL validity (documents)
# ---------------------------------------------------------------------------

def check_dq13_url_validity(documents_df: pd.DataFrame, sample_size: int = None) -> list:
    """requests.head(Annual_Report).status_code == 200 -- WARNING.

    Network check -- optionally pass sample_size to only check a subset,
    since checking all 1,585 URLs on every run is slow.
    """
    import requests
    violations = []
    rows = documents_df if sample_size is None else documents_df.head(sample_size)
    for _, row in rows.iterrows():
        url = row["Annual_Report"]
        if pd.isna(url):
            continue
        try:
            resp = requests.head(url, timeout=5)
            if resp.status_code != 200:
                violations.append(_violation(
                    "DQ-13", "WARNING",
                    f"Annual report URL returned {resp.status_code}",
                    company_id=row["company_id"], year=row.get("Year"),
                    field="Annual_Report",
                ))
        except requests.RequestException as exc:
            violations.append(_violation(
                "DQ-13", "WARNING",
                f"Annual report URL unreachable: {exc}",
                company_id=row["company_id"], year=row.get("Year"),
                field="Annual_Report",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-14: EPS sign consistency
# ---------------------------------------------------------------------------

def check_dq14_eps_sign_consistency(pl_df: pd.DataFrame) -> list:
    """eps > 0 if net_profit > 0 -- WARNING."""
    violations = []
    for _, row in pl_df.iterrows():
        net_profit = row["net_profit"]
        eps = row["eps"]
        if pd.isna(net_profit) or pd.isna(eps):
            continue
        if net_profit > 0 and eps <= 0:
            violations.append(_violation(
                "DQ-14", "WARNING",
                f"EPS sign mismatch: net_profit={net_profit} but eps={eps}",
                company_id=row["company_id"], year=row["year"], field="eps",
            ))
    return violations


# ---------------------------------------------------------------------------
# DQ-15: BSE/ASE balance (informational, stricter re-check of DQ-04)
# ---------------------------------------------------------------------------

def check_dq15_strict_balance_info(balancesheet_df: pd.DataFrame) -> list:
    """Strict equality check (informational only, doesn't block load) -- INFO."""
    violations = []
    mismatched = balancesheet_df[
        balancesheet_df["total_assets"] != balancesheet_df["total_liabilities"]
    ]
    for _, row in mismatched.iterrows():
        violations.append(_violation(
            "DQ-15", "INFO",
            "Strict assets != liabilities (informational only)",
            company_id=row["company_id"], year=row["year"],
        ))
    return violations


# ---------------------------------------------------------------------------
# DQ-16: Coverage check
# ---------------------------------------------------------------------------

def check_dq16_coverage(pl_df: pd.DataFrame) -> list:
    """Each company needs >= 5 years of P&L history -- WARNING."""
    violations = []
    year_counts = pl_df.groupby("company_id")["year"].nunique()
    thin_coverage = year_counts[year_counts < 5]
    for company_id, count in thin_coverage.items():
        violations.append(_violation(
            "DQ-16", "WARNING",
            f"Only {count} years of P&L history (< 5 required for reliable CAGR)",
            company_id=company_id,
        ))
    return violations


# ---------------------------------------------------------------------------
# Orchestrator: run every rule and combine results
# ---------------------------------------------------------------------------

def run_all_checks(companies_df, pl_df, bs_df, cf_df, documents_df,
                    check_urls: bool = False) -> pd.DataFrame:
    """Run all 16 DQ rules and return one combined violations DataFrame."""
    all_violations = []

    all_violations += check_dq01_company_pk_uniqueness(companies_df)

    all_violations += check_dq02_annual_pk_uniqueness(pl_df, "profitandloss")
    all_violations += check_dq02_annual_pk_uniqueness(bs_df, "balancesheet")
    all_violations += check_dq02_annual_pk_uniqueness(cf_df, "cashflow")

    all_violations += check_dq03_fk_integrity(pl_df, companies_df, "profitandloss")
    all_violations += check_dq03_fk_integrity(bs_df, companies_df, "balancesheet")
    all_violations += check_dq03_fk_integrity(cf_df, companies_df, "cashflow")

    all_violations += check_dq04_balance_sheet_balance(bs_df)
    all_violations += check_dq05_opm_cross_check(pl_df)
    all_violations += check_dq06_positive_sales(pl_df)

    all_violations += check_dq07_year_format(pl_df, "profitandloss")
    all_violations += check_dq07_year_format(bs_df, "balancesheet")
    all_violations += check_dq07_year_format(cf_df, "cashflow")

    all_violations += check_dq08_ticker_format(companies_df, "companies", id_column="id")
    all_violations += check_dq08_ticker_format(pl_df, "profitandloss")

    all_violations += check_dq09_net_cash_check(cf_df)
    all_violations += check_dq10_non_negative_fixed_assets(bs_df)
    all_violations += check_dq11_tax_rate_range(pl_df)
    all_violations += check_dq12_dividend_payout_cap(pl_df)

    if check_urls:
        all_violations += check_dq13_url_validity(documents_df, sample_size=20)

    all_violations += check_dq14_eps_sign_consistency(pl_df)
    all_violations += check_dq15_strict_balance_info(bs_df)
    all_violations += check_dq16_coverage(pl_df)

    return pd.DataFrame(all_violations)


if __name__ == "__main__":
    from loader import (
        load_companies, load_profitandloss, load_balancesheet,
        load_cashflow, load_documents,
    )

    RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    companies = load_companies(os.path.join(RAW_DIR, "companies.xlsx"))
    pl = load_profitandloss(os.path.join(RAW_DIR, "profitandloss.xlsx"))
    bs = load_balancesheet(os.path.join(RAW_DIR, "balancesheet.xlsx"))
    cf = load_cashflow(os.path.join(RAW_DIR, "cashflow.xlsx"))
    documents = load_documents(os.path.join(RAW_DIR, "documents.xlsx"))

    results = run_all_checks(companies, pl, bs, cf, documents, check_urls=False)

    output_path = os.path.join(OUTPUT_DIR, "validation_failures.csv")
    results.to_csv(output_path, index=False)

    print(f"Total violations found: {len(results)}")
    if len(results) > 0:
        print()
        print("By rule and severity:")
        print(results.groupby(["rule", "severity"]).size())
        print()
        critical_count = len(results[results["severity"] == "CRITICAL"])
        print(f"CRITICAL violations: {critical_count}")
        if critical_count > 0:
            print("⚠ CRITICAL violations must be resolved before proceeding to Day 4.")
    print(f"\nFull results written to {output_path}")