#!/usr/bin/env python3
# scripts/build_elo_2024.py
"""
Build end-of-season Elo ratings from the completed 2024 NFL season.
Outputs: data/models/elo_2024.csv with columns [team, elo_2024_final]
"""

import math
import pathlib
import pandas as pd


def expected_home_win_prob(elo_home: float, elo_away: float, hfa: float = 55.0) -> float:
    """Elo win prob for the HOME team vs AWAY team."""
    return 1.0 / (1.0 + 10 ** (-((elo_home + hfa) - elo_away) / 400.0))


def main():
    # Lazy import so the script only requires nfl_data_py when you run it
    import nfl_data_py as nfl

    # 1) Load 2024 schedule/results. nfl_data_py returns team abbreviations (e.g., NYG, DAL).
    sched = nfl.import_schedules([2024])

    # Keep regular-season games with final scores present
    mask = (sched["game_type"] == "REG") & sched["home_score"].notna() & sched["away_score"].notna()
    games = sched.loc[mask].copy()

    if games.empty:
        raise SystemExit("No 2024 regular-season finals found. Is nfl_data_py up to date?")

    # 2) Team list (abbreviations)
    teams = sorted(set(games["home_team"]).union(set(games["away_team"])))
    elo = {t: 1500.0 for t in teams}

    # 3) Hyperparameters
    K = 20.0     # base update factor
    HFA = 55.0   # home-field advantage in Elo points

    # 4) Chronological order (prefer kickoff; fallback to any available date col)
    sort_cols = [c for c in ["kickoff", "gameday", "game_date", "start_time"] if c in games.columns]
    if sort_cols:
        games = games.sort_values(sort_cols[0])

    # 5) Iterate through games and update Elo
    for _, g in games.iterrows():
        home, away = str(g["home_team"]), str(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])

        # Expected result (home perspective)
        eh = expected_home_win_prob(elo[home], elo[away], HFA)

        # Actual result (home perspective)
        sh = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)

        # Margin-of-victory multiplier (soft cap)
        mov = abs(hs - as_)
        mult = math.log(max(mov, 1.0) + 1.0) * (2.2 / ((((elo[home] + HFA) - elo[away]) * 0.001) + 2.2))

        delta = K * mult * (sh - eh)
        elo[home] += delta
        elo[away] -= delta

    # 6) Save
    out_df = pd.DataFrame({"team": list(elo.keys()), "elo_2024_final": list(elo.values())})
    pathlib.Path("data/models").mkdir(parents=True, exist_ok=True)
    out_df.to_csv("data/models/elo_2024.csv", index=False)
    print("Wrote data/models/elo_2024.csv")
    print(out_df.sort_values("elo_2024_final", ascending=False).head(5))


if __name__ == "__main__":
    main()
