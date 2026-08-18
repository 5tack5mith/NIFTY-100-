"""Sprint 6, Day 38-40: FastAPI server -- 16 endpoints per spec Section 15.

Run with: uvicorn src.api.main:app --port 8000  (or `make api`)
OpenAPI docs at /docs (spec: "OpenAPI docs at /docs").

16 endpoints, split across 7 routers by resource (companies: 8, screener: 1,
sectors: 2, peers: 2, market_cap: 1, portfolio: 1, health: 1):
1.  GET /api/v1/companies
2.  GET /api/v1/companies/{ticker}
3.  GET /api/v1/companies/{ticker}/pl
4.  GET /api/v1/companies/{ticker}/bs
5.  GET /api/v1/companies/{ticker}/cashflow
6.  GET /api/v1/companies/{ticker}/ratios
7.  GET /api/v1/companies/{ticker}/tearsheet
8.  GET /api/v1/companies/{ticker}/documents
9.  GET /api/v1/screener
10. GET /api/v1/sectors
11. GET /api/v1/sectors/{sector}/companies
12. GET /api/v1/peers/{group_name}
13. GET /api/v1/companies/{ticker}/peers/compare
14. GET /api/v1/market-cap/{ticker}
15. GET /api/v1/portfolio/stats
16. GET /api/v1/health

Every endpoint that returns ROE/ROCE/D-E/Asset-Turnover/Book-Value-per-
Share for a specific company-year attaches a data_quality_caveat field
when that row is one of the Sprint 2 BEL/HAL/INDIGO/LT flagged years --
see db.py's data_quality_caveat_for(), called from companies.py (get_
company, get_ratios), screener.py, sectors.py, and peers.py. This was the
explicit ask in the Sprint 6 kickoff instructions: the caveat needs to
reach API consumers, not just the internal CSVs and dashboard.
"""

import os
import sys

from fastapi import FastAPI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "routers"))
import companies, screener, sectors, peers, market_cap, portfolio, health

app = FastAPI(
    title="Nifty 100 Financial Intelligence Platform API",
    version="1.0.0",
    description="REST API over the Nifty 100 Financial Intelligence Platform's SQLite database.",
)

for router_module in (companies, screener, sectors, peers, market_cap, portfolio, health):
    app.include_router(router_module.router)
