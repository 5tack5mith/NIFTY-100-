"""API endpoint tests -- Sprint 6, Day 41-42.

Uses FastAPI's TestClient (in-process, no live server needed) so this
suite runs standalone as part of `pytest tests/`, unlike the manual
urllib-based checks used during initial development (which caught the
NaN-serialization bug and the SQLite threading bug against the real,
running server -- this file re-tests correctness now that both are fixed,
it doesn't replace having actually run the live server once).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "api"))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_all_12_tables():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["db_row_counts"]) == 12
    assert data["db_row_counts"]["companies"] == 92


def test_list_companies_search_filter():
    response = client.get("/api/v1/companies", params={"search": "TCS"})
    assert response.status_code == 200
    results = response.json()
    assert any(r["id"] == "TCS" for r in results)


def test_company_detail_unknown_ticker_404():
    response = client.get("/api/v1/companies/FAKECO")
    assert response.status_code == 404


def test_company_detail_known_ticker():
    response = client.get("/api/v1/companies/TCS")
    assert response.status_code == 200
    data = response.json()
    assert data["company"]["id"] == "TCS"
    assert data["latest_kpis"] is not None


def test_ratios_endpoint_hal_carries_caveat_on_flagged_years():
    """The specific regression this suite exists to prevent: this exact
    endpoint 500'd with a JSON serialization error the first time it was
    hit against real data (NaN in a financial_ratios column). Also checks
    the Sprint 6 kickoff's explicit requirement -- the caveat must reach
    API responses, not just internal files/dashboard.
    """
    response = client.get("/api/v1/companies/HAL/ratios")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 0
    flagged = [r for r in rows if r.get("data_quality_caveat")]
    unflagged = [r for r in rows if not r.get("data_quality_caveat")]
    assert len(flagged) > 0  # HAL has real flagged years
    assert len(unflagged) > 0  # ...but not ALL of them (early years are clean)
    for row in flagged:
        assert "message" in row["data_quality_caveat"]


def test_ratios_endpoint_no_nan_in_response():
    # Companies with missing/sparse data (e.g. thin coverage) are exactly
    # where a NaN would slip through if the df_to_records() fix regressed.
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    # Spot check a company likely to have sparse ratios data
    response = client.get("/api/v1/companies/JIOFIN/ratios")
    assert response.status_code == 200
    body_text = response.text
    assert "NaN" not in body_text  # NaN is invalid JSON and must never appear literally


def test_screener_filters_by_min_roe():
    response = client.get("/api/v1/screener", params={"min_roe": 50})
    assert response.status_code == 200
    data = response.json()
    for r in data["results"]:
        if r["return_on_equity_pct"] is not None:
            assert r["return_on_equity_pct"] >= 50


def test_sectors_summary_has_10_sectors():
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    assert len(response.json()) == 10


def test_sector_companies_unknown_sector_404():
    response = client.get("/api/v1/sectors/NotARealSector/companies")
    assert response.status_code == 404


def test_peers_unknown_group_404():
    response = client.get("/api/v1/peers/NotARealGroup")
    assert response.status_code == 404


def test_peers_known_group():
    response = client.get("/api/v1/peers/IT Services")
    assert response.status_code == 200
    data = response.json()
    assert any(c["company_id"] == "TCS" and c["is_benchmark"] for c in data)


def test_peers_compare_no_group_assigned_handled_gracefully():
    # Spec R-10: companies with no peer group must be handled gracefully,
    # not crash -- find a company genuinely outside any group.
    response = client.get("/api/v1/companies")
    all_ids = {c["id"] for c in response.json()}
    peer_response = client.get("/api/v1/peers/IT Services")
    grouped_ids = {c["company_id"] for group in ["IT Services"] for c in client.get(f"/api/v1/peers/{group}").json()}
    ungrouped = next(iter(all_ids - grouped_ids), None)
    assert ungrouped is not None
    response = client.get(f"/api/v1/companies/{ungrouped}/peers/compare")
    assert response.status_code == 200
    # Either genuinely ungrouped (radar_data is None) or it happens to be
    # in some OTHER peer group -- both are valid; the key assertion is it
    # doesn't error either way.
    assert response.json()["company_id"] == ungrouped


def test_market_cap_is_flagged_simulated():
    response = client.get("/api/v1/market-cap/TCS")
    assert response.status_code == 200
    assert "SIMULATED" in response.json()["simulated_data_notice"]


def test_portfolio_stats_excludes_debt_free_sentinel():
    """interest_coverage's 999.0 debt-free sentinel (Sprint 2) must not
    appear as a real max/P90 value -- it would badly skew this table if
    the sentinel-exclusion fix in portfolio.py regressed.
    """
    response = client.get("/api/v1/portfolio/stats")
    assert response.status_code == 200
    rows = {r["metric"]: r for r in response.json()}
    icr_row = rows.get("interest_coverage")
    if icr_row:
        assert icr_row["P90"] < 999.0


def test_documents_endpoint_flags_url_validity_by_presence():
    response = client.get("/api/v1/companies/TCS/documents")
    assert response.status_code == 200
    for row in response.json():
        assert row["is_url_valid"] == (row["annual_report"] is not None)


def test_openapi_spec_has_exactly_16_endpoints():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert len(response.json()["paths"]) == 16
