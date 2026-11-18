from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.data_loader import audit_data, load_data
from src.data_cleaning import clean_data
from src.feature_engineering import add_match_situation
from src.pressure_detection import pressure_mask
from src.ranking_engine import (
    rank_players,
    rank_scored_by_context,
    sensitivity_analysis,
)


def competition_summary(frame):
    rows = []
    pressured = frame[frame["is_pressure"]]
    for (group, match_format), part in pressured.groupby(
        ["competition_group", "match_format"], sort=True
    ):
        bat = part[part["is_batter_ball_faced"]]
        legal = part[part["is_legal_ball"]]
        rows.append({
            "competition_group": group,
            "match_format": match_format,
            "pressure_matches": int(part["match_id"].nunique()),
            "pressure_deliveries": int(len(part)),
            "pressure_batter_balls_faced": int(len(bat)),
            "pressure_batter_runs": int(bat["runs"].sum()),
            "pressure_batter_strike_rate": (
                100 * bat["runs"].sum() / len(bat) if len(bat) else np.nan
            ),
            "pressure_bowler_legal_balls": int(len(legal)),
            "pressure_bowler_runs_known": int(part["bowler_conceded_runs_known"].sum()),
            "unallocated_bowler_extras": int(part["bowler_runs_unallocated"].sum()),
            "pressure_bowler_economy_known": (
                6 * part["bowler_conceded_runs_known"].sum() / len(legal)
                if len(legal) else np.nan
            ),
            "pressure_bowler_wickets": int(part["is_bowling_wicket"].sum()),
        })
    return pd.DataFrame(rows)


def sensitivity_table(batter_sensitivity, bowler_sensitivity):
    frames = [batter_sensitivity, bowler_sensitivity]
    return pd.concat(frames, ignore_index=True)


def add_evidence_notes(rankings, role):
    result = rankings.copy()
    if role == "Batter":
        result["potential_role_profile"] = "Pressure run-acceleration batting profile"
        result["selection_justification"] = result.apply(
            lambda row: (
                f"{int(row.pressure_opportunities)} pressure matches; "
                f"{int(row.pressure_runs)} runs from {int(row.pressure_balls)} faced "
                f"(SR {row.pressure_strike_rate:.1f}); "
                f"{int(row.dismissals)} dismissed-player events."
            ),
            axis=1,
        )
        result["evidence_limitations"] = (
            "Pressure states can differ under the unresolved extras_2_runs scenario; "
            "current batting position and auction availability are not verified."
        )
    else:
        result["potential_role_profile"] = (
            "Pressure wicket-taking and run-prevention bowling profile"
        )
        result["selection_justification"] = result.apply(
            lambda row: (
                f"{int(row.pressure_opportunities)} pressure matches; "
                f"{int(row.wickets)} wickets from {int(row.pressure_legal_balls)} legal balls; "
                f"known-charge economy {row.pressure_economy_known:.2f}."
            ),
            axis=1,
        )
        result["evidence_limitations"] = result.apply(
            lambda row: (
                f"Known-charge economy/dot rate; {int(row.unallocated_pressure_extras)} "
                "unallocated pressure extras; pressure states can differ under the "
                "unresolved extras_2_runs scenario. Current role/availability is not verified."
            ),
            axis=1,
        )
    return result


def revised_innings_audit(matches, deliveries):
    observed_pairs = set(
        zip(deliveries["match_id"].astype(int), deliveries["innings"].astype(int))
    )
    rows = []
    for row in matches.itertuples(index=False):
        for innings, column in (
            (1, "first_inn_revised_overs"),
            (2, "second_inn_revised_overs"),
        ):
            limit = getattr(row, column)
            if pd.isna(limit):
                continue
            present = (int(row.match_id), innings) in observed_pairs
            rows.append({
                "match_id": int(row.match_id),
                "competition": row.comp_name,
                "innings": innings,
                "source_limit_value": int(limit),
                "interpreted_legal_balls": int(limit),
                "ball_by_ball_present": present,
                "match_result": row.result,
                "status": "observed" if present else "no_delivery_records",
            })
    return pd.DataFrame(rows)


