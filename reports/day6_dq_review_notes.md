# Day 6 -- Manual Data Quality Review

Spec task: "Data quality review: manually check 5 random companies across all
time-series tables. Fix any loader bugs. Re-run load."

## Sample

Random seed 42 against the 92 loaded companies: **SUNPHARMA, BAJFINANCE,
ADANIGREEN, HAL, EICHERMOT**.

For each, checked: year coverage continuity across profitandloss /
balancesheet / cashflow, whether the latest year's figures look plausible
(no obviously corrupted values), and whether balance sheet balances.

## Findings

### 1. No loader bugs found

Across all 5 sampled companies, `normalize_year()` and `normalize_ticker()`
produced correct, consistent output. Year sequences are monotonic and
column values are in plausible ranges for each company's known scale. No
code changes made; no re-run needed.

### 2. Systemic: a September balance-sheet row with no matching P&L/CF year

**83 of 91 companies** (all 5 in the sample included) carry a `2024-09`
balance sheet row that has no corresponding `2024-09` row in profitandloss
or cashflow -- those tables stop at `2024-03`. This is consistent with the
underlying source (Screener.in) showing whatever the most recent published
balance sheet is, even mid-fiscal-year, while P&L/CF stay strictly annual.

This is not a bug -- the loader is faithfully representing the source. But
it's a real trap for Sprint 2 (Ratio Engine) and beyond: any code that
independently picks "the latest year" per table for a company, rather than
joining `profitandloss` and `balancesheet` on `(company_id, year)` per the
spec's own standard join pattern (Section 7.3), would pair a September
balance sheet with a March P&L and silently compute nonsense ratios.
**Recommendation for Sprint 2: always join on `(company_id, year)`, never
take "latest row per table" independently per table.**

### 3. DQ-04 (balance sheet balance check) is structurally tautological in this dataset

Checked directly: `total_assets == total_liabilities` in **all 1,140**
balancesheet rows, exactly, with zero exceptions. DQ-04's WARNING never
fires in `validation_failures.csv` as a result. This almost certainly means
the source computed `total_liabilities` *as* `total_assets` at scrape time,
rather than as an independently-summed figure -- so DQ-04, while
implemented correctly per the spec's formula, provides no real
discriminating signal on this dataset. Worth knowing before treating "zero
DQ-04 violations" as evidence the balance sheets are unusually clean.

### 4. Data gap: EICHERMOT has a mismatched early fiscal-year-end and a missing year

EICHERMOT's P&L years run `2012-12, 2013-12, 2014-12, 2016-03, 2017-03, ...`
-- three early years labelled with a December fiscal-year-end, then a jump
straight to March with **no 2015 entry at all**. The normaliser converts
each label correctly (`Dec-12` -> `2012-12` is textbook-correct behaviour);
this is a genuine gap/inconsistency in the source data, not a normalisation
error. Flagging for analyst awareness -- not fixed here, since there's no
documented remediation rule for "missing fiscal year with no malformed
label to reject" (this is different from DQ-07, where the year label
itself was blank/unparseable).

## Outcome

No loader bugs -> no code changes -> no re-run required for this step.
Findings #2-4 are logged here for Sprint 2 planning, since none of them are
CRITICAL-severity DQ rule violations.
