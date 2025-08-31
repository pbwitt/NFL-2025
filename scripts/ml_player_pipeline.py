#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFL Player ML Pipeline (player features + opponent-defense features)
- Rolling recent (last N) and season-to-date features for players and defenses
- Flexible filters (positions, player_ids)
- Season-holdout or random split
- Weekly prediction: only for weeks that already exist in weekly_player_stats.csv
"""

import argparse
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# ---------------------------
# Column normalization
# ---------------------------
COL_ALIASES = {
    "pass_yards": "passing_yards",
    "passing_yards": "passing_yards",
    "rush_yards": "rushing_yards",
    "rushing_yards": "rushing_yards",
    "rec_yards": "receiving_yards",
    "receiving_yards": "receiving_yards",
    "attempts": "attempts",
    "pass_attempts": "attempts",
    "completions": "completions",
    "pass_completions": "completions",
    "receptions": "receptions",
    "targets": "targets",
    "carries": "carries",
    "fantasy_points_ppr": "fantasy_points_ppr",
    "rush_tds": "rush_tds",
    "rec_tds": "rec_tds",
    "pass_tds": "pass_tds",
    "sacks": "sacks",
    "interceptions": "interceptions",
    "fumbles": "fumbles",
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for c in df.columns:
        if c in COL_ALIASES:
            rename[c] = COL_ALIASES[c]
    if rename:
        df = df.rename(columns=rename)
    if "team" not in df.columns and "recent_team" in df.columns:
        df = df.rename(columns={"recent_team": "team"})
    if "player_name" not in df.columns and "name" in df.columns:
        df = df.rename(columns={"name": "player_name"})
    return df

def resolve_target_name(user_target: str, df: pd.DataFrame) -> str:
    if user_target in df.columns:
        return user_target
    if user_target in COL_ALIASES:
        canon = COL_ALIASES[user_target]
        if canon in df.columns:
            return canon
    raise ValueError(f"Target '{user_target}' not found. Sample cols: {sorted(df.columns)[:40]} ...")

# ---------------------------
# Load + Features
# ---------------------------
def load_player_weekly(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = normalize_columns(df)
    for c in ("season", "week"):
        if c in df.columns: df[c] = df[c].astype(int)
    if "player_name" not in df.columns:
        df["player_name"] = df["player_id"]
    return df

def add_player_rolling_and_season(df, cols, lookbacks, group_col="player_id", prefix="p_"):
    df = df.sort_values([group_col,"season","week"]).copy()
    for col in cols:
        for k in lookbacks:
            df[f"{prefix}{col}_last{k}"] = (
                df.groupby(group_col)[col].transform(lambda s: s.shift().rolling(k,min_periods=1).mean())
            )
        df[f"{prefix}{col}_season_avg"] = (
            df.groupby([group_col,"season"])[col].transform(lambda s: s.shift().expanding().mean())
        )
    return df

def build_defense_allowed(df_players, agg_cols, lookbacks):
    defense = (df_players.groupby(["season","week","opponent_team"], dropna=False)[agg_cols]
               .sum(min_count=1)
               .reset_index()
               .rename(columns={"opponent_team":"def_team"}))
    defense = defense.sort_values(["def_team","season","week"]).copy()
    for col in agg_cols:
        for k in lookbacks:
            defense[f"def_allowed_{col}_last{k}"] = (
                defense.groupby("def_team")[col].transform(lambda s: s.shift().rolling(k,min_periods=1).mean())
            )
        defense[f"def_allowed_{col}_season_avg"] = (
            defense.groupby(["def_team","season"])[col].transform(lambda s: s.shift().expanding().mean())
        )
    return defense

def join_defense_allowed(df_players, defense, feat_cols):
    use_cols = ["season","week","def_team"] + feat_cols
    merged = df_players.merge(
        defense[use_cols],
        left_on=["season","week","opponent_team"],
        right_on=["season","week","def_team"],
        how="left"
    )
    return merged.drop(columns=["def_team"])

def build_dataset(player_csv, target, positions, player_ids, lookbacks):
    df = load_player_weekly(player_csv)
    target = resolve_target_name(target, df)

    if positions:
        df = df[df["position"].isin(positions)]
    if player_ids:
        df = df[df["player_id"].isin(player_ids)]

    candidates = [
        "passing_yards","rushing_yards","receiving_yards",
        "attempts","completions","carries","targets",
        "fantasy_points_ppr","rush_tds","rec_tds","pass_tds",
        "receptions","sacks","interceptions","fumbles"
    ]
    num_cols = [c for c in candidates if c in df.columns]

    df = add_player_rolling_and_season(df, num_cols, lookbacks, "player_id", "p_")

    def_cols = list(set(num_cols+[target]))
    defense = build_defense_allowed(df, def_cols, lookbacks)

    def_feats = []
    for col in def_cols:
        for k in lookbacks:
            def_feats.append(f"def_allowed_{col}_last{k}")
        def_feats.append(f"def_allowed_{col}_season_avg")
    df = join_defense_allowed(df, defense, def_feats)

    need_cols = [f"p_{target}_season_avg"] + [f"p_{target}_last{k}" for k in lookbacks]
    need_cols = [c for c in need_cols if c in df.columns]
    df = df.dropna(subset=need_cols+[target])

    feat_cols = []
    feat_cols += [c for c in df.columns if c.startswith("p_")]
    feat_cols += [c for c in df.columns if c.startswith("def_allowed_")]
    if "week" in df.columns: feat_cols.append("week")
    X = df[feat_cols].fillna(0)
    y = df[target].astype(float)
    return X, y, df

# ---------------------------
# Train/Eval/Predict
# ---------------------------
def season_holdout_split(df_keys, X, y, holdout_season):
    train_idx = df_keys["season"] < holdout_season
    test_idx  = df_keys["season"] == holdout_season
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]

def random_split(X,y,test_size=0.2,seed=42):
    return train_test_split(X,y,test_size=test_size,random_state=seed,shuffle=True)

def train_and_eval(X_train,y_train,X_test,y_test,n_estimators=600,seed=42):
    model = RandomForestRegressor(n_estimators=n_estimators,random_state=seed,n_jobs=-1)
    model.fit(X_train,y_train)
    if len(X_test):
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test,preds)
        print(f"MAE: {mae:.3f}")
    else:
        mae = None
        print("No test rows available for MAE.")
    return model, mae

def predict_week_existing_rows(model,df_all,X_all,season,week):
    mask = (df_all["season"]==season)&(df_all["week"]==week)
    if mask.sum()==0:
        print("No rows for that season/week (not in CSV).")
        return pd.DataFrame()
    preds = model.predict(X_all[mask])
    out_cols = [c for c in ["player_id","player_name","position","team","opponent_team","season","week"] if c in df_all.columns]
    out = df_all.loc[mask,out_cols].copy()
    out["prediction"] = preds
    return out.sort_values(["team","position","player_name"])

# ---------------------------
# CLI
# ---------------------------
def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--player_csv",required=True)
    p.add_argument("--target",required=True)
    p.add_argument("--positions",nargs="*",default=None)
    p.add_argument("--player_ids",nargs="*",default=None)
    p.add_argument("--lookbacks",nargs="+",type=int,default=[3])
    p.add_argument("--split",choices=["season_holdout","random"],default="season_holdout")
    p.add_argument("--holdout_season",type=int,default=2023)
    p.add_argument("--test_size",type=float,default=0.2)
    p.add_argument("--n_estimators",type=int,default=600)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--predict_season",type=int,default=None)
    p.add_argument("--predict_week",type=int,default=None)
    p.add_argument("--save_preds",default=None)
    return p.parse_args()

def main():
    args=parse_args()
    X,y,df_all=build_dataset(args.player_csv,args.target,args.positions,args.player_ids,args.lookbacks)
    print(f"Rows: {len(df_all)} | Features: {X.shape[1]}")
    if args.split=="season_holdout":
        X_train,X_test,y_train,y_test=season_holdout_split(df_all,X,y,args.holdout_season)
        print(f"Train rows: {len(y_train)} | Test rows: {len(y_test)}")
    else:
        X_train,X_test,y_train,y_test=random_split(X,y,args.test_size,args.seed)
        print(f"Train rows: {len(y_train)} | Test rows: {len(y_test)}")
    model,mae=train_and_eval(X_train,y_train,X_test,y_test,args.n_estimators,args.seed)
    if args.predict_season is not None and args.predict_week is not None:
        preds_df=predict_week_existing_rows(model,df_all,X,args.predict_season,args.predict_week)
        if args.save_preds and not preds_df.empty:
            preds_df.to_csv(args.save_preds,index=False)
            print(f"Saved predictions -> {args.save_preds}")
        elif preds_df.empty:
            print("No predictions to write (empty).")
        else:
            print("Predictions ready.")

if __name__=="__main__":
    main()
