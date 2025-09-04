#!/usr/bin/env python3
# scripts/make_predictions_from_elo.py
import argparse, pathlib
import pandas as pd
import numpy as np
# --- odds loader that accepts JSON array or CSV ---
import json, pathlib, pandas as pd, sys

def load_odds(path: str) -> pd.DataFrame:
    p = pathlib.Path(path)
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        raise SystemExit(f"odds file is empty: {path}")
    # Drop any `[info]` lines if present
    if "[info]" in txt:
        txt = "\n".join(ln for ln in txt.splitlines() if not ln.startswith("[info]")).strip()
    # JSON array from The Odds API → flatten to games
    if txt.startswith("["):
        try:
            arr = json.loads(txt)
        except json.JSONDecodeError as e:
            raise SystemExit(f"failed to parse JSON odds: {e}")
        rows = []
        for g in arr:
            rows.append({
                "game_id": g.get("id") or g.get("event_id"),
                "commence_time": g.get("commence_time"),
                "home_team": g.get("home_team"),
                "away_team": g.get("away_team"),
            })
        return pd.DataFrame(rows)
    # Else assume CSV
    try:
        return pd.read_csv(p)
    except Exception as e:
        raise SystemExit(f"failed to read CSV odds: {e}")

# Normalize a few common bookmaker name variants to full team names
NAME_FIX = {
    "LA Chargers": "Los Angeles Chargers",
    "LA Rams": "Los Angeles Rams",
    # add more if you see mismatches in your odds file
}

# Map full team name -> abbreviation used in Elo table
TEAM_MAP = {
    "Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF",
    "Carolina Panthers":"CAR","Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE",
    "Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET","Green Bay Packers":"GB",
    "Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC",
    "Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LAR","Miami Dolphins":"MIA",
    "Minnesota Vikings":"MIN","New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG",
    "New York Jets":"NYJ","Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF",
    "Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN","Washington Commanders":"WAS"
}

def elo_wp(home_elo, away_elo, hfa=55.0):
    return 1.0 / (1.0 + 10 ** ( -(((home_elo + hfa) - away_elo) / 400.0) ))

def main():
    ap = argparse.ArgumentParser(description="Make Week-1 predictions from 2024 Elo and odds matchups.")
    ap.add_argument("--elo", default="data/models/elo_2024.csv")
    ap.add_argument("--odds", default="data/odds/latest.csv")
    ap.add_argument("--out",  default="data/predictions/latest_predictions.csv")
    args = ap.parse_args()

    # Load Elo table (abbr -> rating)
    elos = pd.read_csv(args.elo)
    elo_map = dict(zip(elos["team"], elos["elo_2024_final"]))

    # Load unique games from odds
    odds = load_odds(args.odds)
    required = ["game_id","commence_time","home_team","away_team"]
    missing = [c for c in required if c not in odds.columns]
    if missing:
        raise SystemExit(f"Odds missing required columns: {missing}. Columns present: {list(odds.columns)} from {args.odds}")

    games = odds[["game_id","commence_time","home_team","away_team"]].drop_duplicates().copy()

    # Fix common short names
    games["home_team"] = games["home_team"].replace(NAME_FIX)
    games["away_team"] = games["away_team"].replace(NAME_FIX)

    # Map to abbreviations and attach Elo
    games["home_abbr"] = games["home_team"].map(TEAM_MAP)
    games["away_abbr"] = games["away_team"].map(TEAM_MAP)
    before = len(games)
    games = games.dropna(subset=["home_abbr","away_abbr"]).copy()
    if len(games) < before:
        print(f"Dropped {before - len(games)} games due to name mapping; update TEAM_MAP/NAME_FIX if needed.")

    games["home_elo"] = games["home_abbr"].map(elo_map).fillna(1500.0)
    games["away_elo"] = games["away_abbr"].map(elo_map).fillna(1500.0)

    # Win probabilities & a simple margin proxy from Elo diff
    games["home_win_prob"] = games.apply(lambda r: elo_wp(r["home_elo"], r["away_elo"]), axis=1)
    games["away_win_prob"] = 1.0 - games["home_win_prob"]
    elo_diff = (games["home_elo"] + 55.0) - games["away_elo"]
    games["pred_margin"] = elo_diff / 25.0  # rough points proxy

    # Build team-level prediction rows without losing home_team/away_team columns
    home_rows = games.copy()
    home_rows["team"] = home_rows["home_team"]
    home_rows["team_win_prob"] = home_rows["home_win_prob"]

    away_rows = games.copy()
    away_rows["team"] = away_rows["away_team"]
    away_rows["team_win_prob"] = away_rows["away_win_prob"]

    preds_cols = ["game_id","commence_time","home_team","away_team","team","team_win_prob","pred_margin"]
    preds = pd.concat([home_rows[preds_cols], away_rows[preds_cols]], ignore_index=True)

    pathlib.Path("data/predictions").mkdir(parents=True, exist_ok=True)
    preds.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(preds)} rows")

if __name__ == "__main__":
    main()
