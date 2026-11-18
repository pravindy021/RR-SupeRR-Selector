import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ranking_engine import (
    SCENARIOS,
    _combine_context_scores,
    _score_contexts,
    consistency_from_matches,
    rank_players,
    rank_players_by_context,
    rank_scored_by_context,
    sensitivity_analysis,
)


def _small_batter_frame():
    rows = []
    for player_id in range(1, 12):
        for match_offset in range(4):
            for ball in range(8):
                if player_id == 1:
                    runs = 3
                elif player_id == 2:
                    runs = 0 if match_offset % 2 == 0 else 6
                else:
                    runs = (player_id + match_offset + ball) % 7
                wicket = ball == 7 and player_id in (2, 4, 6)
                rows.append({
                    "match_id": 100 + match_offset,
                    "innings": 2,
                    "innings_ball_num": ball + 1,
                    "competition_group": "IPL",
                    "comp_name": "IPL 2024",
                    "match_format": "T20",
                    "is_pressure": True,
                    "striker_id": player_id,
                    "striker_name": f"Player {player_id}",
                    "non_striker_id": 100 + player_id,
                    "non_striker_name": f"Partner {player_id}",
                    "is_batter_ball_faced": True,
                    "is_batter_dot_ball": runs == 0,
                    "runs": runs,
                    "is_four": runs == 4,
                    "is_six": runs == 6,
                    "is_wicket": wicket,
                    "dismissed_player_id": player_id if wicket else None,
                    "bowling_team_name": "Opponent",
                    "batting_team_name": "Team A",
                })
    return pd.DataFrame(rows)


def _small_bowler_frame():
    rows = []
    for player_id in range(1, 12):
        for match_offset in range(4):
            for ball in range(8):
                runs = 0 if player_id == 1 else (player_id + ball) % 4
                rows.append({
                    "match_id": 300 + match_offset,
                    "innings": 2,
                    "competition_group": "IPL",
                    "comp_name": "IPL 2024",
                    "match_format": "T20",
                    "is_pressure": True,
                    "bowler_id": player_id,
                    "bowler_name": f"Bowler {player_id}",
                    "is_legal_ball": True,
                    "bowler_conceded_runs_known": runs,
                    "bowler_runs_unallocated": 0,
                    "is_bowling_wicket": ball == 7 and player_id in (2, 4, 6),
                    "is_bowler_dot_ball": runs == 0,
                    "bowling_team_name": "Team A",
                })
    return pd.DataFrame(rows)


def test_context_weights_are_applied_and_missing_context_is_neutral():
    contexts = pd.DataFrame([
        {
            "player_id": 1, "player_name": "A", "competition_group": "IPL",
            "reliability_score": 0.8, "consistency_score": 0.6,
            "performance_score": 0.8, "sample_confidence": 0.5,
        },
        {
            "player_id": 1, "player_name": "A", "competition_group": "T20I",
            "reliability_score": 0.2, "consistency_score": 0.4,
            "performance_score": 0.2, "sample_confidence": 0.5,
        },
    ])
    combined = _combine_context_scores(contexts, SCENARIOS["primary"]).iloc[0]
    expected_ipl = 0.75 * 0.8 + 0.25 * 0.6
    expected_t20i = 0.75 * 0.2 + 0.25 * 0.4
    assert abs(combined["scenario_score"] - (0.7 * expected_ipl + 0.3 * expected_t20i)) < 1e-12

    only_ipl = _combine_context_scores(contexts.iloc[[0]], SCENARIOS["primary"]).iloc[0]
    assert abs(only_ipl["scenario_score"] - (0.7 * expected_ipl + 0.3 * 0.5)) < 1e-12
    assert only_ipl["available_context_weight"] == 0.7


def test_metric_shrinkage_percentiles_reliability_and_consistency_formula():
    metrics = pd.DataFrame([
        {
            "player_id": 1, "player_name": "A", "competition_group": "IPL",
            "pressure_strike_rate": 100, "boundary_pct": 10, "dot_ball_pct": 20,
            "dismissal_avoidance_pct": 50, "pressure_balls": 60,
            "pressure_innings": 4, "pressure_matches": 4, "consistency_score": 0.6,
        },
        {
            "player_id": 2, "player_name": "B", "competition_group": "IPL",
            "pressure_strike_rate": 200, "boundary_pct": 20, "dot_ball_pct": 40,
            "dismissal_avoidance_pct": 100, "pressure_balls": 60,
            "pressure_innings": 4, "pressure_matches": 4, "consistency_score": 0.4,
        },
    ])
    scored = _score_contexts(metrics, "Batter").set_index("player_id")
    assert scored.loc[1, "component_pressure_strike_rate"] == 0.5
    assert scored.loc[2, "component_pressure_strike_rate"] == 1
    assert scored.loc[1, "component_dot_ball_pct"] == 0.5
    assert scored.loc[2, "component_dot_ball_pct"] == 0
    assert scored.loc[1, "performance_score"] == 0.5
    assert scored.loc[2, "performance_score"] == 0.8
    assert scored.loc[1, "reliability_score"] == 0.5
    assert scored.loc[2, "reliability_score"] == 0.65
    ranked = rank_scored_by_context(
        scored.reset_index(), "Batter", "IPL"
    )
    assert ranked["player_id"].tolist() == [2, 1]
    assert ranked["final_composite_score"].tolist() == [0.5875, 0.525]
    assert consistency_from_matches([1, 3]) == 2 / 3
    assert consistency_from_matches([4, 4]) == 1
    assert consistency_from_matches([0, 0]) == 0
    assert consistency_from_matches([4]) == 0


