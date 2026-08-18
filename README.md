# Nifty 100 Financial Intelligence Platform

ETL pipeline + analytics platform for 92 Nifty 100 (Indian large-cap) companies:
data cleaning and validation, a financial ratio engine, a company screener,
peer comparison, and a Streamlit dashboard.

## Setup

```bash
py -3.14 -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

All commands below assume the `.venv` interpreter (`.venv/Scripts/python.exe`
on Windows), not a bare system Python -- the system Python typically won't
have `pandas`/`openpyxl`/`streamlit` installed.

## Build the database

Run once (or after any change to `data/raw/` or `data/supporting/`):

```bash
.venv/Scripts/python.exe db/loader.py                       # core + supplementary tables
.venv/Scripts/python.exe src/analytics/populate_financial_ratios.py  # ratio engine
.venv/Scripts/python.exe src/analytics/peer.py               # peer percentiles
```

This produces `data/nifty100.db` plus several output files under `output/`
(`load_audit.csv`, `validation_failures.csv`, `capital_allocation.csv`,
`sector_roce_notes.csv`, `ratio_edge_cases.log`, `scale_anomaly_flags.csv`).

## Run the dashboard

```bash
.venv/Scripts/python.exe -m streamlit run src/dashboard/app.py
```

Opens at `http://localhost:8501`. 9 screens: Overview (Home), Company
Profile, Screener, Peer Comparison, Trend Analysis, Sector Analysis,
Capital Allocation Map, Annual Reports, Valuation.

## Run the screener / peer / report exports directly (without the dashboard)

```bash
.venv/Scripts/python.exe src/screener/ranking.py           # output/screener_output.xlsx
.venv/Scripts/python.exe src/reports/radar_charts.py        # reports/radar_charts/*.png (92 files)
.venv/Scripts/python.exe src/reports/peer_comparison_export.py  # output/peer_comparison.xlsx
.venv/Scripts/python.exe src/analytics/valuation.py         # output/valuation_summary.xlsx
```

## Run tests

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

## Known data-quality caveat

**BEL, HAL, INDIGO, and LT** have balance sheet figures that appear scaled
incorrectly relative to their P&L for some years (see
`output/scale_anomaly_flags.csv` and `output/ratio_edge_cases.log` for the
exact company-years affected). This was not corrected in the data --
ROCE, Asset Turnover, D/E, and Book Value/Share are unreliable for those
rows specifically. The screener, peer comparison exports, radar charts,
and the dashboard all surface a warning wherever an affected company/year
is shown; other years and other metrics for these companies are
unaffected.

## Project structure

```
src/etl/          Excel loaders, normalisers, DQ validator, cleaner, pipeline
src/analytics/     Ratio engine, CAGR engine, cash flow KPIs, peer percentiles, valuation
src/screener/      Filter engine, ranking/composite score
src/reports/       Radar charts, peer comparison export
src/dashboard/     Streamlit app (app.py + pages/)
db/                schema.sql, loader.py, exploratory_queries.sql
config/            screener_config.yaml, .env.template
tests/             pytest suite (etl/, kpi/, screener/, analytics/)
output/            Generated CSVs, logs, and Excel exports
reports/           radar_charts/, sprint retrospectives, DQ review notes
```

## Project status

Sprints 1-4 complete (Data Foundation, Ratio Engine, Screener & Peer
Comparison, Dashboard & Valuation). See `reports/` for sprint
retrospectives and data quality review notes.
