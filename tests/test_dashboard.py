from io import BytesIO

import pandas as pd
import pytest

from src.dashboard_helpers import compare_players, filter_rankings, rankings_csv_bytes


@pytest.fixture
def ranking_rows():
    return pd.DataFrame([
        {
            "rank": 1, "player_name": "A Batter", "player_id": 1,
            "team_context": "Team A; Team B", "ipl_pressure_matches": 4,
            "t20i_pressure_matches": 0, "final_composite_score": 0.8,
        },
        {
            "rank": 2, "player_name": "B Batter", "player_id": 2,
            "team_context": "Team C", "ipl_pressure_matches": 0,
            "t20i_pressure_matches": 5, "final_composite_score": 0.7,
        },
        {
            "rank": 3, "player_name": "C Batter", "player_id": 3,
            "team_context": "Team B", "ipl_pressure_matches": 3,
            "t20i_pressure_matches": 4, "final_composite_score": 0.6,
        },
    ])


def test_ranking_filters_apply_competition_team_and_player_search(ranking_rows):
    filtered = filter_rankings(
        ranking_rows,
        context="IPL",
        teams=["Team B"],
        player_query="c BAT",
    )
    assert filtered[["player_id", "player_name"]].values.tolist() == [
        [3, "C Batter"]
    ]


def test_player_comparison_returns_only_selected_ranked_players(ranking_rows):
    compared = compare_players(ranking_rows, ["C Batter", "A Batter"])
    assert compared["player_id"].tolist() == [1, 3]
    assert compared["final_composite_score"].tolist() == [0.8, 0.6]


def test_unknown_dashboard_context_is_an_explicit_error(ranking_rows):
    with pytest.raises(ValueError, match="Unknown competition context"):
        filter_rankings(ranking_rows, context="Other")


def test_filtered_rankings_export_contains_exact_filtered_rows(ranking_rows):
    filtered = filter_rankings(
        ranking_rows, context="IPL", teams=["Team B"], player_query="c BAT"
    )
    exported = pd.read_csv(BytesIO(rankings_csv_bytes(filtered)))
    assert exported[["rank", "player_id", "player_name"]].values.tolist() == [
        [3, 3, "C Batter"]
    ]
