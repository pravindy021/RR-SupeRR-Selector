# Extras Data-Integrity Audit

## Scope and evidence searched

The audit inspected all six supplied CSV schemas and records, the official two-page Round 1 brief PDF, the project data dictionary, the existing cleaning and match-state transformations, and all extras-related tests. The data pack contains no supplier schema, field-level dictionary, metadata sidecar, or separate extras specification. The competition brief does not define `extras_2_runs`.

The source files are preserved unchanged. The findings below describe what is observable in the records and distinguish it from unresolved field semantics.

## Observed source values

`ball_by_ball.csv` contains 200,999 delivery rows. The extras labels and record counts are:

| `extras_type` | Rows | Source `extras1_runs` total | Source `extras_2_runs` total |
|---|---:|---:|---:|
| `wide` | 7,714 | 9,174 | 0 |
| `legbyes` | 2,748 | 3,603 | 0 |
| `Overstep` (no-ball label) | 576 | 576 | 48 |
| `byes` | 529 | 1,000 | 0 |
| `other` | 264 | 264 | 35 |
| `Penalty` | 1 | 5 | 0 |
| Missing | 189,167 | 1 | 1 |

There are 36 rows with non-zero `extras_2_runs`, totaling 84 runs: 21 `Overstep` rows totaling 48, 14 `other` rows totaling 35, and one row with a missing extras label totaling 1. In every nonzero `Overstep`/`other` example, `runs` is zero and `extras1_runs` is one; this pattern alone does not establish whether the secondary amount is a second innings charge, a bowler charge, or another category.

There are also 264 `extras1_runs` tagged `other` and one `extras1_runs` value with a missing label. Thus, 349 source runs (84 secondary plus 265 ambiguous first-extra runs) cannot safely be assigned to a bowler. This is a charge-allocation total, not a claim that the 349 runs are missing from the source.

The source run columns contain no null or negative values. Exact duplicate ball-by-ball rows were not found. The source does not establish whether `runs` is exclusively batter runs, whether `extras_2_runs` contributes to the innings total, or which component is charged to a bowler.

## Treatment and affected quantities

The pipeline preserves each source component and reports two innings-state scenarios:

1. **Source-component subtotal (primary):** `runs + extras1_runs`. This is a reproducible subtotal from the two named source fields; it is not represented as a supplier-verified final scorecard total.
2. **Additive candidate:** `runs + extras1_runs + extras_2_runs`. This exposes the impact if the secondary field is an additional innings-run component; it is not presumed authoritative.

The primary pre-delivery score, target fallback, required runs, and required run rate use the source-component subtotal. The additive-candidate state is calculated separately. Any delivery after a prior nonzero `extras_2_runs` in a relevant innings is flagged `match_state_secondary_extras_uncertain`; pressure flags and rankings are compared between scenarios.

Bowler-known charges include `runs` and `extras1_runs` for recognized wides and no-balls. Byes, leg-byes, penalty events, `other`, and `extras_2_runs` are not charged to the bowler without evidence. `bowler_runs_unallocated` preserves the secondary amount plus ambiguous `other`/missing `extras1_runs`.

Consequences:

- The 84 secondary runs may change innings totals, default chase targets, current score, required rate, and which deliveries enter the pressure sample.
- The 349 unallocated runs prevent exact bowler-conceded runs and economy validation. Dot-ball classification on a delivery with unresolved positive runs is conservatively not counted as a dot.
- Batter runs and balls-faced counts are calculated from the striker/source delivery fields and delivery legality. Their underlying totals do not allocate extras to the batter, but their pressure opportunities and rates can change if the unresolved component changes pre-delivery state.
- Wicket counts use `is_wicket` and dismissal type; they do not depend on extras allocation, although pressure-sample membership can.

The generated `outputs/tables/extras_semantics_audit.csv` records the row/run totals, pressure-state disagreement, and Top-10 overlap for the source-component and additive-candidate scenarios. Those calculated comparisons are sensitivity evidence, not proof of field meaning.

## Cricket delivery treatment

- `wide`: not a legal ball and not a batter ball faced; identified wide charge is included in bowler-known runs.
- `Overstep`: treated as a no-ball; batter ball faced but not a legal ball; identified no-ball charge is included in bowler-known runs.
- `byes` and `legbyes`: legal balls and batter balls faced; not charged to the bowler.
- `Penalty`: the one standalone penalty event in the source is excluded from legal balls and balls faced; its recorded `extras1_runs` remains in the source-component subtotal.
- `other` and missing extras labels: retained, surfaced as unallocated, and not charged to the bowler by assumption.

## Conclusion and supplier clarification needed

No available local source resolves the field. Therefore, the report does **not** claim exact innings-total reconciliation or exact bowler economy. The primary rankings use the documented source-component scenario, the additive candidate is reported separately, and bowler economy/dot-ball metrics and affected pressure states remain provisional.

Before removing this limitation, the data provider must confirm:

1. The definition and source system for `extras_2_runs`.
2. Whether it is included in the official innings total and how it relates to `runs` and `extras1_runs`.
3. Whether it is charged to the bowler, and under which extras categories.
4. The intended interpretation of `other` and missing `extras_type` values.

No value is inferred or allocated beyond the explicitly labeled scenarios.
