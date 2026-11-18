import pandas as pd


WIDE_TYPES = {"wide"}
NO_BALL_TYPES = {"overstep"}
PENALTY_TYPES = {"penalty"}
NON_BOWLER_DISMISSALS = {
    "runout",
    "retire out",
    "obstracting the field",
    "obstructing the field",
}


def prepare_delivery_fields(ball):
    ball = ball.copy()
    for column in ("runs", "extras1_runs", "extras_2_runs"):
        values = pd.to_numeric(ball[column], errors="coerce")
        if values.isna().any() or values.lt(0).any():
            raise ValueError(f"{column} contains missing, invalid, or negative values")
        ball[column] = values

    ball["is_wicket"] = ball["is_wicket"].fillna(False).astype(bool)
    ball["is_four"] = ball["is_four"].fillna(False).astype(bool)
    ball["is_six"] = ball["is_six"].fillna(False).astype(bool)
    ball["extras_type"] = ball["extras_type"].fillna("").astype(str).str.strip().str.lower()
    ball["dismissal_type"] = ball["dismissal_type"].fillna("").astype(str).str.strip().str.lower()
    ball["is_wide"] = ball["extras_type"].isin(WIDE_TYPES)
    ball["is_no_ball"] = ball["extras_type"].isin(NO_BALL_TYPES)
    ball["is_penalty"] = ball["extras_type"].isin(PENALTY_TYPES)

    # A no-ball counts as faced; wides and standalone penalty events do not.
    ball["is_batter_ball_faced"] = ~(ball["is_wide"] | ball["is_penalty"])
    ball["is_legal_ball"] = ~(
        ball["is_wide"] | ball["is_no_ball"] | ball["is_penalty"]
    )

    # Keep the unresolved secondary component separate from the source subtotal.
    ball["team_runs_this_delivery"] = ball["runs"] + ball["extras1_runs"]
    ball["team_runs_additive_candidate"] = (
        ball["team_runs_this_delivery"] + ball["extras_2_runs"]
    )

    known_extra_charge = ball["extras_type"].isin(WIDE_TYPES | NO_BALL_TYPES)
    ball["bowler_conceded_runs_known"] = (
        ball["runs"] + ball["extras1_runs"].where(known_extra_charge, 0)
    )
    ambiguous_extra1 = ball["extras_type"].isin({"other", ""})
    ball["bowler_runs_unallocated"] = (
        ball["extras_2_runs"] + ball["extras1_runs"].where(ambiguous_extra1, 0)
    )
    ball["is_batter_dot_ball"] = (
        ball["is_batter_ball_faced"] & ball["team_runs_additive_candidate"].eq(0)
    )
    ball["is_bowler_dot_ball"] = (
        ball["is_legal_ball"] & ball["team_runs_additive_candidate"].eq(0)
    )
    ball["is_bowling_wicket"] = (
        ball["is_wicket"] & ~ball["dismissal_type"].isin(NON_BOWLER_DISMISSALS)
    )
    return ball


def clean_data(data):
    ball = prepare_delivery_fields(data["ball_by_ball"])
    matches = data["matches"].copy()
    competitions = data["competitions"].copy()
    mapping = data["competition_team_player_mapping"].copy()
    eleven = data["playing_eleven"].copy()
    teams = data["teams"].copy()

    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    ball = ball.sort_values(
        ["match_id", "innings", "innings_ball_num"], kind="stable"
    ).reset_index(drop=True)

    context = matches.merge(
        competitions[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    cleaned = {
        "ball_by_ball": ball,
        "competitions": competitions,
        "competition_team_player_mapping": mapping,
        "matches": matches,
        "match_context": context,
        "playing_eleven": eleven,
        "teams": teams,
    }
    return cleaned
