import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_cleaning import prepare_delivery_fields
from src.ranking_engine import (
    BATTER_DIMENSION_WEIGHTS,
    BOWLER_DIMENSION_WEIGHTS,
    batting_summary,
    bowling_summary,
)


def _deliveries(rows):
    base = {
        "runs": 0,
        "extras1_runs": 0,
        "extras_2_runs": 0,
        "is_wicket": False,
        "is_four": False,
        "is_six": False,
        "dismissal_type": None,
        "dismissed_player_id": None,
        "extras_type": None,
    }
    return prepare_delivery_fields(pd.DataFrame([{**base, **row} for row in rows]))


def test_no_ball_counts_as_faced_but_not_legal_and_team_total_once():
    df = _deliveries([{
        "extras_type": "Overstep",
        "extras1_runs": 1,
        "extras_2_runs": 4,
        "striker_id": 10,
        "runs": 0,
    }])
    row = df.iloc[0]
    assert row["is_batter_ball_faced"]
    assert not row["is_legal_ball"]
    assert row["team_runs_this_delivery"] == 1
    assert row["team_runs_additive_candidate"] == 5
    assert row["bowler_conceded_runs_known"] == 1
    assert row["bowler_runs_unallocated"] == 4
    batter = batting_summary(df.assign(striker_id=10), 10)
    assert batter["balls_faced"] == 1
    boundary_no_ball = _deliveries([{
        "extras_type": "Overstep",
        "extras1_runs": 1,
        "runs": 4,
        "striker_id": 10,
    }])
    batter = batting_summary(boundary_no_ball, 10)
    assert batter["balls_faced"] == 1
    assert batter["runs"] == 4
    assert batter["strike_rate"] == 400


def test_wide_bye_and_legbye_cricket_denominators():
    df = _deliveries([
        {"extras_type": "wide", "extras1_runs": 1},
        {"extras_type": "byes", "extras1_runs": 2},
        {"extras_type": "legbyes", "extras1_runs": 1},
    ])
    assert df["is_batter_ball_faced"].tolist() == [False, True, True]
    assert df["is_legal_ball"].tolist() == [False, True, True]
    assert df["team_runs_this_delivery"].tolist() == [1, 2, 1]
    assert df["bowler_conceded_runs_known"].tolist() == [1, 0, 0]


def test_dot_balls_exclude_scoreboard_extras_and_nonlegal_deliveries():
    df = _deliveries([
        {"extras_type": "", "runs": 0},
        {"extras_type": "legbyes", "extras1_runs": 1},
        {"extras_type": "Overstep", "extras1_runs": 1},
        {"extras_type": "other", "extras1_runs": 0, "extras_2_runs": 1},
    ])
    assert df["is_batter_dot_ball"].tolist() == [True, False, False, False]
    assert df["is_bowler_dot_ball"].tolist() == [True, False, False, False]


def test_bowler_economy_uses_legal_ball_denominator_and_known_charges():
    df = _deliveries([
        {"extras_type": "", "runs": 2},
        {"extras_type": "wide", "extras1_runs": 1},
        {"extras_type": "legbyes", "extras1_runs": 2},
        {"extras_type": "Overstep", "extras1_runs": 1, "extras_2_runs": 4},
    ])
    result = bowling_summary(df)
    assert result["legal_balls"] == 2
    assert result["runs_conceded_known"] == 4
    assert result["unallocated_runs"] == 4
    assert result["economy_known"] == 12


def test_dismissal_is_assigned_by_dismissed_player_id_not_striker():
    df = _deliveries([{
        "striker_id": 10,
        "non_striker_id": 20,
        "is_wicket": True,
        "dismissal_type": "RunOut",
        "dismissed_player_id": 20,
        "is_batter_ball_faced": True,
    }])
    assert batting_summary(df, 10)["dismissals"] == 0
    assert batting_summary(df, 20)["dismissals"] == 1


def test_non_bowler_dismissal_is_not_credited_as_bowler_wicket():
    df = _deliveries([{
        "extras_type": "",
        "is_wicket": True,
        "dismissal_type": "RunOut",
        "dismissed_player_id": 20,
    }])
    assert not df.iloc[0]["is_bowling_wicket"]
    non_bowler_dismissals = _deliveries([
        {
            "is_wicket": True,
            "dismissal_type": dismissal,
            "dismissed_player_id": 20,
        }
        for dismissal in (
            "RunOut",
            "Retire Out",
            "Obstructing the field",
            "Obstracting the field",
        )
    ])
    assert not non_bowler_dismissals["is_bowling_wicket"].any()


def test_composite_dimensions_are_unique_and_weights_sum_to_one():
    assert len(BATTER_DIMENSION_WEIGHTS) == 4
    assert len(BOWLER_DIMENSION_WEIGHTS) == 3
    assert abs(sum(BATTER_DIMENSION_WEIGHTS.values()) - 1) < 1e-12
    assert abs(sum(BOWLER_DIMENSION_WEIGHTS.values()) - 1) < 1e-12
