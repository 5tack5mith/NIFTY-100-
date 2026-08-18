"""Unit tests for src/etl/cleaner.py

These use small synthetic DataFrames rather than the real Excel files, so
the tests stay fast and don't depend on data/raw/ being present or
unchanged -- the real files are exercised separately via
`python src/etl/pipeline.py`, whose printed audit is what we check by hand
against the spec's Day 3 exit criteria (zero CRITICAL violations).

Run with: pytest tests/etl/test_cleaner.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "etl"))

from cleaner import (
    drop_orphan_rows,
    drop_unparseable_year_rows,
    deduplicate_annual_rows,
    clean_table,
)


# ---------------------------------------------------------------------------
# drop_orphan_rows() -- DQ-03
# ---------------------------------------------------------------------------

def test_drop_orphan_rows_removes_unknown_company_id():
    df = pd.DataFrame({"company_id": ["TCS", "WIPRO", "INFY"], "sales": [100, 200, 300]})
    clean, dropped = drop_orphan_rows(df, valid_company_ids={"TCS", "INFY"})
    assert sorted(clean["company_id"]) == ["INFY", "TCS"]
    assert dropped == 1


def test_drop_orphan_rows_keeps_all_when_no_orphans():
    df = pd.DataFrame({"company_id": ["TCS", "INFY"], "sales": [100, 300]})
    clean, dropped = drop_orphan_rows(df, valid_company_ids={"TCS", "INFY"})
    assert len(clean) == 2
    assert dropped == 0


def test_drop_orphan_rows_empty_valid_set_drops_everything():
    df = pd.DataFrame({"company_id": ["TCS", "INFY"], "sales": [100, 300]})
    clean, dropped = drop_orphan_rows(df, valid_company_ids=set())
    assert len(clean) == 0
    assert dropped == 2


# ---------------------------------------------------------------------------
# drop_unparseable_year_rows() -- DQ-07
# ---------------------------------------------------------------------------

def test_drop_unparseable_year_rows_removes_none_year():
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "TCS"],
        "year": ["2023-03", None, "2022-03"],
    })
    clean, dropped = drop_unparseable_year_rows(df)
    assert dropped == 1
    assert None not in clean["year"].values


def test_drop_unparseable_year_rows_keeps_all_when_years_valid():
    df = pd.DataFrame({"company_id": ["TCS", "INFY"], "year": ["2023-03", "2022-03"]})
    clean, dropped = drop_unparseable_year_rows(df)
    assert dropped == 0
    assert len(clean) == 2


# ---------------------------------------------------------------------------
# deduplicate_annual_rows() -- DQ-02
# ---------------------------------------------------------------------------

def test_deduplicate_annual_rows_keeps_last_occurrence():
    # Two rows for the same (company_id, year) with different sales figures --
    # simulates a restated/corrected entry appearing later in the sheet.
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS"],
        "year": ["2023-03", "2023-03"],
        "sales": [100, 999],
    })
    clean, dropped = deduplicate_annual_rows(df)
    assert dropped == 1
    assert len(clean) == 1
    assert clean.iloc[0]["sales"] == 999  # the later, "corrected" row survives


def test_deduplicate_annual_rows_no_duplicates_unchanged():
    df = pd.DataFrame({
        "company_id": ["TCS", "INFY"],
        "year": ["2023-03", "2023-03"],
        "sales": [100, 200],
    })
    clean, dropped = deduplicate_annual_rows(df)
    assert dropped == 0
    assert len(clean) == 2


def test_deduplicate_annual_rows_different_years_not_duplicates():
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS"],
        "year": ["2023-03", "2022-03"],
        "sales": [100, 90],
    })
    clean, dropped = deduplicate_annual_rows(df)
    assert dropped == 0
    assert len(clean) == 2


# ---------------------------------------------------------------------------
# clean_table() -- orchestration + audit dict shape
# ---------------------------------------------------------------------------

def test_clean_table_applies_all_three_rules_in_correct_order():
    # This case only passes if bad-year rows are dropped BEFORE dedup runs:
    # two TCS rows share a missing year, and would look like a "duplicate
    # pair" to a naive dedup step (pandas treats None == None in
    # duplicated()). If dedup ran first, one of the two None-year rows
    # would incorrectly survive as "the deduped one" instead of both being
    # rejected by DQ-07.
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "WIPRO", "INFY", "INFY"],
        "year": [None, None, "2023-03", "2023-03", "2023-03"],
        "sales": [1, 2, 3, 4, 5],
    })
    clean, audit = clean_table(df, "profitandloss", valid_company_ids={"TCS", "INFY"}, has_year=True)

    # WIPRO is an orphan (not in valid_company_ids) -> gone via DQ-03.
    # Both TCS rows have no year -> gone via DQ-07.
    # The two INFY rows are true duplicates -> one survives via DQ-02.
    assert sorted(clean["company_id"].unique()) == ["INFY"]
    assert len(clean) == 1
    assert audit["rows_in"] == 5
    assert audit["rows_out"] == 1
    assert audit["rejected_orphan_fk"] == 1
    assert audit["rejected_bad_year"] == 2
    assert audit["rejected_duplicate"] == 1
    assert audit["rejected_total"] == 4


def test_clean_table_skips_orphan_check_when_no_valid_ids_given():
    # Used for companies.xlsx itself, which has no company_id column to
    # FK-check against -- passing valid_company_ids=None must be a genuine
    # no-op for that rule, not an error.
    df = pd.DataFrame({"id": ["TCS", "INFY"], "sector": ["IT", "IT"]})
    clean, audit = clean_table(df, "companies", valid_company_ids=None, has_year=False)
    assert len(clean) == 2
    assert audit["rejected_orphan_fk"] == 0
    assert audit["rejected_total"] == 0


def test_clean_table_skips_year_rules_when_has_year_false():
    # Tables like documents.xlsx have a company_id but no (company_id, year)
    # composite key in the DQ-02/DQ-07 sense -- has_year=False must skip
    # both of those rules while still applying the DQ-03 orphan check.
    df = pd.DataFrame({"company_id": ["TCS", "WIPRO"], "Year": [2023, 2023]})
    clean, audit = clean_table(df, "documents", valid_company_ids={"TCS"}, has_year=False)
    assert len(clean) == 1
    assert audit["rejected_orphan_fk"] == 1
    assert audit["rejected_bad_year"] == 0
    assert audit["rejected_duplicate"] == 0
