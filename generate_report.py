from pathlib import Path
import shutil

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "reports" / "final_submission"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = OUTPUT_DIR / "SupeRR_Selector_Season_2_Methodology_Report.pdf"
RANK_DIR = ROOT / "outputs" / "rankings"
TABLE_DIR = ROOT / "outputs" / "tables"
CHART_DIR = ROOT / "outputs" / "charts"
EXECUTIVE_SUMMARY_PATH = OUTPUT_DIR / "Executive_Summary.md"
SOURCE_DOCUMENT_PATH = OUTPUT_DIR / "Methodology_Source.md"
PACKAGE_CHART_NAMES = [
    "top_10_pressure_batters.png",
    "top_10_pressure_bowlers.png",
    "normal_vs_pressure_batters.png",
    "normal_vs_pressure_bowlers.png",
    "consistency_comparison.png",
    "reliability_score_comparison.png",
    "sensitivity_analysis.png",
    "competition_wise_performance.png",
    "pressure_opportunity_distribution.png",
    "performance_comparisons.png",
]

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="SmallAudit", parent=styles["Normal"], fontSize=8, leading=10))
styles.add(ParagraphStyle(name="TableCell", parent=styles["Normal"], fontSize=6.5, leading=8))


def _display(value, decimals=2):
    if pd.isna(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _short(value, length=29):
    value = str(value or "")
    return value if len(value) <= length else value[: length - 3] + "..."


def _table(headers, rows, widths, font_size=7):
    data = [headers] + rows
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9AA7B2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _ranking_markdown(rankings, role):
    if role == "Batter":
        rows = [
            f"| {int(row.rank)} | {row.player_name} | {int(row.player_id)} | "
            f"{int(row.pressure_opportunities)} | {int(row.pressure_balls)} | "
            f"{int(row.pressure_runs)} | {row.pressure_strike_rate:.2f} | "
            f"{row.final_composite_score:.4f} |"
            for row in rankings.itertuples(index=False)
        ]
        return (
            "| Rank | Batter | ID | Pressure matches | Balls faced | Runs | SR | Score |\n"
            "|---:|---|---:|---:|---:|---:|---:|---:|\n"
            + "\n".join(rows)
        )
    rows = [
        f"| {int(row.rank)} | {row.player_name} | {int(row.player_id)} | "
        f"{int(row.pressure_opportunities)} | {int(row.pressure_legal_balls)} | "
        f"{int(row.wickets)} | {row.pressure_economy_known:.2f}* | "
        f"{row.final_composite_score:.4f} |"
        for row in rankings.itertuples(index=False)
    ]
    return (
        "| Rank | Bowler | ID | Pressure matches | Legal balls | Wickets | Known econ.* | Score |\n"
        "|---:|---|---:|---:|---:|---:|---:|---:|\n"
        + "\n".join(rows)
    )


def _player_recommendation_markdown(row, role):
    if role == "Batter":
        return (
            f"- **{row.player_name} (ID {int(row.player_id)}):** potential pressure "
            f"run-acceleration profile; {int(row.ipl_pressure_matches)} IPL pressure "
            f"matches, {int(row.ipl_pressure_balls)} faced, IPL pressure SR "
            f"{row.ipl_pressure_strike_rate:.1f}. Role/slot is inferred from performance, "
            "not verified by the supplied data."
        )
    return (
        f"- **{row.player_name} (ID {int(row.player_id)}):** potential pressure "
        f"wicket-taking/run-prevention profile; {int(row.ipl_pressure_matches)} IPL "
        f"pressure matches, {int(row.ipl_pressure_legal_balls)} legal balls, "
        f"{int(row.ipl_wickets)} IPL wickets, known-charge economy "
        f"{row.ipl_pressure_economy_known:.2f}. Economy is provisional."
    )


def _write_submission_package(batters, bowlers, summary, sensitivity, extras_audit):
    for role_file in (
        "top_10_batters.csv",
        "top_10_bowlers.csv",
        "top_10_batters_ipl.csv",
        "top_10_batters_t20i.csv",
        "top_10_bowlers_ipl.csv",
        "top_10_bowlers_t20i.csv",
        "combined_player_analysis.csv",
    ):
        shutil.copy2(RANK_DIR / role_file, OUTPUT_DIR / role_file)

    chart_package = OUTPUT_DIR / "charts"
    chart_package.mkdir(exist_ok=True)
    for name in PACKAGE_CHART_NAMES:
        source = CHART_DIR / name
        if not source.exists():
            raise FileNotFoundError(f"Required generated chart is missing: {source}")
        shutil.copy2(source, chart_package / name)

    batting_md = _ranking_markdown(batters, "Batter")
    bowling_md = _ranking_markdown(bowlers, "Bowler")
    summary_text = f"""# Executive Summary — SupeRR Selector Season 2

## Result

The corrected pipeline processed {int(summary.delivery_records):,} deliveries across
{int(summary.delivery_matches):,} matches (883 source match records; 141 competitions).
Competition seasons in the supplied data: {summary.competition_seasons}.

### Top 10 batters
{batting_md}

### Top 10 bowlers
{bowling_md}

Independent IPL-only and T20I-only ranked CSVs are included for both roles. Each uses
the context-specific 75% reliability / 25% consistency rating and that context's
minimum-sample eligibility rule; they are not filtered views of the combined list.

## Decision caveat

The data pack and official brief do not define `extras_2_runs` or `other` extras.
The primary match state uses `runs + extras1_runs`; an additive candidate is tested
separately. Pressure classification differs for
{int(extras_audit.pressure_flags_differ_by_total_scenario)} deliveries between those
scenarios, and the Top-10 overlap is
{int(extras_audit.batter_top_10_overlap_with_additive_candidate)}/10 for batters and
{int(extras_audit.bowler_top_10_overlap_with_additive_candidate)}/10 for bowlers.
The 349 runs that cannot be safely allocated to bowlers make known-charge economy,
bowling dot rates on unresolved deliveries, and related ranks provisional.

No player is claimed to be available for IPL 2027. Verify current role, squad need,
contract status, and auction availability independently before any bid decision.
Manual action remains: select the validated ordered lists in Unstop after reviewing
the provisional extras limitation.
"""
    EXECUTIVE_SUMMARY_PATH.write_text(summary_text, encoding="utf-8")

    source_text = f"""# SupeRR Selector Season 2 — Editable Methodology Source

## Executive summary and competition objective

The Round 1 brief asks for ordered Top-10 batter and bowler lists supported by a
reproducible pressure definition, fair sample/context treatment, evidence, and
limitations. This report analyzes {int(summary.delivery_records):,} deliveries,
{int(summary.delivery_matches):,} delivery-bearing matches, and 141 competitions,
with source seasons {summary.competition_seasons}.

## Dataset and data-integrity validation

Six source CSVs and the official two-page brief were reviewed. No field-level data
dictionary or extras specification was present. There are 883 source match rows,
867 with deliveries, 141 competition records, and 6,413 player mappings. Exact
delivery duplicates: 0; unmatched delivery match IDs: 0; unmapped role/team/player
combinations: 0. One player-name alias exists (ID 4458: `Aneurin Donald` versus
`AHT Donald`); all ranked identities match the map and ball records. Twelve rows
have a dismissed ID while `is_wicket` is false and are ignored for batter dismissal
counts. One `Retire Out` wicket lacks a dismissed player ID.

### Extras integrity

There are 36 rows with 84 nonzero `extras_2_runs`; another 265 `extras1_runs` are
tagged `other` or have a missing label. The combined 349 source runs are unallocated
for bowler charges. The primary state uses the source-component subtotal
`runs + extras1_runs`; an additive candidate includes `extras_2_runs` once.
The source does not establish whether the latter is part of innings totals or
bowler charges. Affected pressure states and bowling metrics remain provisional.
See `docs/EXTRAS_DATA_INTEGRITY_AUDIT.md`.

### Delivery rules and validation

- Batter balls faced exclude wides and standalone penalty events and include no-balls.
- Bowler legal balls exclude wides, no-balls, and penalty events.
- Byes/leg-byes are legal and faced, but not charged to the bowler.
- Dot balls require no team runs on the delivery; positive unresolved secondary runs
  are conservatively not counted as dots.
- Player dismissals use `dismissed_player_id`; run-outs, retirements, and obstruction
  are not bowler wickets. A source wicket without a dismissed ID remains unattributed.

## Pressure-state definition

Each state is reconstructed before the delivery using source `overid` and
`innings_ball_num` only for chronology. Prior score, wickets, wickets remaining,
legal balls, current run rate, target, required runs, and required rate are retained.
The current outcome never contributes to its own state. Revised limits are interpreted
as legal-ball limits because source values are multiples of six; two revised No Result
innings lack delivery records and are not imputed.

Let scheduled overs be `ceil(limit_legal_balls / 6)`. The late-over window starts at
`floor(0.80 × scheduled_overs) + 1`; the endgame is the final `ceil(0.10 × limit)`
legal balls. A death over alone is not pressure.

- Chase with runs remaining: pressure if pre-ball required rate ≥10, at least five
  wickets have fallen, the innings is in the endgame, or it is a late over with
  required rate ≥8 or at least three wickets fallen.
- First innings: pressure if it is in the late-over window and either five wickets
  have fallen or the endgame has begun.
- IPL, T20I, and other T20 contexts are summarized separately; only IPL/T20I feed
  the combined score.

## Batting and bowling performance

Batters are measured by pressure strike rate, boundary rate, zero-team-run delivery
avoidance, and dismissal avoidance. Rates use batter balls faced; dismissals use the
actual dismissed player ID. Bowlers are measured by known-charge economy per legal
ball, wickets per six legal balls, and legal-ball dot rate. The bowler denominator
excludes wides/no-balls; unresolved charges are not silently allocated.

## Reliability and composite score

Within IPL and T20I separately, metric values are shrunk toward the same-context peer
median using `observed × n/(n+k) + median × k/(n+k)`. `k=60` balls, or four pressure
innings for dismissal avoidance. Percentiles use these shrunk values. Batter weights:
strike rate 35%, boundary rate 20%, dot avoidance 20%, dismissal avoidance 25%.
Bowler weights: known economy 40% (lower is better), wickets per six 35%, dot rate
25%. Dimensions appear once.

Match consistency is `1/(1+CV)` for per-match pressure strike rates/economies,
where `CV=population standard deviation / absolute mean`; fewer than two observations
or zero mean yields 0. Performance is shrunk toward neutral 0.5 with
`confidence=matches/(matches+4)`. Context score is 75% sample-adjusted performance
and 25% consistency. Final score is 70% IPL and 30% T20I; a missing context contributes
0.5 instead of receiving all weight. Other T20 competitions are excluded.
Separate IPL-only and T20I-only ranking CSVs use the corresponding context rating
and apply the same ball/match thresholds within that context.

## Final rankings

### Batters
{batting_md}

### Bowlers
{bowling_md}

## Conditional Rajasthan Royals scouting profiles

These are historical pressure profiles, not confirmed auction recommendations or
availability claims. Exact squad need, current role, contract, price, and auction
status are not in the supplied data.

### Batters
{chr(10).join(_player_recommendation_markdown(row, 'Batter') for row in batters.head(3).itertuples(index=False))}

### Bowlers
{chr(10).join(_player_recommendation_markdown(row, 'Bowler') for row in bowlers.head(3).itertuples(index=False))}

## Sensitivity and limitations

The primary performance/consistency weights are 75/25; alternatives are 85/15 and
60/40. Actual Top-10 overlap is calculated from player-ID intersections. An additive
`extras_2_runs` state is also compared with the source-component state. See the
packaged CSV outputs and the extras audit for exact values.

Limitations include undocumented extras semantics, inferred revised-limit units,
incomplete innings/source records, no opponent-strength or venue adjustment, no
current squad-role/availability/auction data, and no market-value model. Bowler
economy and affected pressure states/ranks are provisional pending supplier
clarification.
"""
    SOURCE_DOCUMENT_PATH.write_text(source_text, encoding="utf-8")


def build_report():
    batters = pd.read_csv(RANK_DIR / "top_10_batters.csv")
    bowlers = pd.read_csv(RANK_DIR / "top_10_bowlers.csv")
    context_rankings = {
        (role, context): pd.read_csv(
            RANK_DIR / f"top_10_{role}_{context.lower()}.csv"
        )
        for role in ("batters", "bowlers")
        for context in ("IPL", "T20I")
    }
    audit = pd.read_csv(TABLE_DIR / "data_audit.csv")
    integrity = pd.read_csv(TABLE_DIR / "source_integrity_audit.csv")
    competition = pd.read_csv(TABLE_DIR / "competition_performance_summary.csv")
    sensitivity = pd.read_csv(TABLE_DIR / "sensitivity_analysis.csv")
    summary = pd.read_csv(TABLE_DIR / "analysis_summary.csv").iloc[0]
    revised_audit = pd.read_csv(TABLE_DIR / "revised_innings_audit.csv")
    innings_audit = pd.read_csv(TABLE_DIR / "innings_totals_audit.csv")
    extras_audit = pd.read_csv(TABLE_DIR / "extras_semantics_audit.csv").iloc[0]
    for role, frame in (("batters", batters), ("bowlers", bowlers)):
        if (
            len(frame) != 10
            or frame["rank"].tolist() != list(range(1, 11))
            or not frame["player_id"].is_unique
        ):
            raise ValueError(f"{role} CSV must contain unique ordered ranks 1-10")
    for (role, context), frame in context_rankings.items():
        if (
            len(frame) != 10
            or frame["rank"].tolist() != list(range(1, 11))
            or not frame["player_id"].is_unique
            or not frame["competition_group"].eq(context).all()
        ):
            raise ValueError(f"{role} {context} CSV is not a unique context ranking")
        expected = 0.75 * frame["reliability_score"] + 0.25 * frame["consistency_score"]
        if (expected - frame["final_composite_score"]).abs().gt(1e-12).any():
            raise ValueError(f"{role} {context} scores do not match the context formula")
    for name in PACKAGE_CHART_NAMES:
        if not (CHART_DIR / name).is_file():
            raise FileNotFoundError(f"Required chart is missing: {CHART_DIR / name}")

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
    )
    story = [
        Spacer(1, 3 * cm),
        Paragraph("SupeRR Selector Season 2", styles["Title"]),
        Paragraph("Identifying the Most Reliable Players Under Pressure", styles["Heading2"]),
        Spacer(1, 0.8 * cm),
        Paragraph("Rajasthan Royals - IPL 2027 analytics context", styles["Heading3"]),
        Spacer(1, 0.6 * cm),
        Paragraph(
            "Methodology and ranking report · supplied historical ball-by-ball data",
            styles["Normal"],
        ),
        Spacer(1, 5 * cm),
        Paragraph(
            "Important: the primary score state uses runs + extras1_runs. The supplier "
            "has not defined extras_2_runs or other extras; 349 source runs are unallocated "
            "for bowler charges. Pressure flags and bowling metrics remain provisional.",
            styles["SmallAudit"],
        ),
        PageBreak(),
    ]

    story.extend([
        Paragraph("1. Competition Objective and Executive Summary", styles["Heading1"]),
        Paragraph(
            "The official Round 1 brief requires ordered Top 10 batter and bowler lists "
            "supported by a transparent, reproducible methodology. It leaves the pressure "
            "definition to the entrant and asks for fair handling of sample size, format "
            "context, evidence, reliability, and limitations.",
            styles["Normal"],
        ),
        Paragraph(
            f"The pipeline reconstructed {int(summary.delivery_records):,} deliveries across "
            f"{int(summary.delivery_matches):,} matches with delivery state evaluated before each ball. "
            f"The data covers {int(summary.source_match_records)} source matches and "
            f"{int(summary.source_competitions)} competitions in seasons "
            f"{summary.competition_seasons}.",
            styles["Normal"],
        ),
        Paragraph(
            f"The final lists contain 10 unique players each from {len(batters)} eligible "
            f"batters and {len(bowlers)} eligible bowlers. Primary pressure sample: "
            f"{int(summary.pressure_delivery_records):,} deliveries across "
            f"{int(summary.pressure_match_count)} matches. Rankings use historical evidence "
            "only; no player is represented as currently available for IPL 2027.",
            styles["Normal"],
        ),
        Paragraph("Source table audit", styles["Heading2"]),
        _table(
            ["Dataset", "Rows", "Columns", "Missing cells", "Duplicate rows"],
            [
                [
                    str(row.dataset), str(int(row.rows)), str(int(row.columns)),
                    str(int(row.missing_cells)), str(int(row.duplicate_rows)),
                ]
                for row in audit.itertuples(index=False)
            ],
            [4.1 * cm, 2.2 * cm, 2.2 * cm, 3.0 * cm, 3.0 * cm],
        ),
        PageBreak(),
        Paragraph("2. Data Cleaning and Statistical Validation", styles["Heading1"]),
        Paragraph(
            "All six supplied CSVs were inspected. Delivery-to-match, match-to-competition, "
            "and player/team/competition relationships were checked. No source file was "
            "modified. The table below reports actual structural checks and source anomalies.",
            styles["Normal"],
        ),
        _table(
            ["Finding", "Count", "Audit treatment"],
            [
                [
                    str(row.finding), str(int(row.count)),
                    str(row.interpretation),
                ]
                for row in integrity.itertuples(index=False)
                if row.finding not in {"delivery_records", "delivery_matches", "source_matches", "source_competitions"}
            ],
            [5.0 * cm, 1.6 * cm, 9.0 * cm],
            font_size=6.5,
        ),
        Paragraph(
            "Source boundary flags are internally consistent with the runs field when present; "
            "20 four-run and three six-run rows have no boundary flag and are not inferred as "
            "batter boundaries.",
            styles["SmallAudit"],
        ),
        Paragraph("Extras and innings-total scenario audit", styles["Heading2"]),
        _table(
            ["Measure", "Observed", "Interpretation"],
            [
                ["Nonzero extras_2_runs", f"{int(extras_audit.nonzero_extras_2_rows)} rows / {int(extras_audit.extras_2_run_total)} runs", "Meaning and charge recipient undocumented"],
                ["Other/missing extras1", f"{int(extras_audit.extras1_other_or_missing_rows)} rows / {int(extras_audit.extras1_other_or_missing_total)} runs", "Not allocated to bowler"],
                ["All unallocated bowler runs", str(int(extras_audit.bowler_unallocated_extra_runs)), "Known-charge economy is provisional"],
                ["Uncertain pre-delivery states", f"{int(extras_audit.pressure_state_uncertain_deliveries):,} deliveries", f"{int(extras_audit.pressure_state_uncertain_matches)} matches affected"],
                ["Pressure flags changed by scenario", str(int(extras_audit.pressure_flags_differ_by_total_scenario)), f"{int(extras_audit.source_subtotal_only_pressure_flags)} source-only; {int(extras_audit.additive_candidate_only_pressure_flags)} additive-only"],
                ["Top-10 overlap, alternate totals", f"Batters {int(extras_audit.batter_top_10_overlap_with_additive_candidate)}/10; bowlers {int(extras_audit.bowler_top_10_overlap_with_additive_candidate)}/10", "Sensitivity, not proof of field meaning"],
                ["Revised innings with no deliveries", str(int(summary.revised_innings_without_ball_records)), "No Result innings; no rows imputed"],
                ["Innings totals audited", str(len(innings_audit)), "Source subtotal and additive candidate retained separately"],
            ],
            [4.1 * cm, 3.2 * cm, 7.8 * cm],
            font_size=6.5,
        ),
        PageBreak(),
        Paragraph("3. Pressure State Reconstruction", styles["Heading1"]),
        Paragraph(
            "Deliveries are ordered by match, innings, and source innings_ball_num. "
            "The over comes from source overid. For each row, prior runs, prior wickets, "
            "and prior legal balls are cumulative totals shifted by one delivery. The current "
            "delivery's outcome never contributes to its own pressure state.",
            styles["Normal"],
        ),
        Paragraph(
            "Scheduled length is 120 legal balls unless the match has a revised limit. "
            "Observed revised-limit values are whole multiples of six (30-114); they are "
            "treated as legal-ball counts. This unit is empirically inferred because no "
            "field-level dictionary was supplied. Innings 3/4 are treated as six-ball "
            "super overs.",
            styles["Normal"],
        ),
        Paragraph(
            f"The source contains {int(summary.first_revised_limit_count)} first-innings and "
            f"{int(summary.second_revised_limit_count)} second-innings revised-limit values. "
            f"{int(summary.revised_innings_without_ball_records)} revised innings have no "
            "delivery records; these no-result innings are listed in the revised-innings audit "
            "and are not reconstructed or imputed.",
            styles["SmallAudit"],
        ),
        Paragraph(
            "A death over alone is not pressure. The late-over window starts at "
            "floor(0.80 x scheduled overs) + 1. The endgame is the final ceil(0.10 x "
            "scheduled legal balls). In a chase, while runs remain, pre-ball pressure is "
            "required rate >=10, five wickets lost, the endgame, or a late over with rate >=8 "
            "or three wickets lost. In a first innings, the late-over window must coincide "
            "with five wickets lost or the endgame. This shared match-state label is measured "
            "with separate role-specific batting and bowling metrics.",
            styles["Normal"],
        ),
        Paragraph(
            "The primary state uses the source-component subtotal runs + extras1_runs. "
            "An additive extras_2_runs candidate is calculated separately; states affected "
            "after prior secondary extras are flagged. The source revised_target is treated "
            "as the score to reach based on observed chase totals; absent a source target, "
            "the first-innings source-component subtotal + 1 is used. Each innings is labeled "
            "all out, target reached, scheduled balls completed, or incomplete/interrupted.",
            styles["Normal"],
        ),
        PageBreak(),
        Paragraph("4. Batting Analytics", styles["Heading1"]),
        Paragraph(
            "Batter runs use the source `runs` field. Balls faced exclude wides and standalone "
            "penalty events but include no-balls, byes, leg-byes, and ordinary deliveries. "
            "Strike rate is `100 x batter runs / balls faced`. Boundary rates use the source "
            "`is_four` and `is_six` flags; no boundary is inferred from four/six source runs "
            "when the source flag is false.",
            styles["Normal"],
        ),
        Paragraph(
            "A batting dot is a faced delivery with no team runs in the additive candidate "
            "components. A no-ball with an extra, a bye/leg-bye scoring event, or a delivery "
            "with positive unresolved secondary runs is not counted as a dot. Dismissal "
            "avoidance and runs per dismissal use `dismissed_player_id`, not the striker by "
            "default. The single source wicket lacking a dismissed ID is not assigned to a player.",
            styles["Normal"],
        ),
        Paragraph(
            "Pressure batting dimensions are normalized separately within IPL and T20I. "
            "Source-component batter runs and balls faced are independent of bowler-charge "
            "allocation, but pressure-sample membership can be affected by the unresolved "
            "secondary run field.",
            styles["Normal"],
        ),
        PageBreak(),
        Paragraph("5. Bowling Analytics", styles["Heading1"]),
        Paragraph(
            "Bowler legal balls exclude wides, no-balls, and standalone penalty events. "
            "Byes and leg-byes count as legal deliveries, but their runs are not charged to "
            "the bowler. Known runs include source batter runs plus explicit `wide`/`Overstep` "
            "extras1 charges. Economy is `6 x known charges / legal balls` and is a known-charge "
            "estimate, not a reconciled scorecard economy.",
            styles["Normal"],
        ),
        Paragraph(
            "Bowler dot rate counts legal deliveries with no team runs in the candidate "
            "components; it does not count byes/leg-byes or unresolved positive-run deliveries "
            "as dots. Wickets per six legal balls use `is_bowling_wicket`; run-outs, Retire Out, "
            "and obstruction are not credited to the bowler. `extras_2_runs` and `other` extras "
            "are left unallocated. There are 349 such source runs, so economy, dot rate on "
            "affected events, and bowling ranks remain provisional.",
            styles["Normal"],
        ),
        PageBreak(),
        Paragraph("6. Reliability Scoring Framework", styles["Heading1"]),
        Paragraph("Batter dimensions (percentile-normalized within IPL or T20I):", styles["Heading2"]),
        _table(
            ["Dimension", "Weight", "Direction"],
            [
                ["Pressure strike rate (runs / balls faced x 100)", "35%", "Higher"],
                ["Boundary rate (4s + 6s / balls faced)", "20%", "Higher"],
                ["Dot-ball avoidance", "20%", "Higher"],
                ["Dismissal avoidance by actual dismissed_player_id", "25%", "Higher"],
            ],
            [9 * cm, 2.5 * cm, 3 * cm],
        ),
        Spacer(1, 0.35 * cm),
        Paragraph("Bowler dimensions:", styles["Heading2"]),
        _table(
            ["Dimension", "Weight", "Direction"],
            [
                ["Known-charge economy (known runs / legal balls x 6)", "40%", "Lower"],
                ["Wickets per six legal balls", "35%", "Higher"],
                ["Legal-ball dot rate", "25%", "Higher"],
            ],
            [9 * cm, 2.5 * cm, 3 * cm],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Each rate is shrunk toward the same-context peer median using "
            "`observed x n/(n+k) + median x k/(n+k)`: k=60 balls (four pressure innings "
            "for dismissal avoidance). Percentiles are then calculated within context. "
            "Match consistency is `1/(1+CV)` on match pressure strike rates/economies; "
            "CV is population standard deviation divided by absolute mean.",
            styles["SmallAudit"],
        ),
        PageBreak(),
        Paragraph("7. Competition Context and Eligibility", styles["Heading1"]),
        Paragraph(
            "IPL and T20I are scored separately. Other T20 competitions are summarized but "
            "excluded from rankings. Context ratings use IPL 70% and T20I 30%; a missing "
            "context contributes neutral 0.5 rather than giving the available context full weight. "
            "This is an explicit IPL-prioritizing decision for the Rajasthan Royals use case, "
            "not a claim that the formats are equivalent.",
            styles["Normal"],
        ),
        Paragraph(
            "Context performance is blended toward neutral 0.5 with confidence "
            "`pressure_matches/(pressure_matches+4)`. Context rating is 75% sample-adjusted "
            "performance and 25% match consistency. Eligibility requires 30 pressure balls "
            "faced and four matches for batters; 24 pressure legal balls and four matches "
            "for bowlers. Separate IPL-only and T20I-only Top 10 CSVs rank players within "
            "each context using that context's rating and minimum sample threshold.",
            styles["Normal"],
        ),
        Paragraph("Pressure performance by competition", styles["Heading2"]),
        _table(
            ["Context", "Format", "Matches", "Deliveries", "Batter SR", "Known bowler econ", "Unallocated"],
            [
                [
                    str(row.competition_group), str(row.match_format),
                    str(int(row.pressure_matches)), str(int(row.pressure_deliveries)),
                    _display(row.pressure_batter_strike_rate),
                    _display(row.pressure_bowler_economy_known),
                    str(int(row.unallocated_bowler_extras)),
                ]
                for row in competition.itertuples(index=False)
            ],
            [2.4 * cm, 1.6 * cm, 1.6 * cm, 2 * cm, 2.3 * cm, 3.2 * cm, 2 * cm],
            font_size=6.5,
        ),
        Paragraph(
            "Sensitivity is recalculated at performance/consistency weights 75/25 (primary), "
            "85/15, and 60/40. The overlap table is derived from player-ID intersections of "
            "the actual scenario rankings.",
            styles["SmallAudit"],
        ),
        PageBreak(),
        Paragraph("8. Top 10 Batters Under Pressure", styles["Heading1"]),
    ])
    batter_rows = []
    for row in batters.itertuples(index=False):
        batter_rows.append([
            str(int(row.rank)), str(row.player_name), str(int(row.player_id)),
            _short(row.team_context, 28), _short(row.competition_context, 29),
            str(int(row.pressure_opportunities)), str(int(row.pressure_balls)),
            str(int(row.pressure_runs)), _display(row.pressure_strike_rate),
            _display(row.consistency_score, 3), _display(row.final_composite_score, 4),
        ])
    story.extend([
        _table(
            ["#", "Player", "ID", "Teams", "Competitions", "Matches", "BF", "Runs", "SR", "Cons.", "Score"],
            batter_rows,
            [0.7 * cm, 2.6 * cm, 1.1 * cm, 2.5 * cm, 3.4 * cm, 1.1 * cm, 0.9 * cm, 1 * cm, 1.1 * cm, 1.1 * cm, 1.2 * cm],
            font_size=5.8,
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Team and competition columns list the historical contexts represented in pressure "
            "deliveries; they do not imply current contracts or auction availability.",
            styles["SmallAudit"],
        ),
        PageBreak(),
        Paragraph("9. Top 10 Bowlers Under Pressure", styles["Heading1"]),
    ])
    bowler_rows = []
    for row in bowlers.itertuples(index=False):
        bowler_rows.append([
            str(int(row.rank)), str(row.player_name), str(int(row.player_id)),
            _short(row.team_context, 24), _short(row.competition_context, 25),
            str(int(row.pressure_opportunities)), str(int(row.pressure_legal_balls)),
            str(int(row.pressure_runs_conceded_known)),
            str(int(row.unallocated_pressure_extras)), str(int(row.wickets)),
            _display(row.pressure_economy_known), _display(row.final_composite_score, 4),
        ])
    story.extend([
        _table(
            ["#", "Player", "ID", "Teams", "Competitions", "Matches", "Legal", "Known runs", "Unalloc.", "Wkts", "Econ*", "Score"],
            bowler_rows,
            [0.7 * cm, 2.5 * cm, 1.05 * cm, 2.2 * cm, 3 * cm, 1 * cm, 1 * cm, 1.5 * cm, 1.1 * cm, 0.8 * cm, 1 * cm, 1.1 * cm],
            font_size=5.6,
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "*Known-charge economy estimate; see extras limitation. Rankings are not fully "
            "verifiable until the provider documents `extras_2_runs` and `other` extras.",
            styles["SmallAudit"],
        ),
        PageBreak(),
        Paragraph("10. Conditional Rajasthan Royals Scouting Profiles", styles["Heading1"]),
        Paragraph(
            "The following are historical analytical profiles among the highest-ranked "
            "players, not claims about current squad gaps, official playing roles, availability, "
            "contract, price, or auction interest. A role fit is an inference from observed "
            "pressure output and should be checked against current team strategy.",
            styles["Normal"],
        ),
        Paragraph("Batting profiles", styles["Heading2"]),
    ])
    for row in batters.head(3).itertuples(index=False):
        story.append(Paragraph(
            f"<b>{row.player_name} (ID {int(row.player_id)}) - potential pressure "
            f"run-acceleration profile.</b> Overall evidence: {row.selection_justification} "
            f"IPL pressure sample: {int(row.ipl_pressure_matches)} matches, "
            f"{int(row.ipl_pressure_balls)} balls faced, SR {_display(row.ipl_pressure_strike_rate)}; "
            f"consistency {_display(row.consistency_score, 3)}, reliability "
            f"{_display(row.reliability_score, 3)}. This supports a run-acceleration scouting "
            "discussion, not a confirmed batting slot. Pressure-state uncertainty and current "
            "availability remain to be checked.",
            styles["Normal"],
        ))
    story.append(Paragraph("Bowling profiles", styles["Heading2"]))
    for row in bowlers.head(3).itertuples(index=False):
        story.append(Paragraph(
            f"<b>{row.player_name} (ID {int(row.player_id)}) - potential pressure "
            f"wicket-taking/run-prevention profile.</b> IPL pressure sample: "
            f"{int(row.ipl_pressure_matches)} matches, {int(row.ipl_pressure_legal_balls)} "
            f"legal balls, {int(row.ipl_wickets)} wickets, known-charge economy "
            f"{_display(row.ipl_pressure_economy_known)}; overall known-charge economy "
            f"{_display(row.pressure_economy_known)}. Consistency "
            f"{_display(row.consistency_score, 3)}, reliability "
            f"{_display(row.reliability_score, 3)}. Economy and dot rates remain provisional "
            "because of unresolved extras; current role and availability are not verified.",
            styles["Normal"],
        ))
    story.extend([
        Paragraph(
            "The supplied data has no current squad composition, role requirements, contract, "
            "auction pool, price, or availability fields. These profiles prioritize IPL-relevant "
            "evidence but are not an auction purchase list.",
            styles["SmallAudit"],
        ),
        PageBreak(),
        Paragraph("11. Visual Evidence", styles["Heading1"]),
        Image(str(CHART_DIR / "top_10_pressure_batters.png"), width=17 * cm, height=8.5 * cm),
        Spacer(1, 0.3 * cm),
        Image(str(CHART_DIR / "top_10_pressure_bowlers.png"), width=17 * cm, height=8.5 * cm),
        PageBreak(),
        Paragraph("12. IPL Pressure vs Usual Performance", styles["Heading1"]),
        Paragraph(
            "The following comparisons use IPL-only records for each listed player. "
            "Usual performance is measured on non-pressure deliveries; pressure performance "
            "uses the pre-delivery pressure state defined above. Batting uses strike rate "
            "per batter ball faced. Bowling uses known-charge economy per legal ball and "
            "remains subject to the extras limitation.",
            styles["Normal"],
        ),
        Image(str(CHART_DIR / "normal_vs_pressure_batters.png"), width=17 * cm, height=8.2 * cm),
        Spacer(1, 0.25 * cm),
        Image(str(CHART_DIR / "normal_vs_pressure_bowlers.png"), width=17 * cm, height=8.2 * cm),
        PageBreak(),
        Paragraph("13. Consistency and Reliability", styles["Heading1"]),
        Image(str(CHART_DIR / "consistency_comparison.png"), width=17 * cm, height=7.5 * cm),
        Spacer(1, 0.2 * cm),
        Image(str(CHART_DIR / "reliability_score_comparison.png"), width=17 * cm, height=7.5 * cm),
        PageBreak(),
        Paragraph("14. Sensitivity, Limitations, and Conclusion", styles["Heading1"]),
        Image(str(CHART_DIR / "sensitivity_analysis.png"), width=16 * cm, height=7 * cm),
        _table(
            ["Role", "Scenario", "Perf.", "Cons.", "Top-10 overlap", "Rate"],
            [
                [
                    str(row.role), str(row.scenario),
                    _display(row.performance_weight, 2), _display(row.consistency_weight, 2),
                    str(int(row.primary_top_10_overlap_count)),
                    _display(row.primary_top_10_overlap_rate, 2),
                ]
                for row in sensitivity.itertuples(index=False)
            ],
            [2.3 * cm, 3.3 * cm, 1.7 * cm, 1.7 * cm, 3.3 * cm, 1.7 * cm],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "Limitations: no official field dictionary; bowler extras remain partially "
            "unallocated; revised-limit units are inferred from source values; no opposition "
            "strength, venue, role, injury, contract, availability, or auction-market data "
            "are modeled. Historical team context is not current squad status. No player is "
            "claimed to be available for IPL 2027.",
            styles["SmallAudit"],
        ),
        Paragraph(
            "Conclusion: the lists are reproducible under the explicitly stated primary "
            "source-component assumptions and provide pressure/performance evidence for the "
            "competition. They are not fully supplier-validated scorecard rankings until the "
            "provider clarifies extras_2_runs and other extras. The separate sensitivity "
            "analysis shows where those assumptions change match-state flags or rank membership.",
            styles["Normal"],
        ),
        Paragraph(
            "Reproduce in PowerShell: activate `venv`, run `python run_analysis.py`, "
            "`python -m pytest -q`, then `python generate_report.py`. The PDF rankings are "
            "validated against the generated CSVs; source CSV files are unchanged.",
            styles["SmallAudit"],
        ),
    ])
    doc.build(story)
    _validate_pdf(PDF_PATH, batters, bowlers)
    _write_submission_package(batters, bowlers, summary, sensitivity, extras_audit)
    print(PDF_PATH)


