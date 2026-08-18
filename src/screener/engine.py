"""Sprint 3 Screener Filter Engine -- Days 15-16.

Unlike the ETL pipeline (which reads Excel), this reads from
data/nifty100.db directly. That's a deliberate architectural choice: the
screener, the Sprint 4 dashboard, and any future API endpoint are all
consumers of the same already-built, already-cleaned database (spec
Section 9's system architecture explicitly describes this as the standard
pattern -- see Section 7.3's "Standard Join Pattern"). Re-running the Excel
ETL pipeline inside every screener call would be slower and would risk the
screener silently drifting out of sync with whatever's actually in the DB.

"Screener universe" = one row per company, using each company's LATEST
available year of financial_ratios, plus their latest market_cap snapshot,
plus 5yr Revenue/PAT CAGR computed on the fly from profitandloss (CAGR
isn't persisted anywhere -- see Sprint 2 notes on why), plus sector info
and the Sprint 2 data-quality caveat flag.
"""

import importlib.util
import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analytics"))
from cagr import cagr_for_company

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "screener_config.yaml")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")


def _import_db_loader():
    """Load db/loader.py by explicit path -- same collision reason as in
    src/analytics/populate_financial_ratios.py: db/loader.py and
    src/etl/loader.py share the bare name 'loader'.
    """
    path = os.path.join(os.path.dirname(__file__), "..", "..", "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


db_loader = _import_db_loader()


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_screener_universe(conn) -> pd.DataFrame:
    companies = pd.read_sql("SELECT id AS company_id, company_name, face_value FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)

    fr_all = pd.read_sql("SELECT * FROM financial_ratios", conn)
    fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    mc_all = pd.read_sql("SELECT company_id, year, pe_ratio, pb_ratio, dividend_yield_pct FROM market_cap", conn)
    mc_latest = mc_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
    mc_latest = mc_latest.drop(columns=["year"])  # calendar year, not directly comparable to fr's FY-year label

    # ROCE isn't a financial_ratios column (see Sprint 2 kickoff note -- the
    # spec's own financial_ratios.xlsx schema doesn't declare one), so it's
    # pulled from sector_roce_notes.csv, which already holds each company's
    # latest-year computed ROCE from the D13 cross-check step.
    roce_notes = pd.read_csv(os.path.join(OUTPUT_DIR, "sector_roce_notes.csv"))
    roce_latest = roce_notes[["company_id", "computed_roce_pct", "is_financial_sector"]]

    # 5yr Revenue & PAT CAGR, computed here rather than read from a table --
    # see src/analytics/cagr.py and the Sprint 2 decision not to persist CAGR.
    pl_all = pd.read_sql("SELECT company_id, year, sales, net_profit FROM profitandloss ORDER BY company_id, year", conn)
    cagr_rows = []
    for company_id, group in pl_all.groupby("company_id"):
        revenue_result = cagr_for_company(group.set_index("year")["sales"], windows=(5,))
        pat_result = cagr_for_company(group.set_index("year")["net_profit"], windows=(5,))
        cagr_rows.append({
            "company_id": company_id,
            "revenue_cagr_5yr_pct": revenue_result["cagr_5yr_pct"],
            "pat_cagr_5yr_pct": pat_result["cagr_5yr_pct"],
        })
    cagr_df = pd.DataFrame(cagr_rows)

    # Sprint 2's scale-anomaly finding (BEL/HAL/INDIGO/LT) -- flag any
    # company whose LATEST year (the one this universe actually uses) was
    # one of the affected rows, so screener/ranking output can surface the
    # caveat instead of silently ranking on numbers already known to be
    # unreliable. See engine.py callers for how this flag is surfaced.
    scale_flags = pd.read_csv(os.path.join(OUTPUT_DIR, "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    universe = fr_latest.merge(companies, on="company_id", how="left")
    universe = universe.merge(sectors, on="company_id", how="left")
    universe = universe.merge(mc_latest, on="company_id", how="left")
    universe = universe.merge(roce_latest, on="company_id", how="left")
    universe = universe.merge(cagr_df, on="company_id", how="left")
    universe["data_quality_caveat"] = universe.apply(
        lambda r: (r["company_id"], r["year"]) in flagged_keys, axis=1
    )
    return universe


# Maps each threshold key from screener_config.yaml to (universe column,
# comparison direction). "min" means the column must be >= the threshold;
# "max" means <= the threshold. Centralising this mapping is what lets
# apply_filters() stay generic instead of an if/elif chain per threshold --
# adding a new filterable metric later only means adding one line here and
# one line in the YAML, not new engine code.
_THRESHOLD_MAP = {
    "min_roe_pct": ("return_on_equity_pct", "min"),
    "min_roce_pct": ("computed_roce_pct", "min"),
    "min_npm_pct": ("net_profit_margin_pct", "min"),
    "max_de": ("debt_to_equity", "max"),
    "min_fcf_cr": ("free_cash_flow_cr", "min"),
    "max_pe": ("pe_ratio", "max"),
    "max_pb": ("pb_ratio", "max"),
    "min_dividend_yield_pct": ("dividend_yield_pct", "min"),
    "min_pat_cagr_5yr_pct": ("pat_cagr_5yr_pct", "min"),
    "min_revenue_cagr_5yr_pct": ("revenue_cagr_5yr_pct", "min"),
    "max_borrowings_for_debt_free": ("total_debt_cr", "max"),
    "min_interest_coverage": ("interest_coverage", "min"),
    "min_asset_turnover": ("asset_turnover", "min"),
}
# max_de_non_financial and max_capex_intensity_pct (from the YAML) aren't
# wired into a specific universe column here -- max_de_non_financial is a
# SCREENING-OUTLIER threshold (R-04's ">5 flag"), not a pass/fail filter,
# and capex_intensity isn't computed into the universe frame since no
# preset or the custom filter builder currently needs it. Both stay
# available in the YAML for an analyst to reference, but engine.py doesn't
# yet do anything with them -- flagging this rather than quietly ignoring
# unused config.


def apply_filters(universe: pd.DataFrame, filter_keys: list, thresholds: dict) -> pd.DataFrame:
    """Apply a list of threshold keys (from screener_config.yaml) as an AND filter.

    Rows with a NaN value for a filtered column always fail that filter --
    "we don't know" should never silently pass a screen, since that would
    let companies with missing data slip into a list an analyst is
    trusting to be pre-vetted.
    """
    mask = pd.Series(True, index=universe.index)
    for key in filter_keys:
        column, direction = _THRESHOLD_MAP[key]
        threshold_value = thresholds[key]
        values = universe[column]

        if direction == "min":
            passes = values >= threshold_value
        else:
            passes = values <= threshold_value

        # D/E-based filters carve out financial-sector companies entirely
        # (spec R-04 mitigation: "sectors.broad_sector used to carve out
        # Financials from D/E filter") -- banks/NBFCs run on leverage as
        # their business model, so a D/E<1 "quality" bar would wrongly
        # disqualify every bank rather than reflect anything about
        # quality. They pass this specific criterion automatically instead
        # of being evaluated by it.
        if column == "debt_to_equity":
            passes = passes | universe["is_financial_sector"].fillna(False)

        mask &= passes.fillna(False)
    return universe[mask].copy()


def run_preset(universe: pd.DataFrame, preset_name: str, config: dict) -> pd.DataFrame:
    preset_keys = list(config["presets"][preset_name].keys())
    return apply_filters(universe, preset_keys, config["thresholds"])
