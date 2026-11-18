# RR SupeRR Selector Season 2

Reproducible cricket pressure analytics pipeline for the Rajasthan Royals SupeRR Selector competition. The pressure reconstruction is pre-delivery and uses source `overid`, pre-ball legal balls, and observed revised innings limits.

## Setup (Windows PowerShell)

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_analysis.py
python -m pytest -q
python generate_report.py
python -m streamlit run dashboard/app.py
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

## Key outputs

- `outputs/rankings/top_10_batters.csv`
- `outputs/rankings/top_10_bowlers.csv`
- `outputs/rankings/top_10_batters_ipl.csv`
- `outputs/rankings/top_10_batters_t20i.csv`
- `outputs/rankings/top_10_bowlers_ipl.csv`
- `outputs/rankings/top_10_bowlers_t20i.csv`
- `outputs/rankings/combined_player_analysis.csv`
- `outputs/tables/competition_performance_summary.csv`
- `outputs/tables/sensitivity_analysis.csv`
- `outputs/charts/`
- `reports/final_submission/SupeRR_Selector_Season_2_Methodology_Report.pdf`
- `reports/final_submission/Methodology_Source.md`
- `reports/final_submission/Executive_Summary.md`
- `reports/final_submission/top_10_batters.csv`
- `reports/final_submission/top_10_bowlers.csv`
- `reports/final_submission/top_10_batters_ipl.csv`
- `reports/final_submission/top_10_batters_t20i.csv`
- `reports/final_submission/top_10_bowlers_ipl.csv`
- `reports/final_submission/top_10_bowlers_t20i.csv`
- `reports/final_submission/charts/`

The official brief is preserved at `data/RR_DATASETS/Data Pack/Round 1 Problem Statement _ SupeRR Selector Season 2.docx.pdf`.

## Important source-data limitation

The supplied pack has no field-level data dictionary. In particular, the meaning of `extras_2_runs` and `other` extras cannot be verified. Primary match state uses `runs + extras1_runs`; an additive `extras_2_runs` scenario is calculated separately, not treated as verified. A total of 349 source runs is not safely allocatable to bowlers, so known-charge economy, affected dot rates, pressure states, and related ranks remain provisional. See `docs/EXTRAS_DATA_INTEGRITY_AUDIT.md`, `docs/DATA_DICTIONARY.md`, and `docs/RANKING_METHODOLOGY.md`.

Rankings use IPL and T20I context scores at 70%/30%; other T20 competitions are summarized separately and excluded. A missing context is assigned a neutral score, not reweighted to full weight.
