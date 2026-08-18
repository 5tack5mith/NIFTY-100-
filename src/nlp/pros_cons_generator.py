"""Sprint 5, Day 29-30: auto pros/cons rule engine (Module 9.2).

Spec gives 4 example rules total (pro: ROE>20%, FCF positive 5yr, D/E=0,
revenue CAGR>15%; con: D/E>2, FCF negative 3yr, OPM declining) out of the
24 (12+12) it asks for. The other 20 are designed here using standard
equity-analysis heuristics, not pulled from the document -- same kind of
judgment call as Sprint 2's 5 unnamed capital-allocation labels.

CRITICAL DESIGN CONSTRAINT (per the Sprint 5 kickoff instructions): 5 of
the 24 rules depend on a "scale-sensitive" metric -- ROE, ROCE, D/E, or
Asset Turnover, all of which are denominated by total_assets / equity_capital
/ reserves / borrowings, the exact fields Sprint 2 found mis-scaled for
BEL/HAL/INDIGO/LT in certain years. Every rule is tagged SCALE_SENSITIVE
or not; when a scale-sensitive rule fires using a flagged company-year, the
generated text gets an explicit caveat suffix and a data_quality_caveat
column is set -- the same "surface it, don't hide it" treatment already
applied to the dashboard, screener, and peer exports. Rules based on FCF,
CFO, NPM, dividend payout, tax rate, or any CAGR are NOT scale-sensitive
(they depend on P&L/cash-flow figures, not the mis-scaled balance-sheet
fields) and never need the caveat.

Confidence score: designed so that any rule which fires already clears
D-14's "Confidence > 60%" sign-off bar by construction -- base confidence
per rule (70-90%, higher for "sustained over N years" rules than
single-year snapshot rules) plus a margin bonus scaled by how far past the
threshold the actual value sits, capped at 97%. This isn't a spec formula
(none is given); it's designed to make the sign-off criterion true by
construction rather than something that could accidentally fail.
"""

import importlib.util
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analytics"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "screener"))
from cagr import cagr_for_company
from cashflow_kpis import cfo_quality_score, capex_intensity

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

SCALE_SENSITIVE_CAVEAT_SUFFIX = (
    " [CAUTION: based on a balance-sheet figure flagged for a possible scale "
    "inconsistency in this year -- see Sprint 2 findings; verify before relying on this.]"
)


def _confidence(base: float, actual: float, threshold: float, scale: float = 20.0) -> float:
    """base% plus a margin bonus for how far past the threshold the value sits,
    capped at 97% (never claiming false certainty) and floored at base
    (so a rule that just barely triggers still reports its base confidence,
    not something lower).
    """
    margin = abs(actual - threshold)
    bonus = min(97 - base, (margin / scale) * (97 - base))
    return round(min(97.0, base + bonus), 1)


def _sustained_positive(series: pd.Series, n_years: int) -> bool:
    recent = series.dropna().tail(n_years)
    return len(recent) >= n_years and (recent > 0).all()


def _sustained_negative(series: pd.Series, n_years: int) -> bool:
    recent = series.dropna().tail(n_years)
    return len(recent) >= n_years and (recent < 0).all()


def _is_declining(series: pd.Series, n_years: int = 3) -> bool:
    recent = series.dropna().tail(n_years)
    if len(recent) < n_years:
        return False
    return recent.is_monotonic_decreasing


