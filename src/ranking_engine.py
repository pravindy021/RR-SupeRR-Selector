import numpy as np
import pandas as pd


CONTEXT_WEIGHTS = {"IPL": 0.70, "T20I": 0.30}
SCENARIOS = {
    "primary": 0.75,
    "performance_heavy": 0.85,
    "consistency_heavy": 0.60,
}
BATTER_DIMENSION_WEIGHTS = {
    "pressure_strike_rate": 0.35,
    "boundary_pct": 0.20,
    "dot_ball_avoidance_pct": 0.20,
    "dismissal_avoidance_pct": 0.25,
}
BOWLER_DIMENSION_WEIGHTS = {
    "pressure_economy_known": 0.40,
    "wicket_rate_per_6": 0.35,
    "dot_ball_pct": 0.25,
}
MIN_PRESSURE_BALLS = {"Batter": 30, "Bowler": 24}
MIN_PRESSURE_MATCHES = 4
BALL_PRIOR_STRENGTH = 60.0
MATCH_PRIOR_STRENGTH = 4.0


def batting_summary(deliveries, player_id):
    faced = deliveries[
        deliveries["striker_id"].eq(player_id)
        & deliveries["is_batter_ball_faced"]
    ]
    runs = float(faced["runs"].sum())
    dismissals = int(
        (
            deliveries["is_wicket"].astype(bool)
            & deliveries["dismissed_player_id"].eq(player_id)
        ).sum()
    )
    balls = int(len(faced))
    return {
        "balls_faced": balls,
        "runs": runs,
        "dismissals": dismissals,
        "strike_rate": runs * 100 / balls if balls else np.nan,
    }


def bowling_summary(deliveries):
    legal_balls = int(deliveries["is_legal_ball"].sum())
    runs_known = float(deliveries["bowler_conceded_runs_known"].sum())
    return {
        "legal_balls": legal_balls,
        "runs_conceded_known": runs_known,
        "unallocated_runs": float(deliveries["bowler_runs_unallocated"].sum()),
        "wickets": int(deliveries["is_bowling_wicket"].sum()),
        "economy_known": runs_known * 6 / legal_balls if legal_balls else np.nan,
    }


def consistency_from_matches(values, higher_is_better=True):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return 0.0
    mean = abs(float(values.mean()))
    if mean == 0:
        return 0.0
    coefficient_of_variation = float(values.std(ddof=0)) / mean
    return float(1 / (1 + coefficient_of_variation))


def _batter_appearance_rows(pressure):
    striker = pressure.copy()
    striker["player_id"] = striker["striker_id"]
    striker["player_name"] = striker["striker_name"]
    non_striker = pressure.copy()
    non_striker["player_id"] = non_striker["non_striker_id"]
    non_striker["player_name"] = non_striker["non_striker_name"]
    rows = pd.concat([striker, non_striker], ignore_index=True)
    return rows.drop_duplicates(
        ["match_id", "innings", "innings_ball_num", "player_id"]
    )


