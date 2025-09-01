# scripts/fetch_odds.py
import os, sys, json, pathlib, datetime, time
import argparse
import requests
import pandas as pd

API_BASE = "https://api.the-odds-api.com/v4/sports"

def get_args():
    p = argparse.ArgumentParser(description="Fetch NFL odds and save normalized tables.")
    p.add_argument("--markets", default="h2h,spreads,totals", help="Comma list of markets")
    p.add_argument("--regions", default="us", help="us,us2,uk,eu,au")
    p.add_argument("--odds-format", default="american", choices=["american","decimal"])
    p.add_argument("--sport-key", default="americanfootball_nfl")
    p.add_argument("--outdir", default="data/odds")
    p.add_argument("--bookmakers", default=None, help="Optional comma list to restrict books")
    p.add_argument("--sleep", type=float, default=1.0, help="Sleep between calls (s)")
    return p.parse_args()

def fetch_odds(sport_key, markets, regions, odds_format, bookmakers=None):
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        sys.exit("Missing ODDS_API_KEY in environment")

    params = {
        "apiKey": api_key,
        "markets": markets,
        "regions": regions,
        "oddsFormat": odds_format,
        "dateFormat": "iso"
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"{API_BASE}/{sport_key}/odds"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def normalize(games_json):
    # Flatten JSON -> tidy rows
    recs = []
    for g in games_json:
        game_id = g["id"]
        commence_time = g["commence_time"]
        home = g.get("home_team")
        away = g.get("away_team")
        for bm in g.get("bookmakers", []):
            bookmaker = bm["key"]
            last_update = bm.get("last_update")
            for mk in bm.get("markets", []):
                market = mk["key"]  # h2h | spreads | totals | outrights...
                for out in mk.get("outcomes", []):
                    recs.append({
                        "game_id": game_id,
                        "commence_time": commence_time,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker": bookmaker,
                        "last_update": last_update,
                        "market": market,
                        "name": out.get("name"),          # team or Over/Under
                        "price": out.get("price"),
                        "point": out.get("point")          # spread or total line
                    })
    df = pd.DataFrame.from_records(recs)
    # Derive simple keys helpful for joins
    if not df.empty:
        df["event_date"] = pd.to_datetime(df["commence_time"]).dt.date
        # Normalize team strings
        for col in ["home_team","away_team","name"]:
            df[col] = df[col].astype(str).str.strip()
    return df

def main():
    args = get_args()
    games = fetch_odds(args.sport_key, args.markets, args.regions, args.odds_format, args.bookmakers)
    df = normalize(games)

    outdir = pathlib.Path(args.outdir) / datetime.date.today().isoformat()
    outdir.mkdir(parents=True, exist_ok=True)

    parquet_path = outdir / "odds.parquet"
    csv_latest = pathlib.Path(args.outdir) / "latest.csv"

    if df.empty:
        print("No odds returned; nothing written.")
        return

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_latest, index=False)
    print(f"Wrote {parquet_path} and {csv_latest}")
    print(f"Rows: {len(df)} | Games: {df['game_id'].nunique()} | Books: {df['bookmaker'].nunique()}")

if __name__ == "__main__":
    main()
