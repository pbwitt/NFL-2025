#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pull historical NFL *player-level* data via nfl_data_py (nflverse).

Datasets:
- Weekly player stats
- Seasonal player stats
- PFR advanced logs (season + weekly; pass/rec/rush)
- Rosters (seasonal + weekly), unified player IDs
- Snap counts, injuries, depth charts
- Combine results, draft picks & values
- Optional: Next Gen Stats (passing/rushing/receiving)

Outputs: Parquet by default, optional CSV via --csv.

Weekly mode:
  --latest-week  → append only the latest completed week of current season
                   (robust to 'team' vs 'recent_team' column names)
"""

import argparse
import datetime as dt
import os
from typing import List

import pandas as pd
import nfl_data_py as nfl
from tqdm.auto import tqdm


# -----------------------------
# Utilities
# -----------------------------
def season_years(start=1999, end=None) -> List[int]:
    this_year = dt.date.today().year if end is None else end
    return list(range(start, this_year + 1))

def current_season_today() -> int:
    today = dt.date.today()
    # NFL season considered to roll over in September
    return today.year if today.month >= 9 else today.year - 1

def latest_completed_week(season: int) -> int:
    """Pick the latest week with final scores in the given season."""
    sched = nfl.import_schedules([season])
    done = sched[sched["home_score"].notna() & sched["away_score"].notna()]
    if done.empty:
        return 1
    # If you prefer REG only, uncomment next line:
    # done = done[done["game_type"] == "REG"]
    return int(done["week"].max())

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def ensure_team_col(df: pd.DataFrame) -> pd.DataFrame:
    """Unify to a 'team' column when only 'recent_team' exists."""
    if "team" not in df.columns and "recent_team" in df.columns:
        df = df.rename(columns={"recent_team": "team"})
    return df

def safe_keys(keys: List[str], df: pd.DataFrame) -> List[str]:
    """Keep only keys present in df."""
    return [k for k in keys if k in df.columns]

def save(df: pd.DataFrame, out_dir: str, name: str, as_csv: bool):
    ensure_dir(out_dir)
    df.to_parquet(os.path.join(out_dir, f"{name}.parquet"), index=False)
    if as_csv:
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
    print(f"Saved {name}: {len(df):,} rows")

def append_dedup(df_new: pd.DataFrame, out_dir: str, name: str, keys: List[str], as_csv: bool):
    """
    Append df_new to existing file (if any), then drop duplicates using
    the intersection of requested keys and the actual columns.
    Also writes CSV if requested.
    """
    ensure_dir(out_dir)
    df_new = ensure_team_col(df_new)
    keys_new = safe_keys(keys, df_new)

    ppath = os.path.join(out_dir, f"{name}.parquet")
    if os.path.exists(ppath):
        df_old = pd.read_parquet(ppath)
        df_old = ensure_team_col(df_old)
        keys_old = safe_keys(keys, df_old)
        keys_use = [k for k in keys_new if k in keys_old]
        df = pd.concat([df_old, df_new], ignore_index=True)
        if keys_use:
            df = df.drop_duplicates(subset=keys_use, keep="last")
    else:
        df = df_new
        keys_use = keys_new

    df.to_parquet(ppath, index=False)

    if as_csv:
        cpath = os.path.join(out_dir, f"{name}.csv")
        if os.path.exists(cpath):
            df_old = pd.read_csv(cpath)
            df_old = ensure_team_col(df_old)
            keys_old = safe_keys(keys, df_old)
            keys_use_csv = [k for k in keys_new if k in keys_old]
            dfc = pd.concat([df_old, df_new], ignore_index=True)
            if keys_use_csv:
                dfc = dfc.drop_duplicates(subset=keys_use_csv, keep="last")
        else:
            dfc = df_new
        dfc.to_csv(cpath, index=False)

    print(f"Appended {name}: now {len(df):,} rows (deduped on {keys_use})")


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Player-level nflverse pull with progress + latest-week mode.")
    ap.add_argument("--out", default="data", help="Output directory")
    ap.add_argument("--start", type=int, default=1999, help="First season (inclusive)")
    ap.add_argument("--end", type=int, default=None, help="Last season (inclusive; default=current year)")
    ap.add_argument("--no-pfr", action="store_true", help="Skip PFR advanced logs")
    ap.add_argument("--no-ngs", action="store_true", help="Skip Next Gen Stats")
    ap.add_argument("--csv", action="store_true", help="Also write CSVs next to Parquet")
    ap.add_argument("--latest-week", action="store_true", help="Append only latest completed week of current season")
    args = ap.parse_args()

    out = args.out
    as_csv = args.csv

    # ---------- Latest-week fast path ----------
    if args.latest_week:
        season = current_season_today()
        week = latest_completed_week(season)
        print(f"Latest-week mode: season={season}, week={week}")

        # Weekly player stats
        wk = nfl.import_weekly_data([season])
        wk = wk[wk["week"] == week]
        wk = ensure_team_col(wk)
        append_dedup(wk, out, "weekly_player_stats",
                     keys=["player_id", "season", "week", "team"], as_csv=as_csv)

        # Weekly rosters
        wr = nfl.import_weekly_rosters([season])
        wr = wr[wr["week"] == week]
        wr = ensure_team_col(wr)
        append_dedup(wr, out, "weekly_rosters",
                     keys=["player_id", "season", "week", "team"], as_csv=as_csv)

        # Injuries
        inj = nfl.import_injuries([season])
        inj = inj[inj["week"] == week]
        inj = ensure_team_col(inj)
        append_dedup(inj, out, "injuries",
                     keys=["player_id", "season", "week", "team"], as_csv=as_csv)

        # Snap counts
        sc = nfl.import_snap_counts([season])
        sc = sc[sc["week"] == week]
        sc = ensure_team_col(sc)
        append_dedup(sc, out, "snap_counts",
                     keys=["player_id", "season", "week", "team"], as_csv=as_csv)

        # Depth charts
        dc = nfl.import_depth_charts([season])
        dc = dc[dc["week"] == week]
        dc = ensure_team_col(dc)
        append_dedup(dc, out, "depth_charts",
                     keys=["player_id", "season", "week", "team", "position"], as_csv=as_csv)

        # Optional NGS
        if not args.no_ngs:
            for stype in ["passing", "rushing", "receiving"]:
                try:
                    ngs = nfl.import_ngs_data(stat_type=stype, years=[season])
                    if "week" in ngs.columns:
                        ngs = ngs[ngs["week"] == week]
                    append_dedup(
                        ngs, out, f"ngs_{stype}",
                        keys=[k for k in ["nfl_player_id", "season", "week"] if k in ngs.columns],
                        as_csv=as_csv
                    )
                except Exception as e:
                    print(f"[WARN] NGS {stype} skipped: {e}")

        print("Latest-week append complete.")
        return

    # ---------- Full history with progress ----------
    years = season_years(args.start, args.end)
    tasks = []
    tasks.append(("weekly_player_stats",        lambda: nfl.import_weekly_data(years)))
    tasks.append(("seasonal_player_stats",      lambda: nfl.import_seasonal_data(years, s_type="ALL")))
    tasks.append(("seasonal_rosters",           lambda: nfl.import_seasonal_rosters(years)))
    tasks.append(("weekly_rosters",             lambda: nfl.import_weekly_rosters(years)))
    tasks.append(("player_ids_unified",         lambda: nfl.import_ids()))
    tasks.append(("snap_counts",                lambda: nfl.import_snap_counts(years)))
    tasks.append(("injuries",                   lambda: nfl.import_injuries(years)))
    tasks.append(("depth_charts",               lambda: nfl.import_depth_charts(years)))
    tasks.append(("combine_results",            lambda: nfl.import_combine_data(years)))
    tasks.append(("draft_picks",                lambda: nfl.import_draft_picks(years)))
    tasks.append(("draft_pick_values",          lambda: nfl.import_draft_values()))

    if not args.no_pfr:
        for stype in ["pass", "rec", "rush"]:
            tasks.append((f"pfr_season_{stype}", lambda s=stype: nfl.import_seasonal_pfr(s_type=s, years=years)))
            tasks.append((f"pfr_weekly_{stype}", lambda s=stype: nfl.import_weekly_pfr(s_type=s, years=years)))

    if not args.no_ngs:
        for stype in ["passing", "rushing", "receiving"]:
            tasks.append((f"ngs_{stype}", lambda s=stype: nfl.import_ngs_data(stat_type=s, years=years)))

    for name, fn in tqdm(tasks, desc="Player datasets", unit="set"):
        try:
            df = fn()
            df = ensure_team_col(df)
            save(df, out, name, as_csv=as_csv)
        except Exception as e:
            print(f"[WARN] Skipping {name}: {e}")

    print("Full player data pull complete.")

if __name__ == "__main__":
    main()