def _context_player_metrics(frame, role):
    pressure = frame[
        frame["is_pressure"]
        & frame["competition_group"].isin(CONTEXT_WEIGHTS)
    ].copy()
    metrics = []

    if role == "Batter":
        appearances = _batter_appearance_rows(pressure)
        group_columns = ["player_id", "player_name", "competition_group"]
        for (player_id, player_name, context), group in appearances.groupby(
            group_columns, sort=False, dropna=False
        ):
            faced = group[
                group["striker_id"].eq(player_id)
                & group["is_batter_ball_faced"]
            ]
            batter_metrics = batting_summary(group, player_id)
            balls = batter_metrics["balls_faced"]
            runs = batter_metrics["runs"]
            pressure_innings = group[["match_id", "innings"]].drop_duplicates().shape[0]
            dismissals = batter_metrics["dismissals"]
            match_srs = faced.groupby("match_id").apply(
                lambda values: values["runs"].sum() * 100 / len(values),
                include_groups=False,
            ).to_numpy()
            match_count = group["match_id"].nunique()
            team_context = sorted(
                group["batting_team_name"].dropna().astype(str).unique()
            )
            competitions = sorted(group["comp_name"].dropna().astype(str).unique())
            metrics.append({
                "role": role,
                "player_id": int(player_id),
                "player_name": player_name,
                "competition_group": context,
                "team_context": "; ".join(team_context),
                "competition_context": "; ".join(competitions),
                "pressure_matches": int(match_count),
                "pressure_innings": int(pressure_innings),
                "pressure_balls": int(balls),
                "pressure_runs": int(runs),
                "pressure_boundary_count": int(
                    faced["is_four"].sum() + faced["is_six"].sum()
                ),
                "pressure_dot_balls": int(faced["is_batter_dot_ball"].sum()),
                "pressure_strike_rate": runs * 100 / balls if balls else np.nan,
                "boundary_pct": (
                    100 * (faced["is_four"].sum() + faced["is_six"].sum()) / balls
                    if balls else np.nan
                ),
                "dot_ball_pct": (
                    100 * faced["is_batter_dot_ball"].sum() / balls
                    if balls else np.nan
                ),
                "dismissals": dismissals,
                "dismissal_avoidance_pct": (
                    100 * max(pressure_innings - dismissals, 0) / pressure_innings
                    if pressure_innings else np.nan
                ),
                "consistency_score": consistency_from_matches(match_srs),
                "runs_per_dismissal": runs / dismissals if dismissals else np.nan,
                "normal_strike_rate": np.nan,
                "unallocated_bowler_runs": 0,
            })
            normal = frame[
                (~frame["is_pressure"])
                & frame["competition_group"].eq(context)
                & frame["striker_id"].eq(player_id)
                & frame["is_batter_ball_faced"]
            ]
            metrics[-1]["normal_strike_rate"] = (
                normal["runs"].sum() * 100 / len(normal) if len(normal) else np.nan
            )
    else:
        group_columns = ["bowler_id", "bowler_name", "competition_group"]
        for (player_id, player_name, context), group in pressure.groupby(
            group_columns, sort=False, dropna=False
        ):
            legal = group[group["is_legal_ball"]]
            bowling_metrics = bowling_summary(group)
            balls = bowling_metrics["legal_balls"]
            known_runs = bowling_metrics["runs_conceded_known"]
            unallocated = bowling_metrics["unallocated_runs"]
            wickets = bowling_metrics["wickets"]
            economy = bowling_metrics["economy_known"]
            match_economies = group.groupby("match_id").apply(
                lambda values: (
                    values["bowler_conceded_runs_known"].sum() * 6
                    / values["is_legal_ball"].sum()
                    if values["is_legal_ball"].sum() else np.nan
                ),
                include_groups=False,
            ).to_numpy()
            team_context = sorted(
                group["bowling_team_name"].dropna().astype(str).unique()
            )
            competitions = sorted(group["comp_name"].dropna().astype(str).unique())
            metrics.append({
                "role": role,
                "player_id": int(player_id),
                "player_name": player_name,
                "competition_group": context,
                "team_context": "; ".join(team_context),
                "competition_context": "; ".join(competitions),
                "pressure_matches": int(group["match_id"].nunique()),
                "pressure_innings": int(group[["match_id", "innings"]].drop_duplicates().shape[0]),
                "pressure_legal_balls": int(balls),
                "pressure_runs_conceded_known": int(known_runs),
                "unallocated_pressure_extras": int(unallocated),
                "pressure_dot_balls": int(legal["is_bowler_dot_ball"].sum()),
                "wickets": wickets,
                "pressure_economy_known": economy,
                "wicket_rate_per_6": wickets * 6 / balls if balls else np.nan,
                "dot_ball_pct": (
                    100 * legal["is_bowler_dot_ball"].sum() / balls
                    if balls else np.nan
                ),
                "consistency_score": consistency_from_matches(match_economies),
                "normal_economy_known": np.nan,
            })
            normal = frame[
                (~frame["is_pressure"])
                & frame["competition_group"].eq(context)
                & frame["bowler_id"].eq(player_id)
            ]
            normal_legal_balls = int(normal["is_legal_ball"].sum())
            metrics[-1]["normal_economy_known"] = (
                normal["bowler_conceded_runs_known"].sum() * 6 / normal_legal_balls
                if normal_legal_balls else np.nan
            )

    return pd.DataFrame(metrics)