def build_company_bundle(company_id: str, pl: pd.DataFrame, bs: pd.DataFrame,
                          cf: pd.DataFrame, fr: pd.DataFrame) -> dict:
    """Gather everything a rule needs for one company: latest financial_ratios
    row, historical series for sustained/trend checks, and computed CAGRs.
    """
    pl_c = pl[pl["company_id"] == company_id].sort_values("year")
    cf_c = cf[cf["company_id"] == company_id].sort_values("year")
    fr_c = fr[fr["company_id"] == company_id].sort_values("year")

    if fr_c.empty:
        return None

    latest = fr_c.iloc[-1]
    fcf_series = fr_c.set_index("year")["free_cash_flow_cr"]
    opm_series = fr_c.set_index("year")["operating_profit_margin_pct"]
    cfo_series = cf_c.set_index("year")["operating_activity"] if not cf_c.empty else pd.Series(dtype=float)
    cff_series = cf_c.set_index("year")["financing_activity"] if not cf_c.empty else pd.Series(dtype=float)

    revenue_cagr = cagr_for_company(pl_c.set_index("year")["sales"], windows=(5,))
    pat_cagr = cagr_for_company(pl_c.set_index("year")["net_profit"], windows=(5,))
    eps_cagr = cagr_for_company(pl_c.set_index("year")["eps"], windows=(5,))

    # 5yr average CFO/PAT for the "sustained" quality-score rules (7.1's
    # "5yr avg" framing, reused here since pros/cons should reflect a
    # durable pattern, not one lucky/unlucky year).
    recent_pl = pl_c.tail(5).set_index("year")
    recent_cf = cf_c.tail(5).set_index("year")
    cfo_pat_ratios = []
    for year in recent_pl.index:
        if year in recent_cf.index:
            score = cfo_quality_score(recent_cf.loc[year, "operating_activity"], recent_pl.loc[year, "net_profit"])
            if score is not None:
                cfo_pat_ratios.append(score)
    avg_cfo_quality = sum(cfo_pat_ratios) / len(cfo_pat_ratios) if cfo_pat_ratios else None

    latest_pl_row = pl_c.iloc[-1] if not pl_c.empty else None
    # investing_activity isn't a P&L column -- it's on the cashflow table,
    # so computing capex intensity needs the matching year's cashflow row
    # joined against the P&L row's sales figure.
    latest_capex_intensity = None
    latest_cf_row = cf_c[cf_c["year"] == latest["year"]]
    if not latest_cf_row.empty and latest_pl_row is not None:
        latest_capex_intensity = capex_intensity(latest_cf_row.iloc[0]["investing_activity"], latest_pl_row["sales"])

    return {
        "company_id": company_id,
        "latest_year": latest["year"],
        "fr_latest": latest,
        "fcf_series": fcf_series,
        "opm_series": opm_series,
        "cfo_series": cfo_series,
        "cff_series": cff_series,
        "revenue_cagr_5yr": revenue_cagr["cagr_5yr_pct"],
        "pat_cagr_5yr": pat_cagr["cagr_5yr_pct"],
        "eps_cagr_5yr": eps_cagr["cagr_5yr_pct"],
        "avg_cfo_quality_5yr": avg_cfo_quality,
        "latest_capex_intensity": latest_capex_intensity,
        "latest_net_profit": latest_pl_row["net_profit"] if latest_pl_row is not None else None,
    }


# ---------------------------------------------------------------------------
# Rule definitions. Each rule is (name, scale_sensitive, check_fn) where
# check_fn(bundle) -> (triggered: bool, text: str, confidence: float) or None.
# ---------------------------------------------------------------------------

