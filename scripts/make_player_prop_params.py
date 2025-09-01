#!/usr/bin/env python3
# scripts/make_player_prop_params.py
"""
General-purpose player-prop parameter builder.
- Week 1  : use previous season weekly stats
- Week 2+ : use current season weeks 1..(week-1)
Outputs: data/predictions/player_all_props_params.csv (tidy parameters)
"""

import argparse, pathlib, warnings, math
import pandas as pd
import numpy as np

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True, help="Target season (e.g., 2025)")
    ap.add_argument("--week",   type=int, required=True, help="Target week (1..18)")
    ap.add_argument("--back_seasons", type=int, default=1,
                    help="How many prior seasons to use for Week 1 (default 1)")
    ap.add_argument("--props_csv", default="data/props/latest_all_props.csv",
                    help="Props CSV that limits which players to output")
    ap.add_argument("--out", default="data/predictions/player_all_props_params.csv")
    return ap.parse_args()

# Market → model + stat key
MARKET_MODEL = {
    "player_pass_yds": ("normal", "passing_yards"),
    "player_pass_attempts": ("normal", "passing_attempts"),
    "player_pass_completions": ("normal", "passing_completions"),
    "player_pass_tds": ("poisson", "passing_tds"),
    "player_pass_interceptions": ("poisson", "interceptions"),

    "player_rush_yds": ("normal", "rushing_yards"),
    "player_rush_attempts": ("normal", "rushing_attempts"),
    "player_rush_tds": ("poisson", "rushing_tds"),

    "player_receptions": ("normal", "receptions"),
    "player_reception_yds": ("normal", "receiving_yards"),
    "player_reception_tds": ("poisson", "receiving_tds"),

    "player_field_goals": ("poisson", "field_goals_made"),
    "player_kicking_points": ("normal", "kicking_points"),

    "player_sacks": ("poisson", "sacks"),
    "player_solo_tackles": ("poisson", "solo_tackles"),
    "player_tackles_assists": ("poisson", "tackles_with_assists"),

    "player_anytime_td": ("bernoulli", "anytime_td_rate"),
}

# Robust column aliases
CANDIDATES = {
  "passing_yards": ["passing_yards","pass_yards"],
  "passing_attempts": ["passing_attempts","pass_attempts","attempts"],
  "passing_completions": ["completions","passing_completions","pass_completions","cmp"],
  "passing_tds": ["passing_tds","pass_touchdowns"],
  "interceptions": ["interceptions","int"],

  "rushing_yards": ["rushing_yards","rush_yards"],
  "rushing_attempts": ["rushing_attempts","rush_attempts"],
  "rushing_tds": ["rushing_tds","rush_touchdowns"],

  "receptions": ["receptions","rec"],
  "receiving_yards": ["receiving_yards","rec_yards"],
  "receiving_tds": ["receiving_tds","rec_touchdowns"],

  "field_goals_made": ["field_goals_made","fgm"],
  "kicking_points": ["kicking_points","points_kicking"],

  "sacks": ["sacks"],
  "solo_tackles": ["solo_tackles","def_solo_tackle"],
  "tackles_with_assists": ["tackles_with_assists","tackle_assists"],
}

DEFAULTS_NORMAL = {
    "passing_yards": (210.0, 60.0),
    "passing_attempts": (32.0, 8.0),
    "passing_completions": (20.0, 6.0),
    "rushing_yards": (42.0, 25.0),
    "rushing_attempts": (10.0, 5.0),
    "receptions": (3.0, 2.0),
    "receiving_yards": (36.0, 22.0),
    "kicking_points": (6.0, 3.0),
}

def first_col(df, names):
    for n in names:
        if n in df.columns: return n
    return None

def load_weekly_for_target(season:int, week:int, back_seasons:int):
    import nfl_data_py as nfl
    if week <= 1:
        seasons = list(range(season - back_seasons, season))
    else:
        seasons = [season]
    weekly = nfl.import_weekly_data(seasons)

    # limit to weeks < target week for current season runs
    if week > 1:
        if "season" in weekly.columns and "week" in weekly.columns:
            weekly = weekly[(weekly["season"] == season) & (weekly["week"] < week)].copy()

    # name / team cols
    name_col = "player_display_name" if "player_display_name" in weekly.columns else "player_name"
    weekly["player"] = weekly[name_col].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()
    return weekly

