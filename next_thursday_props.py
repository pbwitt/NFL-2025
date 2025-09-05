# next_thursday_props.py
import os, sys, requests
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo  # py>=3.9
except Exception:
    ZoneInfo = None

API_KEY = os.getenv("ODDS_API_KEY", "bf91c7e54b4224b4e820e6e74f69aa33")
SPORT = "americanfootball_nfl"
REGION = "us"
MARKETS = "player_pass_yds,player_pass_tds,player_rush_yds,player_receptions"

def to_local(dt_utc_iso, tz="America/New_York"):
    dt_utc = datetime.fromisoformat(dt_utc_iso.replace("Z","+00:00")).astimezone(timezone.utc)
    if ZoneInfo:
        return dt_utc.astimezone(ZoneInfo(tz))
    return dt_utc  # fallback: UTC if zoneinfo not available

# 1) get upcoming events
ev = requests.get(f"https://api.the-odds-api.com/v4/sports/{SPORT}/events",
                  params={"apiKey": API_KEY}, timeout=15)
if ev.status_code != 200:
    print("Events error:", ev.status_code, ev.text); sys.exit(1)
events = ev.json()

# 2) pick the soonest THURSDAY (local to ET) event
candidates = []
now_local = to_local(datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"))
for e in events:
    start_local = to_local(e["commence_time"])
    if start_local >= now_local and start_local.weekday() == 3:  # 0=Mon ... 3=Thu
        candidates.append((start_local, e))

if not candidates:
    print("No Thursday NFL events found in the feed yet.")
    sys.exit(0)

candidates.sort(key=lambda x: x[0])
start_local, game = candidates[0]
eid = game["id"]; home = game["home_team"]; away = game["away_team"]

print(f"Next Thursday game (ET): {away} at {home} | {start_local.isoformat()} | id={eid}")

# 3) try to fetch player props for that game
odds = requests.get(
    f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{eid}/odds",
    params={
        "apiKey": API_KEY,
        "regions": REGION,
        "oddsFormat": "decimal",
        "markets": MARKETS,
    },
    timeout=20
)

if odds.status_code == 402 or "OUT_OF_USAGE_CREDITS" in odds.text:
    print("Out of credits:", odds.text); sys.exit(0)
if odds.status_code != 200:
    print("Props error:", odds.status_code, odds.text); sys.exit(1)

data = odds.json()
bms = data.get("bookmakers", [])
if not bms:
    print("No player props posted yet for this Thursday game.")
else:
    print("\n✅ Player props found:")
    for bm in bms:
        print(f"Bookmaker: {bm.get('title')}")
        for m in bm.get("markets", []):
            if m.get("key") in MARKETS.split(","):
                outs = m.get("outcomes", [])
                for o in outs[:8]:
                    print(f"  {m['key']:18s} {o.get('name'):<24} {str(o.get('point')):<8} @ {o.get('price')}")
