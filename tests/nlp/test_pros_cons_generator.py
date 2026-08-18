"""Tests for the pros/cons rule engine (Module 9.2) -- especially the
scale-anomaly caveat treatment, which is the whole reason this module
exists in its current form rather than a simpler threshold-only version.

Run with: pytest tests/nlp/test_pros_cons_generator.py -v
"""

import sys
import os

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "nlp"))

from pros_cons_generator import _apply_rules, _pro_rules, _con_rules, generate_for_company, SCALE_SENSITIVE_CAVEAT_SUFFIX


def _bundle(**overrides):
    fr_latest = pd.Series({
        "return_on_equity_pct": 25.0, "computed_roce_pct": 25.0, "debt_to_equity": 0.5,
        "net_profit_margin_pct": 10.0, "interest_coverage": 3.0,
        "dividend_payout_ratio_pct": 40.0, "total_debt_cr": 100.0, "asset_turnover": 1.0,
        "tax_percentage": 25.0,
    })
    base = {
        "company_id": "TEST", "latest_year": "2024-03", "fr_latest": fr_latest,
        "fcf_series": pd.Series({"2020-03": 10, "2021-03": 10, "2022-03": 10, "2023-03": 10, "2024-03": 10}),
        "opm_series": pd.Series({"2022-03": 20, "2023-03": 18, "2024-03": 15}),
        "cfo_series": pd.Series({"2024-03": 50}),
        "cff_series": pd.Series({"2024-03": -10}),
        "revenue_cagr_5yr": 20.0, "pat_cagr_5yr": 20.0, "eps_cagr_5yr": 20.0,
        "avg_cfo_quality_5yr": 1.2, "latest_capex_intensity": 2.0, "latest_net_profit": 100.0,
    }
    base.update(overrides)
    return base


def test_roe_rule_triggers_without_caveat_when_not_flagged():
    bundle = _bundle()
    rows = _apply_rules(bundle, _pro_rules(), "pro", flagged_keys=set())
    roe_rows = [r for r in rows if r["rule_triggered"] == "ROE > 20%"]
    assert len(roe_rows) == 1
    assert roe_rows[0]["data_quality_caveat"] is False
    assert SCALE_SENSITIVE_CAVEAT_SUFFIX not in roe_rows[0]["text"]


def test_roe_rule_gets_caveat_when_company_year_flagged():
    bundle = _bundle()
    flagged = {("TEST", "2024-03")}
    rows = _apply_rules(bundle, _pro_rules(), "pro", flagged_keys=flagged)
    roe_rows = [r for r in rows if r["rule_triggered"] == "ROE > 20%"]
    assert roe_rows[0]["data_quality_caveat"] is True
    assert SCALE_SENSITIVE_CAVEAT_SUFFIX in roe_rows[0]["text"]


def test_non_scale_sensitive_rule_never_gets_caveat_even_when_flagged():
    # FCF-based rule -- not scale-sensitive (doesn't depend on total_assets/
    # equity/borrowings) -- must NOT get the caveat even for a flagged year.
    bundle = _bundle()
    flagged = {("TEST", "2024-03")}
    rows = _apply_rules(bundle, _pro_rules(), "pro", flagged_keys=flagged)
    fcf_rows = [r for r in rows if r["rule_triggered"] == "FCF positive 5yr"]
    assert len(fcf_rows) == 1
    assert fcf_rows[0]["data_quality_caveat"] is False


def test_de_con_rule_is_scale_sensitive():
    bundle = _bundle(fr_latest=pd.Series({**_bundle()["fr_latest"].to_dict(), "debt_to_equity": 3.0}))
    flagged = {("TEST", "2024-03")}
    rows = _apply_rules(bundle, _con_rules(), "con", flagged_keys=flagged)
    de_rows = [r for r in rows if r["rule_triggered"] == "D/E > 2"]
    assert de_rows[0]["data_quality_caveat"] is True


def test_confidence_never_below_60_for_triggered_rules():
    bundle = _bundle()
    pro_rows = _apply_rules(bundle, _pro_rules(), "pro", flagged_keys=set())
    con_rows = _apply_rules(bundle, _con_rules(), "con", flagged_keys=set())
    for row in pro_rows + con_rows:
        assert row["confidence_pct"] > 60


def test_generate_for_company_always_has_pro_and_con():
    # A "boring" company that trips none of the specific thresholds should
    # still get exactly one fallback pro and one fallback con.
    boring_fr = pd.Series({
        "return_on_equity_pct": 12.0, "computed_roce_pct": 12.0, "debt_to_equity": 1.0,
        "net_profit_margin_pct": 8.0, "interest_coverage": 3.0,
        "dividend_payout_ratio_pct": 45.0, "total_debt_cr": 50.0, "asset_turnover": 1.0,
        "tax_percentage": 25.0,
    })
    bundle = _bundle(
        fr_latest=boring_fr,
        fcf_series=pd.Series({"2024-03": 5}),  # not 5 consecutive positive years
        opm_series=pd.Series({"2024-03": 10}),  # not declining (insufficient history)
        revenue_cagr_5yr=8.0, pat_cagr_5yr=8.0, eps_cagr_5yr=8.0,
        avg_cfo_quality_5yr=0.8, latest_capex_intensity=5.0, latest_net_profit=10.0,
    )
    rows = generate_for_company(bundle, flagged_keys=set())
    types = [r["type"] for r in rows]
    assert "pro" in types
    assert "con" in types
    assert all(r["confidence_pct"] > 60 for r in rows)