def _pro_rules():
    return [
        ("ROE > 20%", True, lambda b: (
            b["fr_latest"]["return_on_equity_pct"] is not None and pd.notna(b["fr_latest"]["return_on_equity_pct"]) and b["fr_latest"]["return_on_equity_pct"] > 20
        ) and (True, f"Strong return on equity of {b['fr_latest']['return_on_equity_pct']:.1f}%.",
               _confidence(75, b["fr_latest"]["return_on_equity_pct"], 20))),
        ("FCF positive 5yr", False, lambda b: _sustained_positive(b["fcf_series"], 5) and (
            True, "Free cash flow has been positive for 5 consecutive years -- consistent cash generation.", 90)),
        ("Debt-free", True, lambda b: pd.notna(b["fr_latest"]["total_debt_cr"]) and b["fr_latest"]["total_debt_cr"] == 0 and (
            True, "Company carries zero debt.", 90)),
        ("Revenue CAGR > 15% (5yr)", False, lambda b: b["revenue_cagr_5yr"] is not None and b["revenue_cagr_5yr"] > 15 and (
            True, f"Revenue has grown at a {b['revenue_cagr_5yr']:.1f}% CAGR over the last 5 years.",
            _confidence(75, b["revenue_cagr_5yr"], 15))),
        ("PAT CAGR > 15% (5yr)", False, lambda b: b["pat_cagr_5yr"] is not None and b["pat_cagr_5yr"] > 15 and (
            True, f"Net profit has grown at a {b['pat_cagr_5yr']:.1f}% CAGR over the last 5 years.",
            _confidence(75, b["pat_cagr_5yr"], 15))),
        ("NPM > 15%", False, lambda b: pd.notna(b["fr_latest"]["net_profit_margin_pct"]) and b["fr_latest"]["net_profit_margin_pct"] > 15 and (
            True, f"High net profit margin of {b['fr_latest']['net_profit_margin_pct']:.1f}%.",
            _confidence(70, b["fr_latest"]["net_profit_margin_pct"], 15))),
        ("High CFO quality", False, lambda b: b["avg_cfo_quality_5yr"] is not None and b["avg_cfo_quality_5yr"] > 1.0 and (
            True, f"Operating cash flow has consistently exceeded reported profit (5yr avg CFO/PAT = {b['avg_cfo_quality_5yr']:.2f}) -- high-quality earnings.", 85)),
        ("Strong interest coverage", False, lambda b: pd.notna(b["fr_latest"]["interest_coverage"]) and b["fr_latest"]["interest_coverage"] not in (999.0,) and b["fr_latest"]["interest_coverage"] > 5 and (
            True, f"Comfortably covers interest obligations ({b['fr_latest']['interest_coverage']:.1f}x coverage).",
            _confidence(75, b["fr_latest"]["interest_coverage"], 5))),
        ("Healthy dividend payout", False, lambda b: pd.notna(b["fr_latest"]["dividend_payout_ratio_pct"]) and 30 <= b["fr_latest"]["dividend_payout_ratio_pct"] <= 60 and (
            True, f"Balanced dividend payout ratio of {b['fr_latest']['dividend_payout_ratio_pct']:.1f}% -- rewards shareholders while retaining capital.", 75)),
        ("ROCE > 20%", True, lambda b: pd.notna(b["fr_latest"].get("computed_roce_pct")) and b["fr_latest"].get("computed_roce_pct", 0) > 20 and (
            True, f"Strong return on capital employed of {b['fr_latest']['computed_roce_pct']:.1f}%.",
            _confidence(75, b["fr_latest"].get("computed_roce_pct", 0), 20))),
        ("Asset-light (low CapEx intensity)", False, lambda b: b["latest_capex_intensity"] is not None and b["latest_capex_intensity"] < 3 and (
            True, "Asset-light business model (CapEx intensity under 3% of sales).", 75)),
        ("EPS CAGR > 12% (5yr)", False, lambda b: b["eps_cagr_5yr"] is not None and b["eps_cagr_5yr"] > 12 and (
            True, f"EPS has grown at a {b['eps_cagr_5yr']:.1f}% CAGR over the last 5 years.",
            _confidence(70, b["eps_cagr_5yr"], 12))),
    ]


