#!/usr/bin/env python3
# scripts/fetch_all_player_props.py
import os, sys, time, pathlib
import pandas as pd
import requests as rq

SPORT   = "americanfootball_nfl"
REGIONS = "us"
ODDSFMT = "american"
API_KEY = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
BASE    = "https://api.the-odds-api.com/v4"

# NFL player prop markets (add/remove as you like)
MARKETS = [
    "player_pass_yds","player_pass_tds","player_pass_attempts","player_pass_completions","player_pass_interceptions",
    "player_receptions","player_reception_yds","player_reception_tds",
    "player_rush_yds","player_rush_attempts","player_rush_tds",
    "player_field_goals","player_kicking_points",
    "player_sacks","player_solo_tackles","player_tackles_assists",
    "player_anytime_td"
]

OUT_DIR = pathlib.Path("data/props"); OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "latest_all_props.csv"

def j(url, params):
    r = rq.get(url, params={**params, "apiKey": API_KEY}, timeout=30)
    if r.status_code == 404:  # no props for this game yet
        return None
    r.raise_for_status()
    return r.json()

def main():
    if not API_KEY:
        print("Missing ODDS_API_KEY (or THE_ODDS_API_KEY).", file=sys.stderr)
        sys.exit(2)
    odds_latest = pathlib.Path("data/odds/latest.csv")
    if not odds_latest.exists():
        print("Missing data/odds/latest.csv. Run: make odds", file=sys.stderr)
        sys.exit(2)

    games = pd.read_csv(odds_latest, low_memory=False)[["game_id","commence_time","home_team","away_team"]].drop_duplicates()
    rows = []
    for _, g in games.iterrows():
        event_id = g["game_id"]
        url = f"{BASE}/sports/{SPORT}/events/{event_id}/odds"
        data = j(url, {"regions": REGIONS, "oddsFormat": ODDSFMT, "markets": ",".join(MARKETS)})
        if not data:
            time.sleep(0.2);
            continue
        for bk in data.get("bookmakers", []):
            btitle = bk.get("title") or bk.get("key")
            for m in bk.get("markets", []):
                mkey = m.get("key")
                for oc in m.get("outcomes", []):
                    rows.append({
                        "game_id": g["game_id"],
                        "commence_time": g["commence_time"],
                        "home_team": g["home_team"],
                        "away_team": g["away_team"],
                        "bookmaker": btitle,
                        "market": mkey,
                        "player": oc.get("description") or oc.get("participant") or "",
                        "name": oc.get("name"),   # Over / Under OR Yes / No
                        "price": oc.get("price"),
                        "point": oc.get("point")
                    })
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT} with {len(df):,} rows across {games.shape[0]} events")

if __name__ == "__main__":
    main()
