# Sprint 1 Retrospective -- Data Foundation (Days 1-7)

## Deliverables status

| # | Deliverable | Status |
|---|---|---|
| D-01 | nifty100.db (10/12 tables, FK constraints enforced) | Done |
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

## Exit criteria check

Zero CRITICAL violations after cleaning: **confirmed**, re-verified on the
final clean rebuild. 317 WARNING-level violations remain, untouched by
design -- they're meant for analyst review, not automatic correction.

## Real findings this sprint (full detail in docs/progress_log/sprint1_summary.md)

1. 8 tickers genuinely absent from companies.xlsx -- dropped from all
   child tables (DQ-03).
2. 134 duplicate (company_id, year) rows across P&L/BS/CF -- kept last
   occurrence (DQ-02).
3. 95 P&L rows with blank/unparseable year -- dropped (DQ-07, per the
   spec's own documented remediation).
4. `companies.face_value` and two P&L columns have real nulls despite the
   spec marking them non-nullable -- schema relaxed to match reality
   rather than reject good rows over it.
5. `analysis.xlsx` is 1:N per company (4 rows/company, one per growth
   window), not 1:1 as the spec's ER map claims.
6. `financial_ratios.xlsx` needed the same DQ-02/DQ-03 treatment as the
   core annual tables -- not one of the 16 numbered rules, but the same
   underlying problem.
7. 83/91 companies carry an extra September balance-sheet snapshot with no
   matching P&L/CF year -- flagged for Sprint 2 as a reason to always join
   on `(company_id, year)` rather than picking "latest row" per table.
8. DQ-04 (balance sheet balance check) never fires -- `total_assets`
   exactly equals `total_liabilities` in all 1,140 rows, suggesting the
   source computed one from the other rather than independently.
9. Real `sectors.xlsx` sector distribution doesn't match the spec's
   Section 6.1 example table (e.g. Financials=23 vs. stated 19); both sum
   to 92 with full coverage, so not a defect, just a doc/data mismatch.

## Process note

`cleaner.py` was originally reported (by an earlier session summary) as
already built. It wasn't -- verified against the actual filesystem before
writing anything, per this project's stated practice of trusting the
codebase over prior summaries. Worth keeping that habit for every future
sprint handoff.

Similarly, the database was first built at `db/nifty100.db`, matching the
spec's literal deliverable naming ("db/schema.sql, db/loader.py"). That
conflicted with `config/.env.template` (`DB_PATH=data/nifty100.db`) and
`.gitignore`, both written during the original project scaffold before
this sprint started -- an existing project convention that outranks the
spec's example path. Fixed by pointing `db/loader.py`'s output at
`data/nifty100.db` and updating the `Makefile`'s `load` target to call it
instead of the bare Excel loader. Caught by reading the existing scaffold
files rather than assuming the spec's naming was the only source of truth.

## Next: Sprint 2 -- Ratio Engine (Days 8-14)

Not started. Waiting for go-ahead before beginning, per project instructions.