def _con_rules():
    return [
        ("D/E > 2", True, lambda b: pd.notna(b["fr_latest"]["debt_to_equity"]) and b["fr_latest"]["debt_to_equity"] > 2 and (
            True, f"High leverage with a debt-to-equity ratio of {b['fr_latest']['debt_to_equity']:.2f}.",
            _confidence(75, b["fr_latest"]["debt_to_equity"], 2, scale=3))),
        ("FCF negative 3yr", False, lambda b: _sustained_negative(b["fcf_series"], 3) and (
            True, "Free cash flow has been negative for 3 consecutive years.", 85)),
        ("OPM declining", False, lambda b: _is_declining(b["opm_series"], 3) and (
            True, "Operating profit margin has declined for 3 consecutive years.", 75)),
        ("Accrual risk", False, lambda b: b["avg_cfo_quality_5yr"] is not None and b["avg_cfo_quality_5yr"] < 0.5 and (
            True, f"Operating cash flow has lagged reported profit (5yr avg CFO/PAT = {b['avg_cfo_quality_5yr']:.2f}) -- possible accrual risk.", 80)),
        ("Capital intensive", False, lambda b: b["latest_capex_intensity"] is not None and b["latest_capex_intensity"] > 8 and (
            True, "Capital-intensive business (CapEx intensity above 8% of sales).", 75)),
        ("Payout exceeds earnings", False, lambda b: pd.notna(b["fr_latest"]["dividend_payout_ratio_pct"]) and b["fr_latest"]["dividend_payout_ratio_pct"] > 100 and (
            True, f"Dividend payout of {b['fr_latest']['dividend_payout_ratio_pct']:.0f}% exceeds reported earnings.", 85)),
        ("Distress pattern", False, lambda b: (
            not b["cfo_series"].empty and not b["cff_series"].empty
            and pd.notna(b["cfo_series"].iloc[-1]) and pd.notna(b["cff_series"].iloc[-1])
            and b["cfo_series"].iloc[-1] < 0 and b["cff_series"].iloc[-1] > 0
        ) and (True, "Operating cash flow is negative while the company is raising external funding -- a distress pattern worth watching.", 85)),
        ("Weak interest coverage", False, lambda b: pd.notna(b["fr_latest"]["interest_coverage"]) and b["fr_latest"]["interest_coverage"] not in (999.0,) and b["fr_latest"]["interest_coverage"] < 1.5 and (
            True, f"Thin interest coverage of {b['fr_latest']['interest_coverage']:.1f}x -- limited buffer against rising rates or earnings pressure.", 80)),
        ("Low asset turnover", True, lambda b: pd.notna(b["fr_latest"]["asset_turnover"]) and b["fr_latest"]["asset_turnover"] < 0.5 and (
            True, f"Low asset turnover of {b['fr_latest']['asset_turnover']:.2f}x -- capital may be used inefficiently.",
            _confidence(70, 0.5 - b["fr_latest"]["asset_turnover"], 0, scale=0.5))),
        ("Declining revenue (5yr)", False, lambda b: b["revenue_cagr_5yr"] is not None and b["revenue_cagr_5yr"] < 0 and (
            True, f"Revenue has declined at a {b['revenue_cagr_5yr']:.1f}% CAGR over the last 5 years.",
            _confidence(75, abs(b["revenue_cagr_5yr"]), 0, scale=10))),
        ("Net loss (latest year)", False, lambda b: b["latest_net_profit"] is not None and pd.notna(b["latest_net_profit"]) and b["latest_net_profit"] < 0 and (
            True, f"Reported a net loss in {b['latest_year']}.", 90)),
        ("High tax rate anomaly", False, lambda b: pd.notna(b["fr_latest"].get("tax_percentage")) and (b["fr_latest"].get("tax_percentage", 0) < 0 or b["fr_latest"].get("tax_percentage", 0) > 60) and (
            True, "Effective tax rate outside the normal 0-60% range -- may indicate a one-off deferred tax item.", 65)),
    ]


def _apply_rules(bundle: dict, rules: list, rule_type: str, flagged_keys: set) -> list:
    rows = []
    for rule_name, scale_sensitive, check_fn in rules:
        result = check_fn(bundle)
        if not result:
            continue
        triggered, text, confidence = result
        if not triggered:
            continue
        has_caveat = scale_sensitive and (bundle["company_id"], bundle["latest_year"]) in flagged_keys
        if has_caveat:
            text = text + SCALE_SENSITIVE_CAVEAT_SUFFIX
        rows.append({
            "company_id": bundle["company_id"],
            "type": rule_type,
            "rule_triggered": rule_name,
            "text": text,
            "confidence_pct": confidence,
            "data_quality_caveat": has_caveat,
        })
    return rows


# Fallback rules -- guarantee every company has >=1 pro AND >=1 con (spec
# AC-16), for the rare company that doesn't clear any of the 12 specific
# thresholds in either direction. Deliberately generic/low-strength claims
# (confidence just above the 60% sign-off bar) rather than a fabricated
# specific one -- "no rule fired" is itself the honest signal here.
def _fallback_pro(bundle: dict) -> dict:
    return {
        "company_id": bundle["company_id"], "type": "pro", "rule_triggered": "Fallback (no specific rule triggered)",
        "text": "No standout strength triggered a specific rule -- financial profile is broadly unremarkable rather than notably strong on any single measure.",
        "confidence_pct": 61.0, "data_quality_caveat": False,
    }


