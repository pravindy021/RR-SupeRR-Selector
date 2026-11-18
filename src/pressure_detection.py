import math
import numpy as np


def _pressure_for_state(
    innings,
    over_number,
    innings_limit_balls,
    runs_required_before,
    required_run_rate_before,
    wickets_lost_before,
    balls_remaining_before,
):
    scheduled_overs = max(1, math.ceil(innings_limit_balls / 6))
    late_over_start = math.floor(0.80 * scheduled_overs) + 1
    in_late_overs = over_number >= late_over_start
    endgame_balls = max(1, math.ceil(0.10 * innings_limit_balls))
    in_endgame = balls_remaining_before <= endgame_balls
    chase = innings in (2, 4)
    if chase and runs_required_before > 0:
        return bool(
            required_run_rate_before >= 10
            or wickets_lost_before >= 5
            or in_endgame
            or (
                in_late_overs
                and (required_run_rate_before >= 8 or wickets_lost_before >= 3)
            )
        )
    if innings in (1, 3):
        return bool(
            in_late_overs
            and (wickets_lost_before >= 5 or in_endgame)
        )
    return False


def is_pressure_delivery(row):
    """Classify pressure from the state before this source delivery."""
    return _pressure_for_state(
        int(row["innings"]),
        int(row["over_number"]),
        int(row["innings_limit_balls"]),
        float(row["runs_required_before"]),
        float(row["required_run_rate_before"]),
        int(row["wickets_lost_before"]),
        int(row["balls_remaining_before"]),
    )


def pressure_mask(frame, score_variant="source_subtotal"):
    if score_variant == "source_subtotal":
        runs_required = frame["runs_required_before"]
        required_rate = frame["required_run_rate_before"]
    elif score_variant == "additive_candidate":
        runs_required = frame["runs_required_additive_candidate_before"]
        required_rate = frame["required_run_rate_additive_candidate_before"]
    else:
        raise ValueError(f"Unknown pressure score variant: {score_variant}")

    overs = np.ceil(frame["innings_limit_balls"] / 6).clip(lower=1)
    late_start = np.floor(0.80 * overs) + 1
    late_over = frame["over_number"].ge(late_start)
    endgame_balls = np.ceil(0.10 * frame["innings_limit_balls"]).clip(lower=1)
    endgame = frame["balls_remaining_before"].le(endgame_balls)
    chase = frame["innings"].isin([2, 4])
    chase_active = chase & runs_required.gt(0)
    return (
        (
            chase_active
            & (
                required_rate.ge(10)
                | frame["wickets_lost_before"].ge(5)
                | endgame
                | (
                    late_over
                    & (
                        required_rate.ge(8)
                        | frame["wickets_lost_before"].ge(3)
                    )
                )
            )
        )
        | (
            frame["innings"].isin([1, 3])
            & late_over
            & (frame["wickets_lost_before"].ge(5) | endgame)
        )
    )