def build_params(weekly: pd.DataFrame, want_players: list[str]) -> pd.DataFrame:
    # map canonical stats
    for key, aliases in CANDIDATES.items():
        col = first_col(weekly, aliases)
        if col: weekly[key] = weekly[col]

    # anytime TD flag from rushing+receiving TDs
    if "rushing_tds" in weekly.columns or "receiving_tds" in weekly.columns:
        rtd = weekly.get("rushing_tds", 0).fillna(0)
        retd = weekly.get("receiving_tds", 0).fillna(0)
        weekly["anytime_td_flag"] = ((rtd + retd) > 0).astype(int)

    # aggregate per player
    use_stats = set(v for kind,v in MARKET_MODEL.values() if kind!="bernoulli")
    agg = {"games": ("player","size")}
    for stat in use_stats:
        if stat in weekly.columns:
            agg[f"{stat}_mean"] = (stat, "mean")
            # normals need std
            if any((k=="normal" and v==stat) for k,v in MARKET_MODEL.values()):
                agg[f"{stat}_std"] = (stat, "std")

    gb = weekly.groupby("player")
    stats = gb.agg(**agg).reset_index() if isinstance(agg, dict) else gb.agg(agg).reset_index()

    # anytime TD rate
    if "anytime_td_flag" in weekly.columns:
        td_rate = weekly.groupby("player")["anytime_td_flag"].mean().rename("anytime_td_rate").reset_index()
        stats = stats.merge(td_rate, on="player", how="left")
    else:
        stats["anytime_td_rate"] = np.nan

    params = pd.DataFrame({"player": want_players}).merge(stats, on="player", how="left")
    params["games"] = params["games"].fillna(0)

    # priors for normals
    for stat,(mu0,sd0) in DEFAULTS_NORMAL.items():
        if f"{stat}_mean" in params.columns:
            params[f"{stat}_mean"] = params[f"{stat}_mean"].fillna(mu0)
        if f"{stat}_std" in params.columns:
            params[f"{stat}_std"] = params[f"{stat}_std"].fillna(sd0)

    # priors for poisson (means act as lambda)
    for stat in ["passing_tds","interceptions","rushing_tds","receiving_tds","field_goals_made","sacks","solo_tackles","tackles_with_assists"]:
        col = f"{stat}_mean"
        if col in params.columns:
            params[col] = params[col].fillna(0.1)

    # anytime TD prior
    params["anytime_td_rate"] = params["anytime_td_rate"].fillna(0.08)

    # tidy rows
    rows = []
    for _, r in params.iterrows():
        for mkt,(kind, stat) in MARKET_MODEL.items():
            if kind == "normal":
                mu = float(r.get(f"{stat}_mean", np.nan))
                sd = float(r.get(f"{stat}_std",  np.nan))
                if not (sd==sd) or sd <= 0: sd = DEFAULTS_NORMAL.get(stat,(0,10))[1]
                rows.append({"player": r["player"], "market": mkt, "model": "normal", "mu": mu, "sigma": max(1e-6, sd), "games": int(r["games"])})
            elif kind == "poisson":
                lam = float(r.get(f"{stat}_mean", np.nan))
                if not (lam==lam) or lam <= 0: lam = 0.1
                rows.append({"player": r["player"], "market": mkt, "model": "poisson", "lam": max(1e-9, lam), "games": int(r["games"])})
            else:  # bernoulli
                p = float(r.get("anytime_td_rate", np.nan))
                if not (p==p) or p <= 0: p = 0.05
                rows.append({"player": r["player"], "market": mkt, "model": "bernoulli", "p": min(max(p,0.001),0.95), "games": int(r["games"])})
    return pd.DataFrame(rows)

def main():
    args = parse_args()
    props_csv = pathlib.Path(args.props_csv)
    if not props_csv.exists():
        raise SystemExit(f"Missing props file: {props_csv}. Run props fetch first.")

    props = pd.read_csv(props_csv, low_memory=False)
    want_players = sorted(set(props["player"].dropna().astype(str).str.replace(r"\s+"," ",regex=True).str.strip()))

    weekly = load_weekly_for_target(args.season, args.week, args.back_seasons)
    params = build_params(weekly, want_players)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    params.to_csv(out, index=False)
    print(f"Wrote {out} with {len(params):,} (player,market) rows for season={args.season}, week={args.week}")

if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        main()
