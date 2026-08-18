"""Sprint 3, Day 18: peer group percentile ranking.

For each of the 11 peer groups (spec Section 6.5), and for each of the 8
radar-chart metrics (spec Module 4.2: ROE, ROCE, NPM, D/E, FCF, PAT CAGR,
Revenue CAGR, EPS CAGR), computes PERCENT_RANK() -- each company's
percentile position (0.0-1.0) among the OTHER companies in its own peer
group, per metric. A company in multiple peer groups gets a separate
percentile per group, since "how does this company rank among IT
Services peers" and "...among all Automobile makers" are different
questions even if a company happened to belong to both.

For D/E, LOWER is better (less leverage), so its percentile is inverted --
without this, a bank with high leverage (normal for banks) would show as
"top percentile" on D/E, which reads backwards to anyone looking at the
radar chart or comparison table expecting "higher percentile = better".
"""

import importlib.util
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "screener"))

from cagr import cagr_for_company
from engine import build_screener_universe  # reuses the same one-row-per-company universe builder

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")

# Maps each of the 8 radar metrics to (universe column, lower_is_better).
RADAR_METRICS = {
    "ROE": ("return_on_equity_pct", False),
    "ROCE": ("computed_roce_pct", False),
    "NPM": ("net_profit_margin_pct", False),
    "D/E": ("debt_to_equity", True),
    "FCF": ("free_cash_flow_cr", False),
    "PAT_CAGR_5yr": ("pat_cagr_5yr_pct", False),
    "Revenue_CAGR_5yr": ("revenue_cagr_5yr_pct", False),
    "EPS_CAGR_5yr": ("eps_cagr_5yr_pct", False),
}


def _import_db_loader():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


db_loader = _import_db_loader()


def add_eps_cagr(universe: pd.DataFrame, conn) -> pd.DataFrame:
    """EPS 5yr CAGR isn't computed by build_screener_universe() (the
    screener presets don't need it), but the radar chart does -- computed
    here rather than duplicating it into engine.py, since it's specific to
    the peer/radar use case.
    """
    pl_all = pd.read_sql("SELECT company_id, year, eps FROM profitandloss ORDER BY company_id, year", conn)
    rows = []
    for company_id, group in pl_all.groupby("company_id"):
        result = cagr_for_company(group.set_index("year")["eps"], windows=(5,))
        rows.append({"company_id": company_id, "eps_cagr_5yr_pct": result["cagr_5yr_pct"]})
    return universe.merge(pd.DataFrame(rows), on="company_id", how="left")


def compute_peer_percentiles(universe: pd.DataFrame, peer_groups: pd.DataFrame) -> pd.DataFrame:
    """Long-format table: one row per (company_id, peer_group, metric)."""
    merged = peer_groups.merge(universe, on="company_id", how="left")

    rows = []
    for group_name, group_df in merged.groupby("peer_group_name"):
        for metric_name, (column, lower_is_better) in RADAR_METRICS.items():
            # PERCENT_RANK semantics: rank among the values actually
            # present in this group -- pandas' rank(pct=True) on a Series
            # with NaNs automatically excludes them from the ranking pool
            # (a company with no data for this metric gets no percentile
            # row at all, rather than being force-ranked against data it
            # doesn't have).
            values = group_df[column]
            ranks = values.rank(pct=True, ascending=not lower_is_better)
            for _, row in group_df.iterrows():
                percentile = ranks.loc[row.name]
                if pd.isna(percentile):
                    continue
                rows.append({
                    "company_id": row["company_id"],
                    "peer_group": group_name,
                    "metric": metric_name,
                    "value": row[column],
                    "percentile_rank": percentile,
                    "year": row["year"],
                })
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    conn = db_loader.get_connection()
    try:
        universe = build_screener_universe(conn)
        universe = add_eps_cagr(universe, conn)
        peer_groups = pd.read_sql("SELECT company_id, peer_group_name FROM peer_groups", conn)

        peer_percentiles = compute_peer_percentiles(universe, peer_groups)

        db_loader.create_schema(conn)  # idempotent (CREATE TABLE IF NOT EXISTS) -- adds peer_percentiles if missing
        conn.execute("DELETE FROM peer_percentiles")
        peer_percentiles.to_sql("peer_percentiles", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    return peer_percentiles


if __name__ == "__main__":
    result = run()
    print(f"peer_percentiles table populated: {len(result)} rows")
    print(f"Peer groups covered: {result['peer_group'].nunique()}")
    print(f"Companies covered: {result['company_id'].nunique()}")