def test_rankings_are_reproducible_and_require_minimum_sample():
    frame = _small_batter_frame()
    first, _ = rank_players(frame, "Batter")
    second, _ = rank_players(frame, "Batter")
    assert first["player_id"].tolist() == second["player_id"].tolist()
    assert first["final_composite_score"].tolist() == second["final_composite_score"].tolist()
    assert first["pressure_balls"].ge(30).all()
    assert first["pressure_opportunities"].ge(4).all()
    assert first["rank"].tolist() == list(range(1, len(first) + 1))


def test_context_rankings_are_independent_and_use_context_score_formula():
    ipl_frame = _small_batter_frame()
    t20i_frame = ipl_frame.copy()
    t20i_frame["competition_group"] = "T20I"
    t20i_frame["comp_name"] = "T20I 2024"
    t20i_frame["match_id"] += 1000
    strongest = t20i_frame["striker_id"].eq(11)
    weakest = t20i_frame["striker_id"].eq(1)
    t20i_frame.loc[strongest, ["runs", "is_four", "is_six", "is_batter_dot_ball"]] = [
        6, False, True, False
    ]
    t20i_frame.loc[weakest, ["runs", "is_four", "is_six", "is_batter_dot_ball"]] = [
        0, False, False, True
    ]
    frame = pd.concat([ipl_frame, t20i_frame], ignore_index=True)

    ipl, _ = rank_players(frame, "Batter")
    ipl_top = rank_players_by_context(frame, "Batter", "IPL")
    t20i_top = rank_players_by_context(frame, "Batter", "T20I")

    assert ipl_top["rank"].tolist() == list(range(1, len(ipl_top) + 1))
    assert t20i_top["rank"].tolist() == list(range(1, len(t20i_top) + 1))
    assert ipl_top["competition_group"].eq("IPL").all()
    assert t20i_top["competition_group"].eq("T20I").all()
    assert ipl_top["pressure_balls"].ge(30).all()
    assert t20i_top["pressure_balls"].ge(30).all()
    assert ipl_top["pressure_opportunities"].ge(4).all()
    assert t20i_top["pressure_opportunities"].ge(4).all()
    assert ipl_top.iloc[0]["player_id"] != t20i_top.iloc[0]["player_id"]
    expected = (
        SCENARIOS["primary"] * t20i_top.iloc[0]["reliability_score"]
        + (1 - SCENARIOS["primary"]) * t20i_top.iloc[0]["consistency_score"]
    )
    assert abs(t20i_top.iloc[0]["final_composite_score"] - expected) < 1e-12


def test_all_exported_composite_scores_match_context_formula_and_top_ten():
    for role in ("batters", "bowlers"):
        rankings_dir = ROOT / "outputs" / "rankings"
        all_ranked = pd.read_csv(rankings_dir / f"all_eligible_{role}.csv")
        top_ten = pd.read_csv(rankings_dir / f"top_10_{role}.csv")
        pd.testing.assert_frame_equal(
            top_ten,
            all_ranked.head(10)[top_ten.columns],
            check_dtype=False,
        )
        ipl_score = (
            0.75 * all_ranked["ipl_reliability_score"]
            + 0.25 * all_ranked["ipl_consistency_score"]
        )
        t20i_score = (
            0.75 * all_ranked["t20i_reliability_score"]
            + 0.25 * all_ranked["t20i_consistency_score"]
        )
        expected = 0.70 * ipl_score.fillna(0.5) + 0.30 * t20i_score.fillna(0.5)
        assert expected.between(0, 1).all()
        assert (expected - all_ranked["final_composite_score"]).abs().max() < 1e-12

        sample_column = "pressure_balls" if role == "batters" else "pressure_legal_balls"
        min_balls = 30 if role == "batters" else 24
        for context in ("ipl", "t20i"):
            matches_column = f"{context}_pressure_matches"
            balls_column = f"{context}_{sample_column}"
            reliability = all_ranked[f"{context}_reliability_score"]
            consistency = all_ranked[f"{context}_consistency_score"]
            context_score = 0.75 * reliability + 0.25 * consistency
            eligible = all_ranked[
                all_ranked[matches_column].ge(4)
                & all_ranked[balls_column].ge(min_balls)
            ].copy()
            eligible["expected_context_score"] = context_score.loc[eligible.index]
            eligible = eligible.sort_values(
                ["expected_context_score", balls_column, "player_name"],
                ascending=[False, False, True],
            ).head(10)
            exported = pd.read_csv(
                rankings_dir / f"top_10_{role}_{context}.csv"
            )
            assert exported["player_id"].tolist() == eligible["player_id"].tolist()
            assert exported["competition_group"].eq(context.upper()).all()
            assert (
                exported["final_composite_score"].to_numpy()
                - eligible["expected_context_score"].to_numpy()
            ).__abs__().max() < 1e-12


