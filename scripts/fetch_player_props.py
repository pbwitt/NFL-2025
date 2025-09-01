#!/usr/bin/env python3
# scripts/fetch_player_props.py
import os, sys, time, pathlib, json
import pandas as pd
import requests as rq

SPORT = "americanfootball_nfl"
MARKETS = ["player_pass_yds"]  # add more later (player_reception_yds, etc.)
REGIONS = "us"
ODDS_FMT = "american"

API_KEY = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
BASE = "https://api.the-odds-api.com/v4"

OUT_DIR = pathlib.Path("data/props")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def get(url, params):
    params = dict(params, apiKey=API_KEY)
    r = rq.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    if not API_KEY:
        print("Missing ODDS_API_KEY env var.", file=sys.stderr)
        sys.exit(2)

    # Use your existing odds list to get event/game ids
    odds_latest = pathlib.Path("data/odds/latest.csv")
    if not odds_latest.exists():
        print("Missing data/odds/latest.csv. Run: make odds", file=sys.stderr)
        sys.exit(2)
    games = pd.read_csv(odds_latest, low_memory=False)[
        ["game_id","commence_time","home_team","away_team"]
    ].drop_duplicates()

    rows = []
    for i, ev in games.iterrows():
        event_id = ev["game_id"]
        url = f"{BASE}/sports/{SPORT}/events/{event_id}/odds"
        try:
            js = get(url, {
                "regions": REGIONS,
                "oddsFormat": ODDS_FMT,
                "markets": ",".join(MARKETS),
            })
        except rq.HTTPError as e:
            # 404 is common if no props yet; skip silently
            if e.response is not None and e.response.status_code == 404:
                continue
            raise

        for bk in js.get("bookmakers", []):
            bk_title = bk.get("title") or bk.get("key")
            for m in bk.get("markets", []):
                mkey = m.get("key")
                if mkey not in MARKETS:
                    continue
                for oc in m.get("outcomes", []):
                    # Player name is provided in "description" for player props
                    player = oc.get("description") or oc.get("participant") or ""
                    side = oc.get("name")  # Over / Under
                    price = oc.get("price")
                    point = oc.get("point")
                    rows.append({
                        "game_id": event_id,
                        "commence_time": ev["commence_time"],
                        "home_team": ev["home_team"],
                        "away_team": ev["away_team"],
                        "bookmaker": bk_title,
                        "market": mkey,
                        "player": player,
                        "name": side,
                        "price": price,
                        "point": point,
                    })
        # polite pacing
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    out_csv = OUT_DIR / "latest_player_pass_yds.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} with {len(df):,} rows across {games.shape[0]} events")

if __name__ == "__main__":
    main()
