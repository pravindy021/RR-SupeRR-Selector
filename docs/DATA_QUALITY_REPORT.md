# Data Quality Report

## Coverage and identifiers

The supplied source files contain 200,999 ball-by-ball records, 883 match records, 141 competition records, 6,413 competition/team/player mappings, 28,381 playing-XI rows, and 353 team records. Deliveries cover 867 distinct matches. Source rows are preserved unchanged.

The delivery-to-match and match-to-competition joins are many-to-one validated in the pipeline. All observed competition/team/player combinations map to the supplied identity table. One source player alias is present (`Aneurin Donald` in ball-by-ball versus `AHT Donald` in the identity map, ID 4458); ranked players have exact name matches in the map and delivery records. Revised-innings fields each have 25 non-null source values; all observed values are whole multiples of six between 30 and 114. The analysis treats these as legal-ball limits, an inferred unit. Two revised second innings belong to `No Result` matches and have no delivery records; their limits are audited, not imputed.

## Missing values and duplicates

No complete duplicate ball-by-ball rows were found. Twelve rows carry `dismissed_player_id` while `is_wicket` is false and are ignored for batter dismissal attribution. One wicket (`Retire Out`) has no `dismissed_player_id`; the match wicket is retained, but player-level attribution is unavailable.

## Extras limitation

The source pack and official brief contain no field-level data dictionary. Thirty-six delivery rows contain non-zero `extras_2_runs` (84 runs). The primary innings-state subtotal uses `runs + extras1_runs`; an additive candidate is calculated separately, and pressure/ranking sensitivity to the two interpretations is reported. The component's innings-total treatment and recipient are not documented. Also unallocated are 264 `extras1_runs` tagged `other` and one run with a missing extras label, for 349 source runs that cannot safely be charged to a bowler. Bowler economy, dot-ball attribution on unresolved rows, and related rankings remain provisional pending supplier clarification.

## Incomplete innings

Each delivery output includes an innings completion status: `all_out`, `target_reached`, `scheduled_balls_completed`, or `incomplete_or_interrupted`. No missing deliveries are imputed. An interrupted innings without a recorded revised target or limit cannot be fully reconstructed from ball data alone.
