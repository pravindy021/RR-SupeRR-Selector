
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.dashboard_helpers import compare_players, filter_rankings, rankings_csv_bytes


RANK_DIR = ROOT / "outputs" / "rankings"
TABLE_DIR = ROOT / "outputs" / "tables"
def _load_rankings(role):
    return {
        "All": pd.read_csv(RANK_DIR / f"top_10_{role}.csv"),
        "IPL": pd.read_csv(RANK_DIR / f"top_10_{role}_ipl.csv"),
        "T20I": pd.read_csv(RANK_DIR / f"top_10_{role}_t20i.csv"),
    }


batters = _load_rankings("batters")
bowlers = _load_rankings("bowlers")
competition = pd.read_csv(TABLE_DIR / "competition_performance_summary.csv")
extras_audit = pd.read_csv(TABLE_DIR / "extras_semantics_audit.csv").iloc[0]

st.set_page_config(page_title="RR SupeRR Selector", layout="wide")
st.title("Rajasthan Royals — SupeRR Selector")
st.caption("Historical pressure-performance analysis; not a current auction-availability list.")


def _render_rankings(role, ranking_sets):
    context = st.selectbox(
        "Ranking context",
        ["All", "IPL", "T20I"],
        key=f"{role}_context_filter",
    )
    rankings = ranking_sets[context]
    team_options = sorted({
        team
        for value in rankings["team_context"].dropna().astype(str)
        for team in value.split("; ")
        if team
    })
    teams = st.multiselect(
        "Historical team context",
        team_options,
        key=f"{role}_team_filter",
    )
    query = st.text_input("Player name", key=f"{role}_player_search")
    filtered = filter_rankings(rankings, "All", teams, query)
    if role == "Batter":
        columns = [
            "rank", "player_name", "player_id", "team_context", "competition_context",
            "pressure_opportunities", "pressure_balls", "pressure_runs",
            "pressure_strike_rate", "dismissals", "final_composite_score",
        ]
        chart_metric = "pressure_strike_rate"
    else:
        columns = [
            "rank", "player_name", "player_id", "team_context", "competition_context",
            "pressure_opportunities", "pressure_legal_balls", "wickets",
            "pressure_runs_conceded_known", "unallocated_pressure_extras",
            "pressure_economy_known", "final_composite_score",
        ]
        chart_metric = "pressure_economy_known"
    st.dataframe(filtered[columns], width="stretch", hide_index=True)
    st.download_button(
        f"Download filtered {role.lower()} CSV",
        rankings_csv_bytes(filtered),
        f"top_10_{role.lower()}_{context.lower()}_filtered.csv",
        "text/csv",
        key=f"{role}_download",
    )
    if filtered.empty:
        st.info("No ranked players match these filters.")
    else:
        st.bar_chart(filtered.set_index("player_name")[[chart_metric]])

    compared_names = st.multiselect(
        "Compare Top-10 players",
        rankings["player_name"].tolist(),
        max_selections=4,
        key=f"{role}_compare",
    )
    compared = compare_players(rankings, compared_names)
    if not compared.empty:
        compare_columns = [
            column for column in columns + [
                "potential_role_profile", "selection_justification",
                "evidence_limitations",
            ]
            if column in compared.columns
        ]
        st.subheader("Player comparison")
        st.dataframe(
            compared[compare_columns],
            width="stretch",
            hide_index=True,
        )
    st.caption(
        f"{context} uses its independently normalized context score; All uses the "
        "70% IPL / 30% T20I composite. Pressure states can differ under the unresolved "
        "extras_2_runs scenario."
    )


batting_tab, bowling_tab, method_tab = st.tabs(
    ["Batter rankings", "Bowler rankings", "Methodology and data quality"]
)
with batting_tab:
    st.subheader("Top 10 batters under pressure")
    _render_rankings("Batter", batters)

with bowling_tab:
    st.subheader("Top 10 bowlers under pressure")
    st.warning(
        "Bowler economy, dot-ball attribution on unresolved rows, and related ranks are "
        "provisional: source extras are not fully allocatable."
    )
    _render_rankings("Bowler", bowlers)

with method_tab:
    st.subheader("Pressure framework")
    st.markdown("""
    Match state is evaluated immediately before each delivery using source `overid`,
    source-component runs, prior wickets, and legal balls already bowled. A death over
    alone is not enough: first-innings late-over pressure also requires a five-wicket
    fall or the final 10% of legal balls. Chases use pre-ball required rate, wickets
    lost, remaining legal balls, and a late-over state condition.

    **Batting:** strike rate (35%), boundary rate (20%), dot-ball avoidance (20%),
    dismissal avoidance (25%). No-ball counts as faced; wides do not. Dismissals use
    `dismissed_player_id`.

    **Bowling:** known-charge economy (40%, lower is better), wickets per six legal
    balls (35%), and legal-ball dot rate (25%). Wides/no-balls are excluded from legal
    balls; byes/leg-byes are legal but not charged to the bowler.

    IPL and T20I are scored separately, then combined at 70%/30%; other T20 competitions
    are summarized separately. Context-specific percentile normalization, median shrinkage,
    sample adjustment, and match consistency are detailed in the methodology report.
    """)
    st.error(
        "No supplied data dictionary defines `extras_2_runs` or `other` extras. "
        f"{int(extras_audit.extras_2_run_total)} secondary runs across "
        f"{int(extras_audit.nonzero_extras_2_rows)} rows and "
        f"{int(extras_audit.extras1_other_or_missing_total)} ambiguous `extras1_runs` "
        "are not charged to bowlers. The additive candidate changes "
        f"{int(extras_audit.pressure_flags_differ_by_total_scenario)} pressure flags; "
        "rankings remain provisional pending supplier clarification."
    )
    st.subheader("Pressure performance by competition")
    st.dataframe(competition, width="stretch", hide_index=True)