def _shrink_to_peer_mean(values, counts, prior_strength):
    values = pd.to_numeric(values, errors="coerce")
    counts = pd.to_numeric(counts, errors="coerce").fillna(0)
    prior = values.median()
    if pd.isna(prior):
        return values
    weight = counts / (counts + prior_strength)
    return values * weight + prior * (1 - weight)


def _percentile(values, higher_is_better=True):
    ranked = values.rank(method="average", pct=True)
    return ranked if higher_is_better else 1 - ranked


def _score_contexts(context_metrics, role):
    scored = context_metrics.copy()
    for context, indexes in scored.groupby("competition_group").groups.items():
        section = scored.loc[indexes]
        if role == "Batter":
            dimensions = [
                ("pressure_strike_rate", "pressure_balls", True,
                 BATTER_DIMENSION_WEIGHTS["pressure_strike_rate"]),
                ("boundary_pct", "pressure_balls", True,
                 BATTER_DIMENSION_WEIGHTS["boundary_pct"]),
                ("dot_ball_pct", "pressure_balls", False,
                 BATTER_DIMENSION_WEIGHTS["dot_ball_avoidance_pct"]),
                ("dismissal_avoidance_pct", "pressure_innings", True,
                 BATTER_DIMENSION_WEIGHTS["dismissal_avoidance_pct"]),
            ]
        else:
            dimensions = [
                ("pressure_economy_known", "pressure_legal_balls", False,
                 BOWLER_DIMENSION_WEIGHTS["pressure_economy_known"]),
                ("wicket_rate_per_6", "pressure_legal_balls", True,
                 BOWLER_DIMENSION_WEIGHTS["wicket_rate_per_6"]),
                ("dot_ball_pct", "pressure_legal_balls", True,
                 BOWLER_DIMENSION_WEIGHTS["dot_ball_pct"]),
            ]

        component_columns = []
        for metric, count_column, higher, weight in dimensions:
            prior_strength = (
                MATCH_PRIOR_STRENGTH
                if count_column == "pressure_innings"
                else BALL_PRIOR_STRENGTH
            )
            shrunk = _shrink_to_peer_mean(
                section[metric], section[count_column], prior_strength
            )
            component = _percentile(shrunk, higher)
            component_name = f"component_{metric}"
            scored.loc[indexes, component_name] = component.to_numpy()
            component_columns.append((component_name, weight))
        performance = sum(
            scored.loc[indexes, column] * weight
            for column, weight in component_columns
        )
        confidence = section["pressure_matches"] / (
            section["pressure_matches"] + MATCH_PRIOR_STRENGTH
        )
        adjusted_performance = confidence * performance + (1 - confidence) * 0.5
        scored.loc[indexes, "performance_score"] = performance.to_numpy()
        scored.loc[indexes, "sample_confidence"] = confidence.to_numpy()
        scored.loc[indexes, "reliability_score"] = adjusted_performance.to_numpy()
    return scored


def _combine_context_scores(scored, performance_weight):
    frame = scored.copy()
    frame["scenario_context_score"] = (
        performance_weight * frame["reliability_score"]
        + (1 - performance_weight) * frame["consistency_score"]
    )
    frame["context_weight"] = frame["competition_group"].map(CONTEXT_WEIGHTS)
    frame["weighted_score"] = frame["scenario_context_score"] * frame["context_weight"]
    for metric in ("performance_score", "reliability_score", "consistency_score", "sample_confidence"):
        frame[f"weighted_{metric}"] = frame[metric] * frame["context_weight"]
    totals = frame.groupby(["player_id", "player_name"], as_index=False).agg(
        weighted_score=("weighted_score", "sum"),
        available_context_weight=("context_weight", "sum"),
        weighted_performance_score=("weighted_performance_score", "sum"),
        weighted_reliability_score=("weighted_reliability_score", "sum"),
        weighted_consistency_score=("weighted_consistency_score", "sum"),
        weighted_sample_confidence=("weighted_sample_confidence", "sum"),
    )
    missing_context_weight = 1 - totals["available_context_weight"]
    totals["scenario_score"] = (
        totals["weighted_score"] + 0.5 * missing_context_weight
    )
    for metric in ("performance_score", "reliability_score", "consistency_score", "sample_confidence"):
        totals[metric] = (
            totals[f"weighted_{metric}"] + 0.5 * missing_context_weight
        )
    return totals


