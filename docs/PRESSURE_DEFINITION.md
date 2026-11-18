# Pressure Definition and State Timing

## State timing

Every match situation is calculated immediately **before** the current delivery. The current delivery's runs, extras, and wicket are not included. `over_number` comes directly from source `overid`; `innings_ball_num` is only used to order deliveries within an innings. Balls remaining are scheduled legal balls minus legal balls already bowled, so a wide/no-ball does not consume one.

The source-component subtotal is `runs + extras1_runs`. `extras_2_runs` is unresolved and is not included in the primary state; an additive candidate is computed in parallel to quantify the impact. The target for an ordinary chase is `revised_target` when supplied; otherwise it is the first-innings source-component subtotal plus one. Super-over innings are treated as six-ball innings; innings 4 chases the innings 3 source-component subtotal plus one.

## Pressure indicators

The same high-leverage match-state label is used for batting and bowling; batting and bowling outcomes are measured with separate role-specific metrics. A death over alone is not sufficient. For a scheduled innings of `O = ceil(legal-ball limit / 6)` overs, the late-over window starts at `floor(0.80 × O) + 1`, using the source `overid`. The endgame is the final `ceil(0.10 × legal-ball limit)` legal balls.

For a chase (innings 2 or 4), while runs remain, a delivery is pressure when at least one pre-ball condition holds:

- Required run rate is at least 10 runs per over.
- At least five wickets have fallen.
- The innings is in the endgame.
- It is in the late-over window and either the required run rate is at least 8 or at least three wickets have fallen.

For a first innings (innings 1 or 3), pressure requires both the late-over window and either at least five wickets fallen or the endgame. This avoids treating every death-over ball as equally pressured. `runs_required_before`, `wickets_remaining_before`, current score/run rate, legal balls remaining, and source over are retained for audit. Competition context is handled by separate IPL/T20I/Other T20 summaries and context-specific ranking normalization, not by using future results in the pressure flag.

Shortened innings use their revised legal-ball limits. The source values appear to be legal-ball limits because they are multiples of six, but this unit is inferred. The definition is deterministic and does not use outcomes from the classified delivery. If prior `extras_2_runs` exist, the source-subtotal and additive-candidate pressure flags are compared and the state is marked uncertain.

## Interrupted/incomplete innings

Each delivery is annotated with the innings limit and an observed completion status: all out, target reached, scheduled balls completed, or `incomplete_or_interrupted`. No unobserved deliveries or end-of-innings scores are imputed. Revised-target values are compared with observed chase totals; matches without a source target use the source-component subtotal. Missing innings and unresolved secondary extras remain limitations.
