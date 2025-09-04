# scripts/fetch_odds.py
import os, sys, argparse, requests

BASE = "https://api.the-odds-api.com/v4"

def fetch_odds(sport_key, markets, regions, odds_format, bookmakers, api_key):
    params = {
        "apiKey": api_key,
        "markets": markets,
        "regions": regions,
        "oddsFormat": odds_format,   # try "decimal" if you suspect format issues
        "dateFormat": "iso",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"{BASE}/sports/{sport_key}/odds"
    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        # >>> THIS IS THE IMPORTANT PART: show the server’s message
        print("[error]", r.status_code, r.reason)
        print(r.text)         # body includes {"message": "...", "error_code": "..."}
        sys.exit(1)

    return r.json()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport_key", default="americanfootball_nfl")
    ap.add_argument("--markets", default="h2h,spreads,totals")
    ap.add_argument("--regions", default="us")             # valid: us, uk, eu, au
    ap.add_argument("--odds_format", default="american")   # valid: american or decimal
    ap.add_argument("--bookmakers", default="")
    args = ap.parse_args()

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("ERROR: ODDS_API_KEY missing. Put it in .env or export it.")
        sys.exit(2)

    print("[info] using key:", api_key[:4], "...", api_key[-4:])
    games = fetch_odds(args.sport_key, args.markets, args.regions, args.odds_format, args.bookmakers, api_key)
    print("[ok] received", len(games), "games")

if __name__ == "__main__":
    main()
