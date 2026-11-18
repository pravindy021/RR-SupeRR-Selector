import numpy as np
import pandas as pd


MATCH_CONTEXT_COLUMNS = [
    "match_id", "comp_id", "comp_name", "match_format", "season",
    "revised_target", "first_inn_revised_overs", "second_inn_revised_overs",
    "home_team_id", "away_team_id", "home_team", "away_team", "result",
]


def _prior_sum(frame, key_columns, value_column):
    return frame.groupby(key_columns, sort=False)[value_column].transform(
        lambda values: values.cumsum().shift(1, fill_value=0)
    )


def add_match_situation(ball, match_context, teams=None):
    context = match_context.copy()
    if "result" not in context:
        context["result"] = np.nan
    context = context[MATCH_CONTEXT_COLUMNS]
    df = ball.merge(
        context,
        on="match_id",
        how="left",
        validate="many_to_one",
        sort=False,
    )
    if df["comp_id"].isna().any():
        missing = df.loc[df["comp_id"].isna(), "match_id"].drop_duplicates().head(5).tolist()
        raise ValueError(f"Delivery rows have no match context; sample match_ids: {missing}")

    df = df.sort_values(
        ["match_id", "innings", "innings_ball_num"], kind="stable"
    ).reset_index(drop=True)
    keys = ["match_id", "innings"]

    df["competition_group"] = np.select(
        [
            df["comp_name"].str.match(r"^IPL(?:\s|$)", case=False, na=False),
            df["match_format"].str.upper().eq("T20I"),
        ],
        ["IPL", "T20I"],
        default="Other T20",
    )

    normal_limit = pd.Series(120, index=df.index, dtype="int64")
    first_revision = df["first_inn_revised_overs"]
    second_revision = df["second_inn_revised_overs"]
    revision = pd.Series(
        np.where(
            df["innings"].eq(1),
            first_revision,
            np.where(df["innings"].eq(2), second_revision, np.nan),
        ),
        index=df.index,
        dtype="float64",
    )
    revised_rows = revision.notna()
    invalid_revision = revised_rows & (
        revision.mod(1).ne(0)
        | revision.mod(6).ne(0)
        | revision.le(0)
        | revision.gt(120)
    )
    if invalid_revision.any():
        bad = revision.loc[invalid_revision].drop_duplicates().tolist()
        raise ValueError(
            "Revised innings limits must be integral whole-over legal-ball counts in [6, 120]; "
            f"unsupported source values: {bad}"
        )
    normal_limit.loc[revised_rows] = revision.loc[revised_rows].astype(int)
    normal_limit.loc[df["innings"].ge(3)] = 6
    df["innings_limit_balls"] = normal_limit
    df["innings_runs_before"] = _prior_sum(
        df, keys, "team_runs_this_delivery"
    )
    df["innings_runs_additive_candidate_before"] = _prior_sum(
        df, keys, "team_runs_additive_candidate"
    )
    df["secondary_extras_before"] = _prior_sum(
        df, keys, "extras_2_runs"
    )
    df["wickets_lost_before"] = _prior_sum(
        df, keys, "is_wicket"
    )
    df["wickets_remaining_before"] = (
        10 - df["wickets_lost_before"]
    ).clip(lower=0).astype(int)
    df["legal_balls_before"] = _prior_sum(
        df, keys, "is_legal_ball"
    ).astype(int)
    df["balls_remaining_before"] = (
        df["innings_limit_balls"] - df["legal_balls_before"]
    ).clip(lower=0)
    df["over_number"] = pd.to_numeric(df["overid"], errors="raise").astype(int)
    df["current_run_rate_before"] = np.where(
        df["legal_balls_before"] > 0,
        df["innings_runs_before"] * 6 / df["legal_balls_before"],
        0.0,
    )
    df["current_run_rate_additive_candidate_before"] = np.where(
        df["legal_balls_before"] > 0,
        df["innings_runs_additive_candidate_before"] * 6 / df["legal_balls_before"],
        0.0,
    )

    innings_totals = (
        df.groupby(["match_id", "innings"], sort=False)["team_runs_this_delivery"]
        .sum()
        .unstack(fill_value=0)
    )
    innings_totals_candidate = (
        df.groupby(["match_id", "innings"], sort=False)["team_runs_additive_candidate"]
        .sum()
        .unstack(fill_value=0)
    )
    first_scores = innings_totals[1] if 1 in innings_totals else pd.Series(dtype=float)
    first_scores_candidate = (
        innings_totals_candidate[1]
        if 1 in innings_totals_candidate
        else pd.Series(dtype=float)
    )
    super_over_scores = innings_totals[3] if 3 in innings_totals else pd.Series(dtype=float)
    super_over_scores_candidate = (
        innings_totals_candidate[3]
        if 3 in innings_totals_candidate
        else pd.Series(dtype=float)
    )
    df["first_innings_score"] = df["match_id"].map(first_scores)
    df["first_innings_score_additive_candidate"] = df["match_id"].map(
        first_scores_candidate
    )
    df["super_over_first_score"] = df["match_id"].map(super_over_scores)
    df["super_over_first_score_additive_candidate"] = df["match_id"].map(
        super_over_scores_candidate
    )
    normal_chase = df["innings"].eq(2)
    super_over_chase = df["innings"].eq(4)
    target = np.where(
        normal_chase,
        df["revised_target"],
        np.nan,
    )
    target = np.where(
        normal_chase & pd.isna(target),
        df["first_innings_score"] + 1,
        target,
    )
    target = np.where(
        super_over_chase,
        df["super_over_first_score"] + 1,
        target,
    )
    target_candidate = np.where(
        normal_chase,
        df["revised_target"],
        np.nan,
    )
    target_candidate = np.where(
        normal_chase & pd.isna(target_candidate),
        df["first_innings_score_additive_candidate"] + 1,
        target_candidate,
    )
    target_candidate = np.where(
        super_over_chase,
        df["super_over_first_score_additive_candidate"] + 1,
        target_candidate,
    )
    df["target"] = target
    df["target_additive_candidate"] = target_candidate
    df["runs_required_before"] = (
        df["target"] - df["innings_runs_before"]
    ).clip(lower=0)
    df["runs_required_additive_candidate_before"] = (
        df["target_additive_candidate"]
        - df["innings_runs_additive_candidate_before"]
    ).clip(lower=0)
    df["required_run_rate_before"] = np.where(
        df["balls_remaining_before"] > 0,
        df["runs_required_before"] * 6 / df["balls_remaining_before"],
        np.where(df["runs_required_before"] > 0, np.inf, 0.0),
    )
    df["required_run_rate_additive_candidate_before"] = np.where(
        df["balls_remaining_before"] > 0,
        df["runs_required_additive_candidate_before"] * 6 / df["balls_remaining_before"],
        np.where(df["runs_required_additive_candidate_before"] > 0, np.inf, 0.0),
    )

    secondary_totals = (
        df.groupby(["match_id", "innings"], sort=False)["extras_2_runs"]
        .sum()
        .unstack(fill_value=0)
    )
    first_secondary = (
        secondary_totals[1] if 1 in secondary_totals else pd.Series(dtype=float)
    )
    super_over_secondary = (
        secondary_totals[3] if 3 in secondary_totals else pd.Series(dtype=float)
    )
    first_secondary_by_match = df["match_id"].map(first_secondary).fillna(0)
    super_secondary_by_match = df["match_id"].map(super_over_secondary).fillna(0)
    inherited_uncertainty = np.where(
        normal_chase & df["revised_target"].isna(),
        first_secondary_by_match.gt(0),
        np.where(super_over_chase, super_secondary_by_match.gt(0), False),
    )
    df["match_state_secondary_extras_uncertain"] = (
        df["secondary_extras_before"].gt(0) | inherited_uncertainty
    )

    legal_after = df["legal_balls_before"] + df["is_legal_ball"].astype(int)
    wickets_after = df["wickets_lost_before"] + df["is_wicket"].astype(int)
    runs_after = df["innings_runs_before"] + df["team_runs_this_delivery"]
    df["balls_remaining_after"] = (
        df["innings_limit_balls"] - legal_after
    ).clip(lower=0)

    reached_target = (
        df["target"].notna()
        & runs_after.ge(df["target"])
    )
    terminal = (
        legal_after.ge(df["innings_limit_balls"])
        | wickets_after.ge(10)
        | reached_target
    )
    df["_terminal_reason"] = np.select(
        [
            wickets_after.ge(10),
            reached_target,
            legal_after.ge(df["innings_limit_balls"]),
        ],
        ["all_out", "target_reached", "scheduled_balls_completed"],
        default="",
    )
    terminal_reason = df["_terminal_reason"].where(terminal, "").groupby(
        [df[c] for c in keys], sort=False
    ).agg(lambda values: next((value for value in values if value), ""))
    terminal_reason.index = pd.MultiIndex.from_tuples(
        terminal_reason.index, names=keys
    )
    df["innings_completion_status"] = [
        terminal_reason.get((match_id, innings), "") or "incomplete_or_interrupted"
        for match_id, innings in zip(df["match_id"], df["innings"])
    ]
    df = df.drop(columns="_terminal_reason")

    if teams is not None:
        team_lookup = teams.rename(
            columns={"team_id": "batting_team_id", "team_name": "batting_team_name"}
        )
        df = df.merge(
            team_lookup[["comp_id", "batting_team_id", "batting_team_name"]],
            on=["comp_id", "batting_team_id"],
            how="left",
            validate="many_to_one",
        )
        bowling_lookup = teams.rename(
            columns={"team_id": "bowling_team_id", "team_name": "bowling_team_name"}
        )
        df = df.merge(
            bowling_lookup[["comp_id", "bowling_team_id", "bowling_team_name"]],
            on=["comp_id", "bowling_team_id"],
            how="left",
            validate="many_to_one",
        )
    else:
        df["batting_team_name"] = np.where(
            df["batting_team_id"].eq(df["home_team_id"]),
            df["home_team"],
            df["away_team"],
        )
        df["bowling_team_name"] = np.where(
            df["bowling_team_id"].eq(df["home_team_id"]),
            df["home_team"],
            df["away_team"],
        )
    return df
