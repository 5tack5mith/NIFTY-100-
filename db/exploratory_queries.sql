-- Sprint 1, Day 7 deliverable: 10+ exploratory queries covering row counts,
-- nulls, and year coverage per company (spec deliverable D-04).
-- Run against db/nifty100.db. Written and verified to execute against the
-- real loaded database, not just theoretically correct SQL.

-- 1. Row count per table -- sanity check against load_audit.csv rows_out.
SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL SELECT 'peer_groups', COUNT(*) FROM peer_groups;

-- 2. Null counts in profitandloss's nullable numeric fields -- flags how
-- much real analytics work will need to handle missing values.
SELECT
    SUM(CASE WHEN other_income IS NULL THEN 1 ELSE 0 END)      AS null_other_income,
    SUM(CASE WHEN interest IS NULL THEN 1 ELSE 0 END)          AS null_interest,
    SUM(CASE WHEN depreciation IS NULL THEN 1 ELSE 0 END)      AS null_depreciation,
    SUM(CASE WHEN net_profit IS NULL THEN 1 ELSE 0 END)        AS null_net_profit,
    SUM(CASE WHEN eps IS NULL THEN 1 ELSE 0 END)               AS null_eps,
    SUM(CASE WHEN dividend_payout IS NULL THEN 1 ELSE 0 END)   AS null_dividend_payout,
    COUNT(*)                                                    AS total_rows
FROM profitandloss;

-- 3. Null counts in balancesheet's nullable numeric fields.
SELECT
    SUM(CASE WHEN reserves IS NULL THEN 1 ELSE 0 END)          AS null_reserves,
    SUM(CASE WHEN borrowings IS NULL THEN 1 ELSE 0 END)        AS null_borrowings,
    SUM(CASE WHEN fixed_assets IS NULL THEN 1 ELSE 0 END)      AS null_fixed_assets,
    SUM(CASE WHEN investments IS NULL THEN 1 ELSE 0 END)       AS null_investments,
    COUNT(*)                                                    AS total_rows
FROM balancesheet;

-- 4. Year coverage per company in profitandloss: min year, max year, and
-- count of distinct years -- this is the same "coverage" concept DQ-16
-- checks (< 5 years flagged), surfaced here as raw numbers per company.
SELECT company_id,
       MIN(year) AS earliest_year,
       MAX(year) AS latest_year,
       COUNT(DISTINCT year) AS years_covered
FROM profitandloss
GROUP BY company_id
ORDER BY years_covered ASC;

-- 5. Companies with thin P&L history (< 5 years) -- same threshold as
-- DQ-16, run directly in SQL rather than through the pandas validator, to
-- cross-check that the two approaches agree.
SELECT company_id, COUNT(DISTINCT year) AS years_covered
FROM profitandloss
GROUP BY company_id
HAVING COUNT(DISTINCT year) < 5
ORDER BY years_covered ASC;

-- 6. Companies present in `companies` but with zero sectors.xlsx coverage --
-- spec claims 100% (92/92) sector coverage; verifying that claim directly
-- rather than trusting the dataset catalogue's stated completeness.
SELECT c.id, c.company_name
FROM companies c
LEFT JOIN sectors s ON c.id = s.company_id
WHERE s.company_id IS NULL;

-- 7. Company count per broad_sector -- cross-check against the spec's
-- Section 6.1 sector breakdown table (Financials=19, Energy=15, etc.).
SELECT broad_sector, COUNT(*) AS company_count
FROM sectors
GROUP BY broad_sector
ORDER BY company_count DESC;

-- 8. Balance sheet rows outside the normal March fiscal-year-end pattern --
-- surfaces the "extra September snapshot" finding from the Day 6 manual
-- review (reports/day6_dq_review_notes.md) as a query anyone can re-run.
SELECT company_id, year
FROM balancesheet
WHERE year NOT LIKE '%-03'
ORDER BY company_id;

-- 9. Companies with a balance sheet year that has no matching profitandloss
-- year for the same company -- the concrete version of finding #2 from the
-- Day 6 review notes: these are the (company_id, year) pairs that a naive
-- "latest row per table" approach would mismatch.
SELECT b.company_id, b.year AS bs_only_year
FROM balancesheet b
LEFT JOIN profitandloss p ON b.company_id = p.company_id AND b.year = p.year
WHERE p.company_id IS NULL
ORDER BY b.company_id, b.year;

-- 10. Peer group membership count per company -- spec notes peer_groups
-- coverage is partial (46/92); this shows exactly which companies have 0,
-- 1, or multiple group memberships.
SELECT c.id,
       COUNT(pg.peer_group_name) AS peer_group_count
FROM companies c
LEFT JOIN peer_groups pg ON c.id = pg.company_id
GROUP BY c.id
ORDER BY peer_group_count DESC;

-- 11. financial_ratios year coverage per company, for comparison against
-- profitandloss coverage (query 4) -- the two shouldn't be wildly
-- different, since financial_ratios is supposed to be computed FROM the
-- core tables.
SELECT company_id, COUNT(DISTINCT year) AS years_covered
FROM financial_ratios
GROUP BY company_id
ORDER BY years_covered ASC
LIMIT 15;

-- 12. documents.xlsx coverage: companies with zero annual report links --
-- spec notes ~82% coverage (75/92); this identifies the ones missing.
SELECT c.id, c.company_name
FROM companies c
LEFT JOIN documents d ON c.id = d.company_id
WHERE d.company_id IS NULL;
