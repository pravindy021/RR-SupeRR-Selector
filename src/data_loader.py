from pathlib import Path
import pandas as pd


DATA_NAMES = (
    "ball_by_ball.csv",
    "competitions.csv",
    "competition_team_player_mapping.csv",
    "matches.csv",
    "playing_eleven.csv",
    "teams.csv",
)


def load_data(data_dir):
    data_dir = Path(data_dir)
    data = {}
    for name in DATA_NAMES:
        path = data_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing required source file: {path}")
        data[name[:-4]] = pd.read_csv(path)
    return data


def audit_data(data):
    rows = []
    for name, frame in data.items():
        missing = int(frame.isna().sum().sum())
        duplicates = int(frame.duplicated().sum())
        rows.append({
            "dataset": name,
            "rows": len(frame),
            "columns": len(frame.columns),
            "missing_cells": missing,
            "duplicate_rows": duplicates,
        })
    return pd.DataFrame(rows)