def _validate_pdf(path, batters, bowlers):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted or not reader.pages:
        raise ValueError(f"Generated PDF cannot be opened: {path}")
    if not 10 <= len(reader.pages) <= 15:
        raise ValueError(f"Expected a 10-15 page report, found {len(reader.pages)} pages")
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    required_sections = [
        "Pressure State Reconstruction",
        "Batting Analytics",
        "Bowling Analytics",
        "Reliability Scoring Framework",
        "Competition Context and Eligibility",
        "Top 10 Batters Under Pressure",
        "Top 10 Bowlers Under Pressure",
        "Conditional Rajasthan Royals Scouting Profiles",
        "Visual Evidence",
        "IPL Pressure vs Usual Performance",
        "Consistency and Reliability",
        "Sensitivity, Limitations, and Conclusion",
    ]
    missing = [section for section in required_sections if section not in text]
    if missing:
        raise ValueError(f"Generated PDF is missing required sections: {missing}")
    ranking_sections = (
        ("batter", batters, "8. Top 10 Batters Under Pressure", "9. Top 10 Bowlers Under Pressure"),
        ("bowler", bowlers, "9. Top 10 Bowlers Under Pressure", "10. Conditional Rajasthan Royals Scouting Profiles"),
    )
    for role, frame, heading, next_heading in ranking_sections:
        start = text.find(heading)
        end = text.find(next_heading, start + len(heading))
        section = text[start:end]
        cursor = 0
        rows = list(frame.itertuples(index=False))
        for index, row in enumerate(rows):
            name = str(row.player_name)
            name_position = section.find(name, cursor)
            if name_position < 0:
                raise ValueError(f"PDF {role} order does not match the CSV at rank {row.rank}")
            next_position = len(section)
            if index + 1 < len(rows):
                next_position = section.find(str(rows[index + 1].player_name), name_position + len(name))
                if next_position < 0:
                    raise ValueError(f"PDF is missing the next {role} ranking row")
            row_text = section[name_position:next_position]
            score = f"{float(row.final_composite_score):.4f}"
            if str(int(row.player_id)) not in row_text or score not in row_text:
                raise ValueError(
                    f"PDF {role} rank {row.rank} identity/score does not match the CSV"
                )
            cursor = next_position


if __name__ == "__main__":
    build_report()
