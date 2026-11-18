# Data Dictionary and Source Semantics

## Documentation availability

The supplied Data Pack contains six CSV files and the official competition brief. It contains no separate data dictionary or field-level specification. Consequently, source field meanings that cannot be established from the records themselves are explicitly marked as unresolved below; the analysis does not silently assign those runs to a bowler.

## Source tables

- `ball_by_ball.csv`: delivery records keyed by `match_id`, `innings`, and `innings_ball_num`; includes source `overid`, batter/bowler IDs and names, `runs`, `extras_type`, `extras1_runs`, `extras_2_runs`, and wicket fields.
- `matches.csv`: match/competition/teams and revised target/innings fields.
- `competitions.csv`: competition name, format, season, and `comp_id`.
- `playing_eleven.csv`: match/team/player participation records.
- `competition_team_player_mapping.csv`: competition/team/player identity map.
- `teams.csv`: team names and IDs within competitions.

## Reconstructed delivery fields

- `is_legal_ball`: false for `wide`, `Overstep` (no-ball), and the standalone `Penalty` event. Byes and leg-byes are legal deliveries.
- `is_batter_ball_faced`: false for wides and standalone penalty events; true for no-balls, byes, leg-byes, and ordinary deliveries.
- `team_runs_this_delivery`: source-component subtotal `runs + extras1_runs`. This is kept separate from unresolved `extras_2_runs`.
- `team_runs_additive_candidate`: alternative candidate `runs + extras1_runs + extras_2_runs`, with each source component included once. This is not treated as an authoritative innings total without a supplier specification.
- `bowler_conceded_runs_known`: source batter runs plus `extras1_runs` when the extras label is wide/no-ball. Byes, leg-byes, penalty, and undocumented extras are not charged to the bowler.
- `bowler_runs_unallocated`: `extras_2_runs`, plus `extras1_runs` tagged `other` or missing. These source values are not assigned to a bowler without documentation.
- `is_batter_dot_ball` / `is_bowler_dot_ball`: zero-run candidate deliveries, requiring no batter-facing/nonlegal exclusion respectively. A positive unresolved secondary component is conservatively not labelled a dot.
- `is_bowling_wicket`: a wicket other than run out, retirement, or obstruction of the field.

## Extras limitation

There are 36 rows with non-zero `extras_2_runs` (84 runs in total). The CSV has no field describing whether these are batter runs, byes/leg-byes, overthrows, a secondary innings total, or another category. The primary match state uses `runs + extras1_runs`; a candidate additive state is computed separately. Bowler economy and rankings are known-charge estimates, not complete scorecard economy figures. Pressure states after such source rows are marked uncertain. See [EXTRAS_DATA_INTEGRITY_AUDIT.md](./EXTRAS_DATA_INTEGRITY_AUDIT.md).

The source also contains 264 `extras1_runs` tagged `other` and one `extras1_runs` value with a missing extras label. Together with `extras_2_runs`, this yields 349 runs that are not safely allocatable to the bowler. The supplied records do not establish whether `extras_2_runs` should be added to innings totals or charged to the bowler.

## Revised innings limits and target

The revised-innings fields are named `*_revised_overs`, but observed non-null values are integer multiples of six between 30 and 114 (for example 114). The pipeline treats these values as legal-ball limits; values outside that observed convention are rejected. This is a data-derived interpretation, not a supplied schema guarantee.

`revised_target` matches the score-to-reach in the observed revised-target cases. Required runs before a delivery are `max(revised_target - source-component score, 0)`. When absent, the default target is the first-innings source-component subtotal plus one; the additive-candidate state is calculated separately when `extras_2_runs` is present.
