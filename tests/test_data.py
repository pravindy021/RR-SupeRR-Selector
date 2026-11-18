import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import load_data
from src.data_cleaning import clean_data
from src.feature_engineering import add_match_situation


def test_required_files_load():
    data = load_data(ROOT / "data" / "RR_DATASETS" / "Data Pack")
    assert set(data) == {
        "ball_by_ball", "competitions", "competition_team_player_mapping",
        "matches", "playing_eleven", "teams",
    }


def test_no_duplicate_full_ball_rows():
    data = load_data(ROOT / "data" / "RR_DATASETS" / "Data Pack")
    assert int(data["ball_by_ball"].duplicated().sum()) == 0


def test_source_over_ids_and_delivery_sequence_keys_are_valid():
    data = load_data(ROOT / "data" / "RR_DATASETS" / "Data Pack")
    ball = data["ball_by_ball"]
    over_ids = pd.to_numeric(ball["overid"], errors="raise")
    assert over_ids.notna().all()
    assert over_ids.mod(1).eq(0).all()
    assert over_ids.ge(1).all()
    assert over_ids.le(20).all()
    assert not ball.duplicated(
        ["match_id", "innings", "innings_ball_num"]
    ).any()


def test_legal_ball_excludes_wide_and_no_ball():
    data = clean_data(load_data(ROOT / "data" / "RR_DATASETS" / "Data Pack"))
    ball = data["ball_by_ball"]
    assert not ball.loc[ball["extras_type"].str.lower().eq("wide"), "is_legal_ball"].any()
    assert not ball.loc[ball["extras_type"].str.lower().eq("overstep"), "is_legal_ball"].any()
    assert ball.loc[ball["extras_type"].str.lower().eq("overstep"), "is_batter_ball_faced"].all()


def test_all_source_revised_limits_are_applied_to_the_correct_innings():
    source = load_data(ROOT / "data" / "RR_DATASETS" / "Data Pack")
    data = clean_data(source)
    matches = data["match_context"]
    revised_matches = matches[
        matches["first_inn_revised_overs"].notna()
        | matches["second_inn_revised_overs"].notna()
    ]
    assert matches["first_inn_revised_overs"].notna().sum() == 25
    assert matches["second_inn_revised_overs"].notna().sum() == 25
    subset = data["ball_by_ball"][
        data["ball_by_ball"]["match_id"].isin(revised_matches["match_id"])
    ]
    reconstructed = add_match_situation(subset, revised_matches, data["teams"])
    for row in revised_matches.itertuples(index=False):
        for innings, revision in (
            (1, row.first_inn_revised_overs),
            (2, row.second_inn_revised_overs),
        ):
            if pd.isna(revision):
                continue
            observed = reconstructed.loc[
                reconstructed["match_id"].eq(row.match_id)
                & reconstructed["innings"].eq(innings),
                "innings_limit_balls",
            ]
            if observed.empty:
                assert row.result == "No Result"
                continue
            assert observed.eq(int(revision)).all()