def _rank_scored_contexts(context_metrics, role, performance_weight):
    scored = _score_contexts(context_metrics, role)
    overall = _combine_context_scores(scored, performance_weight)

    if role == "Batter":
        count_column = "pressure_balls"
        total_column = "pressure_runs"
    else:
        count_column = "pressure_legal_balls"
        total_column = "wickets"
    aggregate_spec = {
        "total_pressure_matches": ("pressure_matches", "sum"),
        "total_pressure_balls": (count_column, "sum"),
        "total_count": (total_column, "sum"),
        "team_context": ("team_context", lambda values: "; ".join(sorted(set(
            item for value in values for item in value.split("; ") if item
        )))),
        "competition_context": ("competition_context", lambda values: "; ".join(sorted(set(
            item for value in values for item in value.split("; ") if item
        )))),
    }
    if role == "Batter":
        aggregate_spec.update({
            "pressure_boundary_count": ("pressure_boundary_count", "sum"),
            "pressure_dot_balls": ("pressure_dot_balls", "sum"),
        })
    else:
        aggregate_spec.update({
            "pressure_runs_conceded_known": ("pressure_runs_conceded_known", "sum"),
            "unallocated_pressure_extras": ("unallocated_pressure_extras", "sum"),
            "pressure_dot_balls": ("pressure_dot_balls", "sum"),
        })
    totals = context_metrics.groupby(
        ["player_id", "player_name"], as_index=False
    ).agg(**aggregate_spec)
    if role == "Batter":
        aggregate_dismissals = context_metrics.groupby(
            ["player_id", "player_name"], as_index=False
        ).agg(dismissals=("dismissals", "sum"))
        totals = totals.merge(
            aggregate_dismissals, on=["player_id", "player_name"], validate="one_to_one"
        )
        totals["pressure_strike_rate"] = (
            100 * totals["total_count"] / totals["total_pressure_balls"]
        )
        totals["boundary_pct"] = (
            100 * totals["pressure_boundary_count"] / totals["total_pressure_balls"]
        )
        totals["dot_ball_pct"] = (
            100 * totals["pressure_dot_balls"] / totals["total_pressure_balls"]
        )
        totals["runs_per_dismissal"] = np.where(
            totals["dismissals"].gt(0),
            totals["total_count"] / totals["dismissals"],
            np.nan,
        )
    else:
        totals["pressure_economy_known"] = (
            6 * totals["pressure_runs_conceded_known"] / totals["total_pressure_balls"]
        )
        totals["dot_ball_pct"] = (
            100 * totals["pressure_dot_balls"] / totals["total_pressure_balls"]
        )
        totals["wicket_rate_per_6"] = (
            6 * totals["total_count"] / totals["total_pressure_balls"]
        )

    for context in CONTEXT_WEIGHTS:
        part = scored[scored["competition_group"].eq(context)].copy()
        if part.empty:
            continue
        part = part.rename(columns={
            "pressure_matches": f"{context.lower()}_pressure_matches",
            "pressure_strike_rate": f"{context.lower()}_pressure_strike_rate",
            "pressure_economy_known": f"{context.lower()}_pressure_economy_known",
            "pressure_legal_balls": f"{context.lower()}_pressure_legal_balls",
            "pressure_balls": f"{context.lower()}_pressure_balls",
            "pressure_runs": f"{context.lower()}_pressure_runs",
            "pressure_runs_conceded_known": f"{context.lower()}_pressure_runs_conceded_known",
            "wickets": f"{context.lower()}_wickets",
            "performance_score": f"{context.lower()}_performance_score",
            "consistency_score": f"{context.lower()}_consistency_score",
            "reliability_score": f"{context.lower()}_reliability_score",
            "normal_strike_rate": f"{context.lower()}_normal_strike_rate",
            "normal_economy_known": f"{context.lower()}_normal_economy_known",
        })
        include_columns = ["player_id", "player_name"] + [
            column for column in part.columns
            if column.startswith(f"{context.lower()}_")
        ]
        totals = totals.merge(
            part[include_columns],
            on=["player_id", "player_name"],
            how="left",
            validate="one_to_one",
        )

    totals = totals.merge(overall, on=["player_id", "player_name"], validate="one_to_one")
    eligible = totals[
        totals["total_pressure_balls"].ge(MIN_PRESSURE_BALLS[role])
        & totals["total_pressure_matches"].ge(MIN_PRESSURE_MATCHES)
    ].copy()
    eligible = eligible.sort_values(
        ["scenario_score", "total_pressure_balls", "player_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    eligible.insert(0, "rank", np.arange(1, len(eligible) + 1))
    eligible = eligible.rename(columns={
        "total_pressure_matches": "pressure_opportunities",
        "total_pressure_balls": (
            "pressure_balls" if role == "Batter" else "pressure_legal_balls"
        ),
        "total_count": "pressure_runs" if role == "Batter" else "wickets",
        "scenario_score": "final_composite_score",
    })
    return eligible, scored


def rank_players(frame, role, performance_weight=SCENARIOS["primary"]):
    context_metrics = _context_player_metrics(frame, role)
    if context_metrics.empty:
        return pd.DataFrame(), context_metrics
    return _rank_scored_contexts(context_metrics, role, performance_weight)


def rank_scored_by_context(scored, role, context):
    if context not in CONTEXT_WEIGHTS:
        raise ValueError(f"Unknown ranking context: {context}")
    ranked = scored[scored["competition_group"].eq(context)].copy()
    if ranked.empty:
        return ranked

    sample_column = (
        "pressure_balls" if role == "Batter" else "pressure_legal_balls"
    )
    ranked = ranked[
        ranked[sample_column].ge(MIN_PRESSURE_BALLS[role])
        & ranked["pressure_matches"].ge(MIN_PRESSURE_MATCHES)
    ].copy()
    if ranked.empty:
        return ranked

    performance_weight = SCENARIOS["primary"]
    ranked["final_composite_score"] = (
        performance_weight * ranked["reliability_score"]
        + (1 - performance_weight) * ranked["consistency_score"]
    )
    ranked = ranked.sort_values(
        ["final_composite_score", sample_column, "player_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1))
    ranked = ranked.rename(columns={"pressure_matches": "pressure_opportunities"})
    return ranked


def rank_players_by_context(frame, role, context):
    if context not in CONTEXT_WEIGHTS:
        raise ValueError(f"Unknown ranking context: {context}")
    context_metrics = _context_player_metrics(frame, role)
    if context_metrics.empty:
        return pd.DataFrame()
    return rank_scored_by_context(
        _score_contexts(context_metrics, role), role, context
    )


def sensitivity_analysis(frame, role, primary_rankings):
    primary_top = set(primary_rankings.head(10)["player_id"])
    context_metrics = _context_player_metrics(frame, role)
    rows = []
    scenario_rankings = {}
    scored = _score_contexts(context_metrics, role)
    for scenario, performance_weight in SCENARIOS.items():
        ranked, _ = _rank_scored_contexts(
            context_metrics, role, performance_weight
        )
        scenario_rankings[scenario] = ranked
        top = set(ranked.head(10)["player_id"])
        overlap = len(primary_top & top)
        rows.append({
            "role": role,
            "scenario": scenario,
            "performance_weight": performance_weight,
            "consistency_weight": 1 - performance_weight,
            "primary_top_10_overlap_count": overlap,
            "primary_top_10_overlap_rate": overlap / max(len(primary_top), 1),
            "top_10_player_ids": ";".join(str(value) for value in ranked.head(10)["player_id"]),
        })
    return pd.DataFrame(rows), scenario_rankings
