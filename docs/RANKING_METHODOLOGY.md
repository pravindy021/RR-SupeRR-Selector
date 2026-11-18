# Ranking and Reliability Methodology

## Eligible evidence

Only IPL and T20I records contribute to the combined rankings. Other T20 competitions appear in a separate performance summary and do not enter the ranking. A batter needs at least 30 pressure balls faced and four pressure matches; a bowler needs at least 24 pressure legal balls and four pressure matches.

## Context scores

Metric values are shrunk toward the median of players in the same context before percentile normalization:

`shrunk = observed × n/(n+k) + context_median × k/(n+k)`

Here `n` is the relevant ball count (or pressure innings for dismissal avoidance) and `k` is 60 balls or four innings. This reduces extreme small-sample rates while preserving the player's observed value as sample size grows. Metrics are percentile-scored within IPL or T20I, not across the pooled formats.

### Batter performance dimensions

| Dimension | Weight | Direction | Denominator |
|---|---:|---|---|
| Pressure strike rate | 35% | Higher | Balls faced (wide excluded; no-ball included) |
| Boundary rate | 20% | Higher | Balls faced |
| Dot-ball avoidance | 20% | Higher | Balls faced with no team runs on the delivery |
| Dismissal avoidance | 25% | Higher | Pressure innings, with dismissal keyed to `dismissed_player_id` |

### Bowler performance dimensions

| Dimension | Weight | Direction | Denominator |
|---|---:|---|---|
| Economy from known bowler charges | 40% | Lower | Legal balls |
| Wickets per six legal balls | 35% | Higher | Legal balls |
| Dot-ball rate | 25% | Higher | Legal deliveries with no team runs |

No metric is entered twice. `extras_2_runs` and other undocumented extras remain separately flagged and are not assumed to be bowler charges.

## Consistency, sample adjustment, and final score

Match consistency for pressure strike rates/economies is `1/(1+CV)`, where `CV = population standard deviation / absolute mean`. Fewer than two pressure matches or a zero mean yields a consistency score of 0.

Within each competition context, the percentile performance score is adjusted toward a neutral 0.5 prior:

`reliability = confidence × performance + (1-confidence) × 0.5`

`confidence = pressure_matches/(pressure_matches+4)`.

The context rating is `0.75 × reliability + 0.25 × consistency`. Final combined score is `0.70 × IPL rating + 0.30 × T20I rating`; a missing context contributes the neutral 0.5 prior and is not reweighted to 100% of the score. This intentionally prioritizes IPL evidence for the RR use case while retaining a defined contribution from T20I evidence.

The pipeline also exports independent IPL-only and T20I-only Top 10s for both roles. These lists rank the context-specific rating `0.75 × reliability + 0.25 × consistency` and apply the minimum balls and four-match threshold within that context; they are not filtered views of the combined ranking. Ties are broken by context pressure sample size (descending), then player name (ascending). The dashboard's context selector loads these independent lists.

## Sensitivity

The primary performance/consistency weights are 75%/25%. Sensitivity is recalculated from the eligible player scores using 85%/15% and 60%/40% alternatives. Top-10 overlap is the count and proportion of IDs shared with the primary list. These values are generated from actual scenario rankings.

## Limitations

The field definition for `extras_2_runs` is unavailable. Rankings use the `runs + extras1_runs` source-component subtotal for match state; an additive scenario is calculated separately. Some pre-delivery states and bowler dot/economy metrics are therefore provisional. Competition strength, venue, current squad role, auction availability, and market value are not modeled.
