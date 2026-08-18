"""Sprint 3, Day 19: 8-axis radar chart PNG per company.

Spec Module 4.2 says "Plotly radar / matplotlib polar" -- explicitly
offering both as valid choices. This uses matplotlib: the project's venv
has matplotlib but not kaleido (the package Plotly needs to export static
PNGs without a browser/Node dependency), and installing a new package
outside what's already in requirements.txt is a bigger decision than this
one chart deserves. matplotlib's polar projection produces the same
8-axis radar shape with zero new dependencies.

Peer group coverage is only 56/92 companies (spec's own risk register,
R-10, flags this as expected and says the peer module must "gracefully
handle companies not in any group"). For the 36 companies with no peer
group: this falls back to a whole-universe percentile (reusing
ranking.winsorized_score, the same normalisation the screener's composite
score uses) instead of a peer-group percentile, with a note on the chart
saying so -- so every one of the 92 companies still gets a chart (matching
the D-10 deliverable: "One radar chart per company"), rather than silently
skipping over a third of the dataset.
"""

import importlib.util
import os
import sys

import matplotlib
matplotlib.use("Agg")  # headless rendering -- no display needed to write PNG files
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "screener"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analytics"))

from engine import build_screener_universe
from ranking import winsorized_score
from peer import add_eps_cagr, RADAR_METRICS

RADAR_CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "radar_charts")


def _import_db_loader():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "db", "loader.py")
    spec = importlib.util.spec_from_file_location("db_loader_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


db_loader = _import_db_loader()


def build_whole_universe_percentiles(universe: pd.DataFrame) -> pd.DataFrame:
    """Fallback percentile scores (0-1) for companies with no peer group,
    using the same P10/P90 winsorised normalisation the screener's
    composite score uses -- consistent methodology across the project
    rather than inventing a second normalisation scheme just for radar
    charts.
    """
    scored = universe.copy()
    for metric_name, (column, lower_is_better) in RADAR_METRICS.items():
        scored[f"_score_{metric_name}"] = winsorized_score(scored[column], lower_is_better) / 100
    return scored


def draw_radar(company_id: str, company_name: str, values: dict, peer_avg: dict | None,
                has_peer_group: bool, has_scale_caveat: bool, save_path: str) -> None:
    axes_labels = list(RADAR_METRICS.keys())
    n = len(axes_labels)
    angles = [i / n * 2 * np.pi for i in range(n)] + [0]

    company_values = [values.get(m, 0) or 0 for m in axes_labels] + [values.get(axes_labels[0], 0) or 0]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, company_values, color="#2563eb", linewidth=2, label=company_id)
    ax.fill(angles, company_values, color="#2563eb", alpha=0.25)

    if peer_avg is not None:
        avg_values = [peer_avg.get(m, 0) or 0 for m in axes_labels] + [peer_avg.get(axes_labels[0], 0) or 0]
        ax.plot(angles, avg_values, color="#94a3b8", linewidth=1.5, linestyle="--", label="Peer group avg")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axes_labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_yticklabels([])
    title = f"{company_id} -- {company_name}"
    if not has_peer_group:
        title += "\n(no peer group assigned -- shown vs. full 92-company universe)"
    if has_scale_caveat:
        title += "\nCAUTION: balance-sheet-derived metrics (ROCE, D/E) unreliable for this year"
        title_color = "#b91c1c"
    else:
        title_color = "black"
    ax.set_title(title, fontsize=9, color=title_color)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=7)

    fig.tight_layout()
    fig.savefig(save_path, dpi=100)
    plt.close(fig)


def run() -> int:
    os.makedirs(RADAR_CHARTS_DIR, exist_ok=True)
    conn = db_loader.get_connection()
    try:
        universe = build_screener_universe(conn)
        universe = add_eps_cagr(universe, conn)
        peer_percentiles = pd.read_sql("SELECT * FROM peer_percentiles", conn)
        peer_groups = pd.read_sql("SELECT company_id, peer_group_name FROM peer_groups", conn)
    finally:
        conn.close()

    universe_scored = build_whole_universe_percentiles(universe)
    fallback_group = universe_scored[[f"_score_{m}" for m in RADAR_METRICS]].mean()

    # Same Sprint 2 scale-anomaly flag the screener surfaces (see
    # screener/engine.py) -- ROCE and D/E both derive from total_assets/
    # equity/borrowings, so a radar chart for BEL/HAL/INDIGO/LT would show
    # a striking, misleading shape on exactly those two axes without this.
    scale_flags = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "..", "output", "scale_anomaly_flags.csv"))
    flagged_keys = set(zip(scale_flags["company_id"], scale_flags["year"]))

    charts_written = 0
    for _, company in universe.iterrows():
        company_id = company["company_id"]
        companys_groups = peer_groups[peer_groups["company_id"] == company_id]["peer_group_name"]

        if len(companys_groups) > 0:
            # Company may be in multiple groups -- use the first one for
            # the radar chart (a single chart can only show one peer
            # comparison; the full multi-group detail lives in
            # peer_comparison.xlsx's one-sheet-per-group layout, D20).
            group_name = companys_groups.iloc[0]
            group_rows = peer_percentiles[
                (peer_percentiles["company_id"] == company_id) & (peer_percentiles["peer_group"] == group_name)
            ]
            values = dict(zip(group_rows["metric"], group_rows["percentile_rank"]))
            peer_avg = {m: 0.5 for m in RADAR_METRICS}  # by definition, the group's own average percentile is 0.5
            has_peer_group = True
        else:
            row_scores = universe_scored[universe_scored["company_id"] == company_id].iloc[0]
            values = {m: row_scores.get(f"_score_{m}") for m in RADAR_METRICS}
            peer_avg = fallback_group.rename(lambda c: c.replace("_score_", "")).to_dict()
            has_peer_group = False

        has_scale_caveat = (company_id, company["year"]) in flagged_keys
        save_path = os.path.join(RADAR_CHARTS_DIR, f"{company_id}.png")
        draw_radar(company_id, company["company_name"], values, peer_avg,
                   has_peer_group, has_scale_caveat, save_path)
        charts_written += 1

    return charts_written


if __name__ == "__main__":
    count = run()
    print(f"Radar charts written: {count} -> {RADAR_CHARTS_DIR}")
