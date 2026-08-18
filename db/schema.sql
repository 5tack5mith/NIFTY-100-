-- Nifty 100 Financial Intelligence Platform -- SQLite schema
-- Sprint 1, Day 4 deliverable (project spec Section 9, Feature 1.6)
--
-- The spec's table lists are slightly inconsistent: the Day 4 task text and
-- the deliverables checklist both say "10 tables", but the entity-relationship
-- map (Section 7.1) and the Module 1 output description both explicitly name
-- 12: companies, profitandloss, balancesheet, cashflow, analysis, documents,
-- prosandcons, sectors, market_cap, stock_prices, financial_ratios,
-- peer_groups. We're building all 12 named tables now -- creating a table is
-- free, and every one of them has a defined schema and a real source file
-- (7 core now, 5 supplementary on Day 5), so there's no reason to leave any
-- of them out just because a summary count elsewhere in the doc says "10".
--
-- Every child table declares company_id as a FOREIGN KEY to companies.id
-- rather than relying on the ETL layer alone to catch orphans -- the ETL
-- cleaner (src/etl/cleaner.py) already rejects DQ-03 violations before rows
-- reach this database, but the DB-level constraint is what actually
-- guarantees it stays true even if someone loads data through a different
-- path later (e.g. a manual INSERT, or a future script that skips cleaner.py).
--
-- SQLite does not enforce FOREIGN KEY constraints unless the connection has
-- run "PRAGMA foreign_keys = ON" -- db/loader.py sets this on every connection
-- it opens, since forgetting it would make every FK clause below a no-op.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Core tables (from data/raw/, 7 files)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS companies (
    id                 VARCHAR PRIMARY KEY,   -- NSE ticker; the FK target for every other table
    company_logo       TEXT,
    company_name       VARCHAR NOT NULL,
    chart_link         TEXT,
    about_company      TEXT,
    website            TEXT,
    nse_profile        TEXT,
    bse_profile        TEXT,
    -- Spec Section 5.1 documents face_value as non-nullable, but the real
    -- companies.xlsx has exactly one blank cell here (TVSMOTOR). Rejecting
    -- or dropping that company over one missing field would cascade-orphan
    -- all of its P&L/BS/CF/etc. rows via the FK constraints below -- a
    -- disproportionate loss for one blank cell, so the constraint here
    -- matches the real data rather than the spec's claim about it.
    face_value         NUMERIC,
    book_value         NUMERIC,
    roce_percentage    NUMERIC,
    roe_percentage     NUMERIC
);

-- profitandloss / balancesheet / cashflow all key on (company_id, year), not
-- the source file's "id" column -- the spec calls that id "not analytically
-- meaningful" (Section 5.2), a leftover row number from the scrape rather
-- than a real identity. We keep it as a plain column for traceability back
-- to the source row, but the composite (company_id, year) is what's
-- actually enforced as unique here, matching DQ-02's own definition of the
-- table's real primary key.

