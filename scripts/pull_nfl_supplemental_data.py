#!/usr/bin/env python3
import argparse, datetime as dt, os
import pandas as pd
import nfl_data_py as nfl
from tqdm.auto import tqdm

def season_years(start=1999, end=None):
    this_year = dt.date.today().year if end is None else end
    return list(range(start, this_year + 1))

def current_season_today():
    today = dt.date.today()
    return today.year if today.month >= 9 else today.year - 1

def latest_completed_week(season: int) -> int:
    sched = nfl.import_schedules([season])
    sched = sched[sched["home_score"].notna() & sched["away_score"].notna()]
    if sched.empty: return 1
    return int(sched["week"].max())

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def save(df: pd.DataFrame, out_dir: str, name: str, as_csv: bool):
    ensure_dir(out_dir)
    df.to_parquet(os.path.join(out_dir, f"{name}.parquet"), index=False)
    if as_csv: df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
    print(f"Saved {name}: {len(df):,} rows")

def append_dedup(df_new: pd.DataFrame, out_dir: str, name: str, keys, as_csv: bool):
    ensure_dir(out_dir)
    path = os.path.join(out_dir, f"{name}.parquet")
    if os.path.exists(path):
        df_old = pd.read_parquet(path)
        df = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=keys, keep="last")
    else:
        df = df_new
    df.to_parquet(path, index=False)
    if as_csv:
        cpath = os.path.join(out_dir, f"{name}.csv")
        if os.path.exists(cpath):
            df_old = pd.read_csv(cpath)
            dfc = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=keys, keep="last")
        else:
            dfc = df_new
        dfc.to_csv(cpath, index=False)
    print(f"Appended {name}: now {len(df):,} rows")

def main():
    ap = argparse.ArgumentParser(description="Supplemental nflverse pull with progress + latest-week mode.")
    ap.add_argument("--out", default="data/nfl_supplemental")
    ap.add_argument("--start", type=int, default=1999)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--no-pbp", action="store_true", help="Skip play-by-play (large)")
    ap.add_argument("--csv", action="store_true")
    # NEW: only append latest completed week of current season (schedules + PBP for that week)
    ap.add_argument("--latest-week", action="store_true", help="Fetch only latest completed week (current season) and append.")
    args = ap.parse_args()

    out, as_csv = args.out, args.csv

    if args.latest_week:
        season = current_season_today()
        week = latest_completed_week(season)
        print(f"Latest-week mode: season={season}, week={week}")

        # Schedules: append only that week
        sched = nfl.import_schedules([season])
        sched_w = sched[sched["week"] == week]
        append_dedup(sched_w, out, "schedules", keys=["game_id"], as_csv=as_csv)

        # Play-by-play for that week only (if allowed)
        if not args.no_pbp:
            pbp = nfl.import_pbp_data([season])
            if "week" in pbp.columns:
                pbp_w = pbp[pbp["week"] == week]
            else:
                # conservative fallback if schema changes
                pbp_w = pbp.merge(sched_w[["game_id"]], on="game_id", how="inner")
            append_dedup(pbp_w, out, "play_by_play", keys=["game_id","play_id"], as_csv=as_csv)

        # Team metadata is static; skip in latest mode to keep it quick
        print("Latest-week append complete.")
        return

    # Full historical mode with progress bars; loop PBP per-year for visibility
    years = season_years(args.start, args.end)

    # Schedules (all at once)
    try:
        sched = nfl.import_schedules(years)
        save(sched, out, "schedules", as_csv)
    except Exception as e:
        print(f"[WARN] Schedules failed: {e}")

    # Team metadata
    try:
        team_desc = nfl.import_team_desc()
        save(team_desc, out, "team_descriptions", as_csv)
    except Exception as e:
        print(f"[WARN] Team descriptions failed: {e}")

    # Play-by-play (per year) with progress
    if not args.no_pbp:
        for y in tqdm(years, desc="Play-by-play by season", unit="season"):
            try:
                pbp_y = nfl.import_pbp_data([y])
                save(pbp_y, out, f"play_by_play_{y}", as_csv)
            except Exception as e:
                print(f"[WARN] PBP {y} failed: {e}")

    print("Supplemental pull complete.")

if __name__ == "__main__":
    main()