def test_sensitivity_overlap_is_calculated_from_alternative_rankings():
    frame = _small_batter_frame()
    primary, _ = rank_players(frame, "Batter")
    sensitivity, alternatives = sensitivity_analysis(frame, "Batter", primary)
    primary_top = set(primary.head(10)["player_id"])
    assert set(sensitivity["scenario"]) == set(SCENARIOS)
    assert len(alternatives) == len(SCENARIOS)
    assert sensitivity.loc[
        sensitivity["scenario"].eq("primary"), "primary_top_10_overlap_count"
    ].item() == 10
    for _, row in sensitivity.iterrows():
        alt_top = set(alternatives[row["scenario"]].head(10)["player_id"])
        expected = len(primary_top & alt_top)
        assert row["primary_top_10_overlap_count"] == expected
        assert row["primary_top_10_overlap_rate"] == expected / 10


def test_bowler_ranking_uses_legal_ball_economy_and_dot_rate_exactly():
    rankings, _ = rank_players(_small_bowler_frame(), "Bowler")
    bowler = rankings.loc[rankings["player_id"].eq(1)].iloc[0]
    assert bowler["pressure_opportunities"] == 4
    assert bowler["pressure_legal_balls"] == 32
    assert bowler["pressure_runs_conceded_known"] == 0
    assert bowler["pressure_economy_known"] == 0
    assert bowler["pressure_dot_balls"] == 32
    assert bowler["dot_ball_pct"] == 100
    assert bowler["wickets"] == 0
    wicket_taker = rankings.loc[rankings["player_id"].eq(2)].iloc[0]
    assert wicket_taker["wickets"] == 4
    assert wicket_taker["pressure_legal_balls"] == 32
    assert wicket_taker["wicket_rate_per_6"] == 0.75


def test_other_competitions_do_not_change_combined_rankings():
    frame = _small_batter_frame()
    baseline, _ = rank_players(frame, "Batter")
    other = frame.copy()
    other["competition_group"] = "Other T20"
    other["comp_name"] = "Other T20 2024"
    other["match_id"] += 1000
    other["runs"] = 6
    other["is_four"] = False
    other["is_six"] = True
    combined, _ = rank_players(pd.concat([frame, other], ignore_index=True), "Batter")
    assert combined["player_id"].tolist() == baseline["player_id"].tolist()
    assert combined["final_composite_score"].tolist() == baseline["final_composite_score"].tolist()


def test_exported_top_twenty_identities_match_source_map_and_deliveries():
    mapping = pd.read_csv(
        ROOT / "data" / "RR_DATASETS" / "Data Pack" / "competition_team_player_mapping.csv"
    )
    deliveries = pd.read_csv(
        ROOT / "data" / "RR_DATASETS" / "Data Pack" / "ball_by_ball.csv",
        low_memory=False,
    )
    for role in ("batters", "bowlers"):
        ranking_files = [
            f"top_10_{role}.csv",
            f"top_10_{role}_ipl.csv",
            f"top_10_{role}_t20i.csv",
        ]
        for ranking_file in ranking_files:
            rankings = pd.read_csv(ROOT / "outputs" / "rankings" / ranking_file)
            for row in rankings.itertuples(index=False):
                assert row.player_name in set(
                    mapping.loc[mapping["player_id"].eq(row.player_id), "player_name"]
                )
                player_id = row.player_id
                source_names = pd.concat([
                    deliveries.loc[
                        deliveries["striker_id"].eq(player_id), "striker_name"
                    ],
                    deliveries.loc[
                        deliveries["non_striker_id"].eq(player_id), "non_striker_name"
                    ],
                    deliveries.loc[
                        deliveries["bowler_id"].eq(player_id), "bowler_name"
                    ],
                ]).dropna()
                assert row.player_name in set(source_names)


def test_real_suryakumar_and_buttler_dismissals_use_dismissed_id():
    rankings = pd.read_csv(ROOT / "outputs" / "rankings" / "all_eligible_batters.csv")
    deliveries = pd.read_csv(
        ROOT / "outputs" / "cleaned_data" / "delivery_level_analysis.csv",
        low_memory=False,
    )
    pressure = deliveries[deliveries["is_pressure"]]
    for player_id in (1699, 813):
        rank_row = rankings.loc[rankings["player_id"].eq(player_id)].iloc[0]
        player_dismissals = int(
            (
                pressure["is_wicket"].astype(bool)
                & pressure["dismissed_player_id"].eq(player_id)
            ).sum()
        )
        assert int(rank_row["dismissals"]) == player_dismissals
