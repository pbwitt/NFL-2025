# scripts/clean_td_merges.py
#!/usr/bin/env python3
import argparse, re
import pandas as pd
import numpy as np

def prob_to_american(p):
    p = float(p)
    if p <= 0 or p >= 1 or np.isnan(p):
        return np.nan
    return -100 * p/(1-p) if p >= 0.5 else 100 * (1-p)/p

def american_to_prob(odds):
    if pd.isna(odds): return np.nan
    o = float(odds)
    return (100/(-o+100)) if o<0 else (100/(o+100))

def keyify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.in_csv)

    # Normalize keys (be forgiving on column availability)
    if "player_key" not in df.columns and "player" in df.columns:
        df["player_key"] = df["player"].map(keyify)
    elif "player_key" in df.columns:
        df["player_key"] = df["player_key"].map(keyify)

    if "market_std" not in df.columns and "market" in df.columns:
        df["market_std"] = df["market"].str.lower().str.replace(" ", "_")
    else:
        df["market_std"] = df["market_std"].astype(str).str.lower()

    # Focus on anytime TDs only (adjust if you want others)
    df = df[df["market_std"] == "anytime_td"].copy()

    # Sort so NaN model rows come first, modeled rows last; then keep last
    # This collapses (bookmaker,player,game,price) pairs to the modeled copy.
    sort_cols = ["model_prob", "model_price", "mu"]
    for c in sort_cols:
        if c not in df.columns: df[c] = np.nan

    df = df.sort_values(sort_cols)  # NaNs sort last=False by default? In pandas NaNs go last.
    # We want modeled rows last, so make sure NaNs are first:
    # Trick: create a flag for "has_model"
    has_model = (~df["model_prob"].isna()).astype(int)
    df = df.assign(_has_model=has_model).sort_values(["_has_model"]).drop(columns=["_has_model"])

    # Dedup on the natural key
    key_cols = [c for c in ["game_id","player_key","market_std","bookmaker","price"] if c in df.columns]
    df = df.drop_duplicates(subset=key_cols, keep="last")

    # Compute market implied prob & edge if not present
    if "market_prob" not in df.columns:
        df["market_prob"] = df["price"].map(american_to_prob)

    if "model_prob" not in df.columns:
        df["model_prob"] = np.nan  # should exist; just in case

    # Fair price from model prob
    df["model_price"] = df["model_prob"].map(prob_to_american)

    # Simple edge metric: model - market probability (positive = value)
    df["edge_prob"] = df["model_prob"] - df["market_prob"]

    # Keep nice columns first
    preferred = [c for c in [
        "home_team","away_team","player","player_key","team_key","market_std","bookmaker","price",
        "market_prob","mu","sigma","model_prob","model_price","model_line","edge_prob","game_id","commence_time","name"
    ] if c in df.columns]
    df = df[preferred + [c for c in df.columns if c not in preferred]]

    df.to_csv(args.out_csv, index=False)
    print(f"[clean_td_merges] Wrote {len(df)} rows to {args.out_csv}")

if __name__ == "__main__":
    main()
s