def innings_totals_audit(frame):
    rows = []
    for (match_id, innings), part in frame.groupby(
        ["match_id", "innings"], sort=True
    ):
        final = part.iloc[-1]
        rows.append({
            "match_id": int(match_id),
            "competition": final["comp_name"],
            "season": final["season"],
            "innings": int(innings),
            "delivery_records": int(len(part)),
            "legal_balls": int(part["is_legal_ball"].sum()),
            "wickets": int(part["is_wicket"].sum()),
            "scheduled_limit_balls": int(final["innings_limit_balls"]),
            "source_component_subtotal": int(part["team_runs_this_delivery"].sum()),
            "unresolved_secondary_runs": int(part["extras_2_runs"].sum()),
            "additive_candidate_total": int(
                part["team_runs_additive_candidate"].sum()
            ),
            "source_revised_target": final["revised_target"],
            "completion_status": final["innings_completion_status"],
            "match_result": final["result"],
        })
    return pd.DataFrame(rows)


def source_integrity_audit(source, data, frame):
    ball = source["ball_by_ball"]
    matches = source["matches"]
    competitions = source["competitions"]
    mapping = source["competition_team_player_mapping"]
    match_comp = matches.set_index("match_id")["comp_id"]
    ball_comp = ball["match_id"].map(match_comp)
    map_keys = set(
        map(
            tuple,
            mapping[["comp_id", "team_id", "player_id"]]
            .drop_duplicates()
            .astype(int)
            .to_numpy(),
        )
    )
    unmapped_player_team = 0
    for player_column, team_column in (
        ("striker_id", "batting_team_id"),
        ("non_striker_id", "batting_team_id"),
        ("bowler_id", "bowling_team_id"),
    ):
        combinations = pd.DataFrame({
            "comp_id": ball_comp,
            "team_id": ball[team_column],
            "player_id": ball[player_column],
        }).drop_duplicates()
        unmapped_player_team += sum(
            (int(row.comp_id), int(row.team_id), int(row.player_id)) not in map_keys
            for row in combinations.itertuples(index=False)
        )

    source_names = pd.concat([
        ball[["striker_id", "striker_name"]].rename(
            columns={"striker_id": "player_id", "striker_name": "player_name"}
        ),
        ball[["non_striker_id", "non_striker_name"]].rename(
            columns={"non_striker_id": "player_id", "non_striker_name": "player_name"}
        ),
        ball[["bowler_id", "bowler_name"]].rename(
            columns={"bowler_id": "player_id", "bowler_name": "player_name"}
        ),
    ]).dropna().drop_duplicates()
    mapped_names = mapping.groupby("player_id")["player_name"].agg(set)
    name_aliases = source_names[
        source_names.apply(
            lambda row: row["player_name"] not in mapped_names.get(
                row["player_id"], set()
            ),
            axis=1,
        )
    ]
    findings = [
        ("delivery_records", len(ball), "Source ball-by-ball rows"),
        ("delivery_matches", int(ball["match_id"].nunique()), "Distinct match IDs in deliveries"),
        ("source_matches", int(matches["match_id"].nunique()), "Distinct match IDs in matches.csv"),
        ("source_competitions", int(competitions["comp_id"].nunique()), "Distinct competition IDs"),
        ("duplicate_delivery_rows", int(ball.duplicated().sum()), "Exact duplicate delivery rows"),
        ("duplicate_match_ids", int(matches["match_id"].duplicated().sum()), "Repeated match keys"),
        ("duplicate_competition_ids", int(competitions["comp_id"].duplicated().sum()), "Repeated competition keys"),
        (
            "duplicate_team_keys",
            int(source["teams"].duplicated(["comp_id", "team_id"]).sum()),
            "Repeated competition/team keys",
        ),
        ("duplicate_identity_rows", int(mapping.duplicated().sum()), "Exact duplicate player-map rows"),
        ("unmatched_delivery_match_ids", int(ball_comp.isna().sum()), "Delivery rows without a source match"),
        ("unmapped_player_team_combinations", int(unmapped_player_team), "Role/team/competition combinations absent from identity map"),
        ("source_player_name_alias_pairs", int(len(name_aliases)), "Source names differing from mapping names"),
        (
            "dismissed_id_on_non_wicket_rows",
            int((ball["dismissed_player_id"].notna() & ~ball["is_wicket"].astype(bool)).sum()),
            "Ignored for player dismissal attribution",
        ),
        (
            "wickets_without_dismissed_id",
            int((ball["is_wicket"].astype(bool) & ball["dismissed_player_id"].isna()).sum()),
            "Match wicket retained; player attribution unavailable",
        ),
        (
            "boundary_flag_run_mismatches",
            int(
                (
                    ball["is_four"].astype(bool) & ball["runs"].ne(4)
                    | ball["is_six"].astype(bool) & ball["runs"].ne(6)
                ).sum()
            ),
            "Boundary flags inconsistent with source run value",
        ),
        ("missing_batting_team_names", int(frame["batting_team_name"].isna().sum()), "Delivery rows missing joined batting team"),
        ("missing_bowling_team_names", int(frame["bowling_team_name"].isna().sum()), "Delivery rows missing joined bowling team"),
        ("revised_first_innings_limits", int(matches["first_inn_revised_overs"].notna().sum()), "Non-null source revised limits"),
        ("revised_second_innings_limits", int(matches["second_inn_revised_overs"].notna().sum()), "Non-null source revised limits"),
    ]
    return pd.DataFrame(findings, columns=["finding", "count", "interpretation"])


