import pandas as pd


def filter_rankings(rankings, context="All", teams=None, player_query=""):
    filtered = rankings.copy()
    if context == "IPL":
        filtered = filtered[filtered["ipl_pressure_matches"].fillna(0).gt(0)]
    elif context == "T20I":
        filtered = filtered[filtered["t20i_pressure_matches"].fillna(0).gt(0)]
    elif context != "All":
        raise ValueError(f"Unknown competition context: {context}")

    if teams:
        selected = set(teams)
        filtered = filtered[
            filtered["team_context"].fillna("").map(
                lambda value: bool(selected.intersection(value.split("; ")))
            )
        ]
    query = player_query.strip().casefold()
    if query:
        filtered = filtered[
            filtered["player_name"].astype(str).str.casefold().str.contains(
                query, regex=False
            )
        ]
    return filtered.reset_index(drop=True)


def compare_players(rankings, player_names):
    selected = set(player_names)
    if not selected:
        return rankings.iloc[0:0].copy()
    return rankings[rankings["player_name"].isin(selected)].copy()


def rankings_csv_bytes(rankings):
    return rankings.to_csv(index=False).encode("utf-8")
