# Sprint 1 Retrospective -- Data Foundation (Days 1-7)

## Deliverables status

| # | Deliverable | Status |
|---|---|---|
| D-01 | nifty100.db (12 tables, FK constraints enforced) | Done |
| D-02 | load_audit.csv (all 12 files, zero CRITICAL failures) | Done |
| D-03 | validation_failures.csv (all violations logged with severity) | Done |
| D-04 | exploratory_queries.sql (12 queries, verified against real DB) | Done |

## What got built

- `src/etl/normaliser.py` -- `normalize_year()`, `normalize_ticker()`
- `src/etl/loader.py` -- 12 loader functions (7 core + 5 supplementary)
- `src/etl/validator.py` -- all 16 DQ rule checks
- `src/etl/cleaner.py` -- DQ-02/DQ-03/DQ-07 remediation (dedupe, orphan-drop, bad-year-drop)
- `src/etl/pipeline.py` -- the single load -> clean -> validate entry point
- `db/schema.sql` -- 12-table SQLite schema with FK constraints
- `db/loader.py` -- builds nifty100.db from the pipeline's cleaned output
- `db/exploratory_queries.sql` -- 12 verified queries
- `tests/etl/test_normalise.py` (35 tests), `tests/etl/test_cleaner.py` (11 tests)

## Exit criteria

Zero CRITICAL violations after cleaning: confirmed on the final clean
rebuild. 317 WARNING-level violations remain, untouched by design --
they are meant for analyst review, not automatic correction.

## Findings

1. 8 tickers absent from companies.xlsx despite appearing in child
   tables -- dropped from all child tables (DQ-03).
2. 134 duplicate (company_id, year) rows across P&L/BS/CF -- resolved by
   keeping the last occurrence (DQ-02).
3. 95 P&L rows with blank/unparseable year -- dropped (DQ-07, per the
   spec's documented remediation).
4. `companies.face_value` and two P&L columns contain nulls despite the
   spec marking them non-nullable -- schema relaxed to match the real
   data rather than reject otherwise-good rows.
5. `analysis.xlsx` is 1:N per company (4 rows per company, one per
   growth window), not 1:1 as the spec's entity-relationship map states.
6. `financial_ratios.xlsx` required the same DQ-02/DQ-03 treatment as
   the core annual tables. Not one of the 16 numbered rules, but the
   same underlying issue.
7. 83 of 91 companies carry an extra September balance-sheet snapshot
   with no matching P&L/CF year. Downstream modules must join on
   `(company_id, year)` rather than take the latest row per table.
8. DQ-04 (balance sheet balance check) never fires -- `total_assets`
   equals `total_liabilities` exactly in all 1,140 rows, indicating the
   source computed one field from the other rather than independently.
9. The real `sectors.xlsx` sector distribution does not match the
   spec's Section 6.1 example table (e.g. Financials=23 vs. stated 19).
   Both sum to 92 with full coverage -- a documentation/data mismatch,
   not a defect.

## Decisions

`cleaner.py` did not exist at the start of this sprint despite being
reported as already built. It was built from scratch in Sprint 1.

The database was initially built at `db/nifty100.db`, matching the
spec's literal deliverable naming (`db/schema.sql`, `db/loader.py`).
This conflicted with `config/.env.template` (`DB_PATH=data/nifty100.db`)
and `.gitignore`, both part of the original project scaffold. The
existing project convention took precedence: `db/loader.py`'s output
path was changed to `data/nifty100.db`, and the `Makefile`'s `load`
target was updated to call it instead of the bare Excel loader.

## Sprint 2 -- Ratio Engine (Days 8-14)

Scope: profitability, leverage, and efficiency ratios; CAGR engine; cash
flow KPIs; populate the `financial_ratios` table for all 92 companies.
