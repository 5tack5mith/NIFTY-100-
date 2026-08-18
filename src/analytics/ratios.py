"""Sprint 2 Ratio Engine -- profitability, returns, leverage & efficiency ratios.

Every formula here follows the project spec's Section 13 KPI reference,
edge case column, exactly. The recurring pattern across almost every
function is "return None instead of raising or returning a nonsense
number" -- e.g. dividing by zero sales, or computing ROE against negative
equity. None is the right sentinel because these functions feed a SQLite
NUMERIC column and a screener that will later filter/sort by these values;
a crashed pipeline or a silently wrong -inf/nan value would both be worse
than a clean gap the analyst can see and understand.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etl"))


def build_annual_frame(pl: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame) -> pd.DataFrame:
    """Join cleaned P&L, balance sheet and cash flow tables on (company_id, year).

    This join is the single most important line in the whole Ratio Engine,
    and it's written as an explicit merge on the composite key for a
    concrete reason found during Sprint 1's manual QA (see
    reports/day6_dq_review_notes.md, finding #2): 83 of 91 companies carry
    an extra September balance-sheet snapshot with no matching P&L/CF year.
    If this code instead pulled "the latest balancesheet row" and "the
    latest profitandloss row" independently per company and zipped them
    together, it would silently pair a September 2024 balance sheet with a
    March 2024 P&L for most companies -- producing ratios that are
    numerically valid but describe two different points in time. Joining
    explicitly on (company_id, year) means a mismatched BS-only year (like
    2024-09) just doesn't have a P&L counterpart and drops out of every
    P&L-anchored ratio for that row, instead of silently corrupting one.

    Left-joined onto P&L (not an inner join) because P&L is the table that
    defines "which company-years exist" for this analysis -- a company-year
    with P&L but no matching BS/CF row should still show up with those
    ratios as None, not disappear from the dataset entirely.

    The source 'id' column from each table is dropped before merging --
    it's a row number, not analytically meaningful (spec Section 5.2), and
    keeping it around would just create id_x/id_y noise columns.
    """
    pl = pl.drop(columns=["id"], errors="ignore")
    bs = bs.drop(columns=["id"], errors="ignore")
    cf = cf.drop(columns=["id"], errors="ignore")

    frame = pl.merge(bs, on=["company_id", "year"], how="left", suffixes=("", "_bs"))
    frame = frame.merge(cf, on=["company_id", "year"], how="left", suffixes=("", "_cf"))
    return frame


# ---------------------------------------------------------------------------
# Profitability ratios (D08)
# ---------------------------------------------------------------------------

def net_profit_margin(net_profit, sales):
    """NPM = net_profit / sales x 100. None if sales = 0. Negative allowed (spec 13)."""
    if pd.isna(sales) or sales == 0 or pd.isna(net_profit):
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(operating_profit, sales):
    """OPM = operating_profit / sales x 100.

    Spec has two descriptions of this metric that don't quite agree:
    Section 13 (KPI formula reference) frames the computed value as the
    metric to use, with the source opm_percentage field as a cross-check
    (Section 5.2). Section 6.4 (financial_ratios.xlsx schema) instead says
    to store the SOURCE field and use the computed value only to validate
    it. Judgment call: store the computed value here, matching Section 13
    (the more detailed, formal formula reference), and separately flag any
    row where it disagrees with the source by >1% -- see
    opm_cross_check_flag() below, which is exactly what D08's "cross-
    validate OPM vs source" actually asks for regardless of which value
    ends up stored.
    """
    if pd.isna(sales) or sales == 0 or pd.isna(operating_profit):
        return None
    return (operating_profit / sales) * 100


def opm_cross_check_flag(computed_opm, stated_opm_percentage) -> bool:
    """True if computed OPM disagrees with the source opm_percentage by >=1%.

    Same threshold as the validator's DQ-05 check -- this isn't a new
    policy, just reusing the one the spec already defined for the exact
    same comparison.
    """
    if pd.isna(computed_opm) or pd.isna(stated_opm_percentage):
        return False
    return abs(computed_opm - stated_opm_percentage) >= 1.0


# ---------------------------------------------------------------------------
# Returns ratios (D08)
# ---------------------------------------------------------------------------

def return_on_equity(net_profit, equity_capital, reserves):
    """ROE = net_profit / (equity + reserves) x 100. None if equity+reserves <= 0."""
    if pd.isna(net_profit) or pd.isna(equity_capital):
        return None
    reserves = reserves if pd.notna(reserves) else 0
    equity = equity_capital + reserves
    if equity <= 0:
        return None
    return (net_profit / equity) * 100


def return_on_capital(operating_profit, depreciation, equity_capital, reserves,
                       borrowings, is_financial_sector: bool):
    """ROCE = EBIT / (equity + reserves + borrowings) x 100.

    EBIT = operating_profit - depreciation (spec 5.2: "EBIT =
    operating_profit - depreciation"). None if capital employed <= 0.

    Banks/NBFCs (is_financial_sector=True) get this formula applied too --
    it still returns a number -- but the CALLER is responsible for treating
    that number as not directly comparable to non-financial companies (spec:
    "Bank carve-out: use sector-relative benchmark", D13). This function
    doesn't suppress the value; src/analytics/populate_financial_ratios.py
    is what routes financial-sector ROCE into sector_roce_notes.csv instead
    of a flat cross-sector comparison.
    """
    if pd.isna(operating_profit) or pd.isna(equity_capital):
        return None
    depreciation = depreciation if pd.notna(depreciation) else 0
    reserves = reserves if pd.notna(reserves) else 0
    borrowings = borrowings if pd.notna(borrowings) else 0
    ebit = operating_profit - depreciation
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    return (ebit / capital_employed) * 100


# ---------------------------------------------------------------------------
# Leverage & efficiency ratios (D09)
# ---------------------------------------------------------------------------

DEBT_FREE_SENTINEL = 999.0  # spec 13: "None if interest=0 -> display 'Debt Free'";
# Module 2 summary (spec p.19) instead says "999 displayed as 'Debt Free'".
# These two spec passages disagree on whether the stored value should be
# None or a 999 sentinel for a debt-free company. Judgment call: 999,
# because interest_coverage is declared NUMERIC in db/schema.sql -- storing
# None would make "debt-free" indistinguishable from "data missing" once
# it's in SQLite, which is a real information loss a screener or dashboard
# would have no way to recover from. 999 is an obviously-out-of-range
# sentinel (real ICR values cluster single/low-double digits) that the
# display layer can special-case into the text "Debt Free".

def interest_coverage(operating_profit, other_income, interest):
    """ICR = (op_profit + other_income) / interest. Debt-free substitution if interest = 0."""
    if pd.isna(operating_profit):
        return None
    other_income = other_income if pd.notna(other_income) else 0
    if pd.isna(interest) or interest == 0:
        return DEBT_FREE_SENTINEL
    return (operating_profit + other_income) / interest


def debt_to_equity(borrowings, equity_capital, reserves):
    """D/E = borrowings / (equity + reserves). 0 = debt-free.

    The spec's bank/NBFC carve-out ("flag >5 for non-financials") is a
    SCREENING rule, not a computation rule -- the ratio itself is computed
    identically for every sector here; it's populate_financial_ratios.py's
    job to know which companies are financials and suppress the >5 flag
    for them, not this function's.
    """
    if pd.isna(borrowings) or pd.isna(equity_capital):
        return None
    reserves = reserves if pd.notna(reserves) else 0
    equity = equity_capital + reserves
    if equity <= 0:
        return None
    return borrowings / equity


def asset_turnover(sales, total_assets):
    """Asset Turnover = sales / total_assets. None if total_assets = 0."""
    if pd.isna(sales) or pd.isna(total_assets) or total_assets == 0:
        return None
    return sales / total_assets


# ---------------------------------------------------------------------------
# Display-only / cross-check metrics needed for the financial_ratios table
# ---------------------------------------------------------------------------

def book_value_per_share(equity_capital, reserves, face_value):
    """Book value/share = (equity + reserves) / (equity_capital / face_value).

    (equity_capital / face_value) is the implied share count -- spec 13
    formula. None if face_value is missing or zero (companies.face_value
    has one real null in this dataset, see Sprint 1 findings) or if
    equity_capital is zero (would make share count zero, undefined ratio).
    """
    if pd.isna(equity_capital) or pd.isna(face_value) or face_value == 0 or equity_capital == 0:
        return None
    reserves = reserves if pd.notna(reserves) else 0
    share_count = equity_capital / face_value
    return (equity_capital + reserves) / share_count