def save_charts(batters, bowlers, df, sensitivity, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    top_b = batters.head(10)
    top_bw = bowlers.head(10)

    if not top_b.empty:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh(
            top_b["player_name"][::-1],
            top_b["pressure_strike_rate"][::-1],
            color="#CD5046",
        )
        ax.set(title="Top Pressure Batters", xlabel="Pressure strike rate", ylabel="Player")
        fig.tight_layout()
        fig.savefig(output_dir / "top_10_pressure_batters.png", dpi=180)
        plt.close(fig)

    if not top_bw.empty:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh(
            top_bw["player_name"][::-1],
            top_bw["pressure_economy_known"][::-1],
            color="#4C78A8",
        )
        ax.invert_xaxis()
        ax.set(
            title="Top Pressure Bowlers (known-conceded-run estimate)",
            xlabel="Known pressure economy",
            ylabel="Player",
        )
        fig.tight_layout()
        fig.savefig(output_dir / "top_10_pressure_bowlers.png", dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if not top_b.empty:
        axes[0].bar(top_b["player_name"], top_b["pressure_strike_rate"], color="#CD5046")
        axes[0].tick_params(axis="x", rotation=60)
        axes[0].set(title="Pressure strike rate", ylabel="Runs per 100 balls faced")
    if not top_bw.empty:
        axes[1].bar(top_bw["player_name"], top_bw["pressure_economy_known"], color="#4C78A8")
        axes[1].tick_params(axis="x", rotation=60)
        axes[1].set(title="Known pressure economy", ylabel="Runs per 6 legal balls")
    fig.tight_layout()
    fig.savefig(output_dir / "performance_comparisons.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    match_counts = (
        df[df["is_pressure"]]
        .groupby("competition_group")["match_id"]
        .nunique()
        .sort_index()
    )
    match_counts.plot(kind="bar", ax=ax, color="#72A555")
    ax.set(title="Matches containing pressure deliveries", xlabel="Competition group", ylabel="Matches")
    fig.tight_layout()
    fig.savefig(output_dir / "pressure_opportunity_distribution.png", dpi=180)
    plt.close(fig)

    if not top_b.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        positions = np.arange(len(top_b))
        width = 0.38
        ax.bar(positions - width / 2, top_b["ipl_pressure_strike_rate"], width, label="IPL pressure")
        ax.bar(positions + width / 2, top_b["ipl_normal_strike_rate"], width, label="IPL normal")
        ax.set_xticks(positions, top_b["player_name"], rotation=55, ha="right")
        ax.set(title="IPL batter normal vs pressure strike rate", ylabel="Strike rate")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "normal_vs_pressure_batters.png", dpi=180)
        plt.close(fig)

    if not top_bw.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        positions = np.arange(len(top_bw))
        width = 0.38
        ax.bar(positions - width / 2, top_bw["ipl_pressure_economy_known"], width, label="IPL pressure")
        ax.bar(positions + width / 2, top_bw["ipl_normal_economy_known"], width, label="IPL normal")
        ax.set_xticks(positions, top_bw["player_name"], rotation=55, ha="right")
        ax.set(title="IPL bowler normal vs pressure economy", ylabel="Runs per 6 legal balls")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_dir / "normal_vs_pressure_bowlers.png", dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if not top_b.empty:
        axes[0].bar(top_b["player_name"], top_b["consistency_score"], color="#72A555")
        axes[0].tick_params(axis="x", rotation=60)
        axes[0].set(title="Batter match consistency", ylabel="1 / (1 + coefficient of variation)")
    if not top_bw.empty:
        axes[1].bar(top_bw["player_name"], top_bw["consistency_score"], color="#72A555")
        axes[1].tick_params(axis="x", rotation=60)
        axes[1].set(title="Bowler match consistency", ylabel="1 / (1 + coefficient of variation)")
    fig.tight_layout()
    fig.savefig(output_dir / "consistency_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    context_summary = competition_summary(df)
    if not context_summary.empty:
        ax.bar(
            context_summary["competition_group"],
            context_summary["pressure_batter_strike_rate"],
            color="#8C6BB1",
        )
    ax.set(title="Competition-wise pressure batting", xlabel="Competition", ylabel="Pressure strike rate")
    fig.tight_layout()
    fig.savefig(output_dir / "competition_wise_performance.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if not top_b.empty:
        axes[0].bar(top_b["player_name"], top_b["reliability_score"], color="#D99035")
        axes[0].tick_params(axis="x", rotation=60)
        axes[0].set(title="Batter reliability", ylabel="Sample-shrunk pressure performance")
    if not top_bw.empty:
        axes[1].bar(top_bw["player_name"], top_bw["reliability_score"], color="#D99035")
        axes[1].tick_params(axis="x", rotation=60)
        axes[1].set(title="Bowler reliability", ylabel="Sample-shrunk pressure performance")
    fig.tight_layout()
    fig.savefig(output_dir / "reliability_score_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    if not sensitivity.empty:
        for role, part in sensitivity.groupby("role"):
            ax.plot(
                part["scenario"],
                part["primary_top_10_overlap_rate"],
                marker="o",
                label=role,
            )
    ax.set(
        title="Top-10 overlap under alternative score weights",
        xlabel="Scenario",
        ylabel="Overlap with primary Top 10",
        ylim=(0, 1.05),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "sensitivity_analysis.png", dpi=180)
    plt.close(fig)


def main():
    data_dir = ROOT / "data" / "RR_DATASETS" / "Data Pack"
    source = load_data(data_dir)
    data = clean_data(source)
    audit = audit_data(source)
    df = add_match_situation(
        data["ball_by_ball"], data["match_context"], data["teams"]
    )
    integrity_audit = source_integrity_audit(source, data, df)
    df["is_pressure"] = pressure_mask(df)
    df["is_pressure_additive_candidate"] = pressure_mask(
        df, score_variant="additive_candidate"
    )

    batters, batter_context_scores = rank_players(df, "Batter")
    bowlers, bowler_context_scores = rank_players(df, "Bowler")
    batters = add_evidence_notes(batters, "Batter")
    bowlers = add_evidence_notes(bowlers, "Bowler")
    context_rankings = {}
    for role, role_name, context_scores in (
        ("batters", "Batter", batter_context_scores),
        ("bowlers", "Bowler", bowler_context_scores),
    ):
        for context in ("IPL", "T20I"):
            context_rankings[(role, context)] = add_evidence_notes(
                rank_scored_by_context(context_scores, role_name, context),
                role_name,
            )
    batter_sensitivity, _ = sensitivity_analysis(df, "Batter", batters)
    bowler_sensitivity, _ = sensitivity_analysis(df, "Bowler", bowlers)
    sensitivity = sensitivity_table(batter_sensitivity, bowler_sensitivity)
    additive_candidate = df.copy()
    additive_candidate["is_pressure"] = additive_candidate[
        "is_pressure_additive_candidate"
    ]
    additive_batters, _ = rank_players(additive_candidate, "Batter")
    additive_bowlers, _ = rank_players(additive_candidate, "Bowler")
    comp_summary = competition_summary(df)
    revised_audit = revised_innings_audit(
        data["match_context"], data["ball_by_ball"]
    )
    innings_audit = innings_totals_audit(df)

    rankings_dir = ROOT / "outputs" / "rankings"
    charts_dir = ROOT / "outputs" / "charts"
    tables_dir = ROOT / "outputs" / "tables"
    cleaned_dir = ROOT / "outputs" / "cleaned_data"
    for directory in (rankings_dir, charts_dir, tables_dir, cleaned_dir):
        directory.mkdir(parents=True, exist_ok=True)

    batters.head(10).to_csv(rankings_dir / "top_10_batters.csv", index=False)
    bowlers.head(10).to_csv(rankings_dir / "top_10_bowlers.csv", index=False)
    for (role, context), rankings in context_rankings.items():
        rankings.head(10).to_csv(
            rankings_dir / f"top_10_{role}_{context.lower()}.csv",
            index=False,
        )
    combined = pd.concat(
        [
            batters.head(10).assign(role="Batter"),
            bowlers.head(10).assign(role="Bowler"),
        ],
        ignore_index=True,
        sort=False,
    )
    combined.to_csv(rankings_dir / "combined_player_analysis.csv", index=False)
    batters.to_csv(rankings_dir / "all_eligible_batters.csv", index=False)
    bowlers.to_csv(rankings_dir / "all_eligible_bowlers.csv", index=False)
    sensitivity.to_csv(tables_dir / "sensitivity_analysis.csv", index=False)
    comp_summary.to_csv(tables_dir / "competition_performance_summary.csv", index=False)
    audit.to_csv(tables_dir / "data_audit.csv", index=False)
    integrity_audit.to_csv(tables_dir / "source_integrity_audit.csv", index=False)

    extras1_ambiguous = df["extras_type"].isin(["other", ""])
    primary_batter_ids = set(batters.head(10)["player_id"])
    primary_bowler_ids = set(bowlers.head(10)["player_id"])
    extras_audit = pd.DataFrame([{
        "nonzero_extras_2_rows": int(df["extras_2_runs"].ne(0).sum()),
        "extras_2_run_total": int(df["extras_2_runs"].sum()),
        "extras1_other_or_missing_rows": int(
            (extras1_ambiguous & df["extras1_runs"].gt(0)).sum()
        ),
        "extras1_other_or_missing_total": int(
            df.loc[extras1_ambiguous, "extras1_runs"].sum()
        ),
        "source_component_subtotal_runs": int(df["team_runs_this_delivery"].sum()),
        "additive_candidate_total_runs": int(
            df["team_runs_additive_candidate"].sum()
        ),
        "bowler_unallocated_extra_runs": int(df["bowler_runs_unallocated"].sum()),
        "pressure_state_uncertain_deliveries": int(
            df["match_state_secondary_extras_uncertain"].sum()
        ),
        "pressure_state_uncertain_matches": int(
            df.loc[df["match_state_secondary_extras_uncertain"], "match_id"].nunique()
        ),
        "pressure_flags_differ_by_total_scenario": int(
            df["is_pressure"].ne(df["is_pressure_additive_candidate"]).sum()
        ),
        "source_subtotal_only_pressure_flags": int(
            (df["is_pressure"] & ~df["is_pressure_additive_candidate"]).sum()
        ),
        "additive_candidate_only_pressure_flags": int(
            (~df["is_pressure"] & df["is_pressure_additive_candidate"]).sum()
        ),
        "batter_top_10_overlap_with_additive_candidate": len(
            primary_batter_ids & set(additive_batters.head(10)["player_id"])
        ),
        "bowler_top_10_overlap_with_additive_candidate": len(
            primary_bowler_ids & set(additive_bowlers.head(10)["player_id"])
        ),
        "source_dictionary_available": False,
        "treatment": (
            "Primary match state uses runs + extras1_runs; extras_2_runs remains separate. "
            "An additive total is audited as an alternative, not treated as verified. "
            "Do not allocate unresolved extras to bowlers."
        ),
    }])
    extras_audit.to_csv(tables_dir / "extras_semantics_audit.csv", index=False)
    revised_audit.to_csv(tables_dir / "revised_innings_audit.csv", index=False)
    innings_audit.to_csv(tables_dir / "innings_totals_audit.csv", index=False)
    analysis_summary = pd.DataFrame([{
        "delivery_records": int(len(df)),
        "delivery_matches": int(df["match_id"].nunique()),
        "source_match_records": int(data["matches"]["match_id"].nunique()),
        "source_competitions": int(data["competitions"]["comp_id"].nunique()),
        "pressure_delivery_records": int(df["is_pressure"].sum()),
        "pressure_match_count": int(df.loc[df["is_pressure"], "match_id"].nunique()),
        "first_revised_limit_count": int(data["matches"]["first_inn_revised_overs"].notna().sum()),
        "second_revised_limit_count": int(data["matches"]["second_inn_revised_overs"].notna().sum()),
        "revised_innings_without_ball_records": int((~revised_audit["ball_by_ball_present"]).sum()),
        "competition_seasons": "; ".join(sorted(data["competitions"]["season"].astype(str).unique())),
    }])
    analysis_summary.to_csv(tables_dir / "analysis_summary.csv", index=False)
    df.to_csv(cleaned_dir / "delivery_level_analysis.csv", index=False)

    save_charts(batters, bowlers, df, sensitivity, charts_dir)
    print(
        f"Analyzed {len(df):,} deliveries across "
        f"{df['match_id'].nunique():,} matches."
    )
    print(
        f"Eligible batters: {len(batters)}; "
        f"eligible bowlers: {len(bowlers)}"
    )
    print(f"Pressure data by competition:\n{comp_summary.to_string(index=False)}")
    print("\nTOP 10 BATTERS")
    columns = [
        "rank", "player_name", "player_id", "team_context", "competition_context",
        "pressure_opportunities", "pressure_balls", "pressure_runs",
        "pressure_strike_rate", "consistency_score", "reliability_score",
        "final_composite_score",
    ]
    print(batters.head(10)[columns].to_string(index=False))
    print("\nTOP 10 BOWLERS")
    columns = [
        "rank", "player_name", "player_id", "team_context", "competition_context",
        "pressure_opportunities", "pressure_legal_balls",
        "pressure_runs_conceded_known", "unallocated_pressure_extras",
        "wickets", "pressure_economy_known", "consistency_score",
        "reliability_score", "final_composite_score",
    ]
    print(bowlers.head(10)[columns].to_string(index=False))
    print(f"\nExtras treatment audit:\n{extras_audit.to_string(index=False)}")
    print(f"\nSensitivity analysis:\n{sensitivity.to_string(index=False)}")


if __name__ == "__main__":
    main()
