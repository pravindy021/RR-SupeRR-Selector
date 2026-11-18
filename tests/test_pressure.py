import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_cleaning import prepare_delivery_fields
from src.feature_engineering import add_match_situation
from src.pressure_detection import pressure_mask


def _source_ball(innings, seq, overid, runs, wicket=False, dismissed=None):
    return {
        "match_id": 1,
        "innings": innings,
        "overid": overid,
        "over_ball_num": seq,
        "innings_ball_num": seq,
        "batting_team_id": 10 if innings in (1, 3) else 20,
        "bowling_team_id": 20 if innings in (1, 3) else 10,
        "striker_id": 100 + innings,
        "striker_name": f"Player {100 + innings}",
        "non_striker_id": 200 + innings,
        "non_striker_name": f"Player {200 + innings}",
        "bowler_id": 300 + innings,
        "bowler_name": f"Bowler {300 + innings}",
        "runs": runs,
        "extras1_runs": 0,
        "extras_2_runs": 0,
        "is_wicket": wicket,
        "dismissal_type": "RunOut" if wicket else None,
        "dismissed_player_id": dismissed,
        "is_four": False,
        "is_six": False,
        "extras_type": None,
    }


def test_state_is_pre_delivery_uses_source_over_and_revised_balls():
    raw = pd.DataFrame([
        _source_ball(1, 1, 1, 1),
        _source_ball(1, 2, 1, 1),
        _source_ball(2, 1, 15, 2, wicket=True, dismissed=202),
        # A large current-ball score/wicket must not leak into its own pressure state.
        _source_ball(2, 2, 17, 200, wicket=True, dismissed=102),
    ])
    ball = prepare_delivery_fields(raw)
    match = pd.DataFrame([{
        "match_id": 1,
        "comp_id": 1,
        "comp_name": "IPL 2024",
        "match_format": "T20",
        "season": "2024",
        "revised_target": 202,
        "first_inn_revised_overs": 120,
        "second_inn_revised_overs": 120,
        "home_team_id": 10,
        "away_team_id": 20,
        "home_team": "Home",
        "away_team": "Away",
    }])
    df = add_match_situation(ball, match)
    current = df[(df["innings"] == 2) & (df["innings_ball_num"] == 2)].iloc[0]
    assert current["over_number"] == 17
    assert current["innings_limit_balls"] == 120
    assert current["innings_runs_before"] == 2
    assert current["wickets_lost_before"] == 1
    assert current["legal_balls_before"] == 1
    assert current["balls_remaining_before"] == 119
    assert abs(current["required_run_rate_before"] - (200 * 6 / 119)) < 1e-12
    assert current["innings_completion_status"] == "target_reached"
    assert bool(pressure_mask(df).loc[current.name])
    assert current["runs_required_before"] == 200
    assert current["wickets_remaining_before"] == 9


def test_no_ball_does_not_consume_a_bowler_ball_remaining():
    rows = pd.DataFrame([
        _source_ball(2, 1, 1, 0),
        {**_source_ball(2, 2, 1, 0), "extras_type": "Overstep", "extras1_runs": 1},
    ])
    match = pd.DataFrame([{
        "match_id": 1, "comp_id": 1, "comp_name": "Series", "match_format": "T20I",
        "season": "2024", "revised_target": 100, "first_inn_revised_overs": None,
        "second_inn_revised_overs": 12, "home_team_id": 10, "away_team_id": 20,
        "home_team": "Home", "away_team": "Away",
    }])
    df = add_match_situation(prepare_delivery_fields(rows), match)
    second = df.iloc[1]
    assert second["legal_balls_before"] == 1
    assert second["balls_remaining_before"] == 11
    assert second["innings_completion_status"] == "incomplete_or_interrupted"


def test_current_wicket_cannot_create_pressure_for_its_own_delivery():
    rows = []
    for delivery in range(1, 6):
        rows.append(_source_ball(
            2,
            delivery,
            1,
            0,
            wicket=True,
            dismissed=102,
        ))
    match = pd.DataFrame([{
        "match_id": 1, "comp_id": 1, "comp_name": "Series", "match_format": "T20I",
        "season": "2024", "revised_target": 6, "first_inn_revised_overs": None,
        "second_inn_revised_overs": 12, "home_team_id": 10, "away_team_id": 20,
        "home_team": "Home", "away_team": "Away",
    }])
    df = add_match_situation(prepare_delivery_fields(pd.DataFrame(rows)), match)
    fifth = df.iloc[4]
    assert fifth["wickets_lost_before"] == 4
    assert not bool(pressure_mask(df).iloc[4])


def test_unresolved_secondary_runs_are_not_silently_used_in_chase_state():
    rows = [_source_ball(1, 1, 1, 0)]
    for delivery in range(1, 7):
        extra = {
            "extras_type": "other",
            "extras_2_runs": 3,
        } if delivery == 1 else {}
        rows.append({
            **_source_ball(2, delivery, 1, 0),
            **extra,
        })
    rows.append(_source_ball(2, 7, 2, 0))
    match = pd.DataFrame([{
        "match_id": 1, "comp_id": 1, "comp_name": "Series", "match_format": "T20I",
        "season": "2024", "revised_target": 190, "first_inn_revised_overs": None,
        "second_inn_revised_overs": 120, "home_team_id": 10, "away_team_id": 20,
        "home_team": "Home", "away_team": "Away",
    }])
    df = add_match_situation(prepare_delivery_fields(pd.DataFrame(rows)), match)
    last = df.iloc[-1]
    assert last["innings_runs_before"] == 0
    assert last["innings_runs_additive_candidate_before"] == 3
    assert last["match_state_secondary_extras_uncertain"]
    assert bool(pressure_mask(df).iloc[-1])
    assert not bool(
        pressure_mask(df, score_variant="additive_candidate").iloc[-1]
    )


def test_revised_overs_are_interpreted_as_source_ball_limits():
    rows = pd.DataFrame([_source_ball(1, 1, 1, 0)])
    match = pd.DataFrame([{
        "match_id": 1, "comp_id": 1, "comp_name": "IPL 2024", "match_format": "T20",
        "season": "2024", "revised_target": None, "first_inn_revised_overs": 30,
        "second_inn_revised_overs": None, "home_team_id": 10, "away_team_id": 20,
        "home_team": "Home", "away_team": "Away",
    }])
    df = add_match_situation(prepare_delivery_fields(rows), match)
    assert df.iloc[0]["innings_limit_balls"] == 30


def test_death_over_without_batting_state_signals_is_not_pressure():
    rows = pd.DataFrame([
        _source_ball(1, seq, 18, 0)
        for seq in range(1, 109)
    ])
    match = pd.DataFrame([{
        "match_id": 1, "comp_id": 1, "comp_name": "Series", "match_format": "T20I",
        "season": "2024", "revised_target": None, "first_inn_revised_overs": 120,
        "second_inn_revised_overs": None, "home_team_id": 10, "away_team_id": 20,
        "home_team": "Home", "away_team": "Away",
    }])
    df = add_match_situation(prepare_delivery_fields(rows), match)
    assert df["over_number"].eq(18).all()
    assert df["balls_remaining_before"].gt(12).all()
    assert df["wickets_lost_before"].eq(0).all()
    assert not pressure_mask(df).any()