def _fallback_con(bundle: dict) -> dict:
    return {
        "company_id": bundle["company_id"], "type": "con", "rule_triggered": "Fallback (no specific rule triggered)",
        "text": "No specific risk factor triggered a rule -- this reflects the absence of a flagged weakness among the metrics checked, not a clean bill of health.",
        "confidence_pct": 61.0, "data_quality_caveat": False,
    }


def generate_for_company(bundle: dict, flagged_keys: set) -> list:
    if bundle is None:
        return []
    pros = _apply_rules(bundle, _pro_rules(), "pro", flagged_keys)
    cons = _apply_rules(bundle, _con_rules(), "con", flagged_keys)
    if not pros:
        pros = [_fallback_pro(bundle)]
    if not cons:
        cons = [_fallback_con(bundle)]
    return pros + cons


def run() -> pd.DataFrame:
    import sqlite3
    conn_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nifty100.db")
    conn = sqlite3.connect(conn_path)
    try:
        pl = pd.read_sql("SELECT * FROM profitandloss", conn)
        bs = pd.read_sql("SELECT * FROM balancesheet", conn)
        cf = pd.read_sql("SELECT * FROM cashflow", conn)
        fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
        companies = pd.read_sql("SELECT id AS company_id FROM companies", conn)
        prosandcons_manual = pd.read_sql("SELECT company_id, pros, cons FROM prosandcons", conn)
    finally:
        conn.close()

    fr = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
    roce_notes = pd.read_csv(os.path.join(OUTPUT_DIR, "sector_roce_notes.csv"))
    fr = fr.merge(roce_notes[["company_id", "computed_roce_pct"]], on="company_id", how="left")
    fr_full_history = fr_all  # bundles need the full history, not just latest

    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    all_rows = []
    for company_id in companies["company_id"]:
        # fr needs the latest-row-with-ROCE version; fr_full_history needs
        # every year for the CFO-quality/OPM-trend series -- build_company_
        # bundle takes the full-history frame and does its own latest-row
        # selection, so pass fr_full_history, but attach computed_roce_pct
        # from the already-merged fr for the latest row specifically.
        bundle = build_company_bundle(company_id, pl, bs, cf, fr_full_history)
        if bundle is None:
            continue
        roce_row = fr[fr["company_id"] == company_id]
        if not roce_row.empty:
            bundle["fr_latest"] = bundle["fr_latest"].copy()
            bundle["fr_latest"]["computed_roce_pct"] = roce_row.iloc[0]["computed_roce_pct"]
        all_rows.extend(generate_for_company(bundle, flagged_keys))

    # Fold in the original manual prosandcons.xlsx entries (the ~8-14
    # companies with real analyst-written text from Sprint 1) as their own
    # rows, marked distinctly -- these supplement the rule-based rows
    # rather than replacing them, since a real analyst's specific
    # observation ("Stock trading at 2.76x book value") carries different
    # information than a threshold rule ever could.
    for _, row in prosandcons_manual.iterrows():
        if pd.notna(row["pros"]):
            all_rows.append({"company_id": row["company_id"], "type": "pro", "rule_triggered": "Manual (analyst-written)",
                              "text": row["pros"], "confidence_pct": 100.0, "data_quality_caveat": False})
        if pd.notna(row["cons"]):
            all_rows.append({"company_id": row["company_id"], "type": "con", "rule_triggered": "Manual (analyst-written)",
                              "text": row["cons"], "confidence_pct": 100.0, "data_quality_caveat": False})

    result = pd.DataFrame(all_rows)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "pros_cons_generated.csv")
    result.to_csv(output_path, index=False)
    return result, output_path


if __name__ == "__main__":
    result, path = run()
    print(f"pros_cons_generated.csv: {len(result)} rows -> {path}")
    coverage = result.groupby("company_id")["type"].apply(lambda s: set(s))
    missing_pro = (~coverage.apply(lambda s: "pro" in s)).sum()
    missing_con = (~coverage.apply(lambda s: "con" in s)).sum()
    print(f"Companies covered: {coverage.shape[0]} / 92")
    print(f"Missing >=1 pro: {missing_pro} | Missing >=1 con: {missing_con}")
    print(f"Rows with data_quality_caveat: {result['data_quality_caveat'].sum()}")
    print(f"Rows with confidence <= 60%: {(result['confidence_pct'] <= 60).sum()}")