CREATE TABLE IF NOT EXISTS profitandloss (
    id                  INTEGER,
    company_id          VARCHAR NOT NULL REFERENCES companies(id),
    year                VARCHAR NOT NULL,      -- 'YYYY-MM', standardised by normalize_year()
    sales               NUMERIC NOT NULL,
    expenses            NUMERIC NOT NULL,
    -- Spec 5.2 marks these non-nullable too, but ~1% of real rows (12-13
    -- out of 1,070 post-cleaning) are genuinely blank here -- same call as
    -- face_value above: too small a fraction, and too disruptive to reject
    -- an otherwise-good P&L row over it, so the schema follows reality.
    -- The validator's own DQ-05 check already treats these as skippable
    -- (it does `if pd.isna(...): continue` rather than flagging them), so
    -- this isn't a new policy, just making the schema consistent with a
    -- decision the validator had already made.
    operating_profit    NUMERIC,
    opm_percentage      NUMERIC,
    other_income        NUMERIC,
    interest            NUMERIC,
    depreciation        NUMERIC,
    profit_before_tax   NUMERIC,
    tax_percentage      NUMERIC,
    net_profit          NUMERIC,
    eps                 NUMERIC,
    dividend_payout     NUMERIC,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS balancesheet (
    id                  INTEGER,
    company_id          VARCHAR NOT NULL REFERENCES companies(id),
    year                VARCHAR NOT NULL,
    equity_capital       NUMERIC NOT NULL,
    reserves             NUMERIC,
    borrowings           NUMERIC,
    other_liabilities    NUMERIC,
    total_liabilities    NUMERIC NOT NULL,
    fixed_assets         NUMERIC,
    cwip                 NUMERIC,
    investments          NUMERIC,
    other_asset          NUMERIC,
    total_assets         NUMERIC NOT NULL,
    PRIMARY KEY (company_id, year)
);

CREATE TABLE IF NOT EXISTS cashflow (
    id                   INTEGER,
    company_id           VARCHAR NOT NULL REFERENCES companies(id),
    year                 VARCHAR NOT NULL,
    operating_activity   NUMERIC,
    investing_activity   NUMERIC,
    financing_activity   NUMERIC,
    net_cash_flow        NUMERIC,
    PRIMARY KEY (company_id, year)
);

-- analysis.xlsx has ~9% coverage (spec 7.2) and stores growth figures as
-- free text like "10 Years: 21%" rather than numbers -- parsing that text
-- is explicitly a later NLP-module task (Sprint 5, D29-30), so these
-- columns stay TEXT here rather than being pre-parsed into NUMERIC. Storing
-- them raw now means the parser can be tested against the real stored
-- strings later instead of against a re-derived intermediate.
--
-- The spec's ER map (Section 7.1) claims a 1:1 cardinality with companies,
-- but the real file has 4 rows per covered company -- one per growth-period
-- window (10yr/5yr/3yr/1yr), all sharing the same company_id. UNIQUE on
-- company_id would reject 3 of every 4 real rows, so it's dropped here;
-- id (the source row number) is the only thing that's actually unique.
CREATE TABLE IF NOT EXISTS analysis (
    id                          INTEGER PRIMARY KEY,
    company_id                  VARCHAR NOT NULL REFERENCES companies(id),
    compounded_sales_growth     TEXT,
    compounded_profit_growth    TEXT,
    stock_price_cagr            TEXT,
    roe                         TEXT
);

-- documents.xlsx allows multiple annual-report rows per company per
-- calendar year in principle (spec: "1-20 annual report links per
-- company" total, not "per year"), so id is the real primary key here,
-- not (company_id, Year) -- unlike the three time-series tables above.
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY,
    company_id      VARCHAR NOT NULL REFERENCES companies(id),
    year            INTEGER NOT NULL,   -- source column is capitalised 'Year' in the Excel file; spec 5.6 flags this explicitly
    annual_report   TEXT
);

CREATE TABLE IF NOT EXISTS prosandcons (
    id            INTEGER PRIMARY KEY,
    company_id    VARCHAR NOT NULL REFERENCES companies(id),
    pros          TEXT,
    cons          TEXT
);

-- ---------------------------------------------------------------------------
-- Supplementary tables (from data/supporting/, 5 files -- populated Day 5)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sectors (
    company_id            VARCHAR PRIMARY KEY REFERENCES companies(id),  -- 1:1 with companies, full 92/92 coverage
    broad_sector          VARCHAR NOT NULL,
    sub_sector            VARCHAR NOT NULL,
    index_weight_pct      NUMERIC,
    market_cap_category   VARCHAR
);

CREATE TABLE IF NOT EXISTS stock_prices (
    company_id       VARCHAR NOT NULL REFERENCES companies(id),
    date             VARCHAR NOT NULL,   -- 'YYYY-MM-DD', first of month
    open_price       NUMERIC,
    high_price       NUMERIC,
    low_price        NUMERIC,
    close_price      NUMERIC,
    volume           INTEGER,
    adjusted_close   NUMERIC,
    PRIMARY KEY (company_id, date)
);

CREATE TABLE IF NOT EXISTS market_cap (
    company_id                VARCHAR NOT NULL REFERENCES companies(id),
    year                      INTEGER NOT NULL,   -- calendar year, unlike the 'YYYY-MM' financial-year strings elsewhere
    market_cap_crore          NUMERIC,
    enterprise_value_crore    NUMERIC,
    pe_ratio                  NUMERIC,
    pb_ratio                  NUMERIC,
    ev_ebitda                 NUMERIC,
    dividend_yield_pct        NUMERIC,
    PRIMARY KEY (company_id, year)
);

-- financial_ratios.xlsx already ships pre-computed KPIs as a supplementary
-- file, but the spec also has the Sprint 2 Ratio Engine independently
-- compute the same 14 metrics from P&L/BS/CF (Module 2). We load the
-- source file's version here on Day 5 for now; whether Sprint 2 overwrites
-- this table or writes to a second one is a decision for that sprint, not
-- this one -- flagging it here so it isn't forgotten.
CREATE TABLE IF NOT EXISTS financial_ratios (
    company_id                       VARCHAR NOT NULL REFERENCES companies(id),
    year                             VARCHAR NOT NULL,
    net_profit_margin_pct            NUMERIC,
    operating_profit_margin_pct      NUMERIC,
    return_on_equity_pct             NUMERIC,
    debt_to_equity                   NUMERIC,
    interest_coverage                NUMERIC,
    asset_turnover                   NUMERIC,
    free_cash_flow_cr                NUMERIC,
    capex_cr                         NUMERIC,
    earnings_per_share               NUMERIC,
    book_value_per_share             NUMERIC,
    dividend_payout_ratio_pct        NUMERIC,
    total_debt_cr                    NUMERIC,
    cash_from_operations_cr          NUMERIC,
    PRIMARY KEY (company_id, year)
);

-- Many-to-many: a company can belong to more than one peer group (spec
-- 7.1), so neither column alone can be the primary key.
CREATE TABLE IF NOT EXISTS peer_groups (
    company_id        VARCHAR NOT NULL REFERENCES companies(id),
    peer_group_name   VARCHAR NOT NULL,
    is_benchmark      BOOLEAN NOT NULL DEFAULT 0,
    PRIMARY KEY (company_id, peer_group_name)
);

-- Sprint 3, Day 18: PERCENT_RANK() per metric per peer group (spec's own
-- named schema: "SQLite: company_id, peer_group, metric, value,
-- percentile_rank, year"). Long/melted format (one row per
-- company x metric x group) rather than one wide row per company, because
-- a company can belong to more than one peer group -- a wide table would
-- need a variable, unbounded number of columns to hold "this company's
-- ROE percentile within EACH group it belongs to."
CREATE TABLE IF NOT EXISTS peer_percentiles (
    company_id        VARCHAR NOT NULL REFERENCES companies(id),
    peer_group        VARCHAR NOT NULL,
    metric             VARCHAR NOT NULL,
    value               NUMERIC,
    percentile_rank     NUMERIC NOT NULL,  -- 0.0-1.0, per spec's PERCENT_RANK() convention
    year                VARCHAR NOT NULL,
    PRIMARY KEY (company_id, peer_group, metric)
);
