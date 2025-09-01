# scripts/join_predictions_with_odds.py
import argparse, pathlib, pandas as pd, numpy as np

def get_args():
    p = argparse.ArgumentParser(description="Join model predictions with odds and compute edges.")
    p.add_argument("--preds", default="data/predictions/latest_predictions.csv")
    p.add_argument("--odds", default="data/odds/latest.csv")
    p.add_argument("--out", default="data/merged/latest_with_edges.csv")
    p.add_argument("--kickoff_tolerance_min", type=int, default=5)
    return p.parse_args()

def compute_moneyline_edge(row):
    # Convert American odds to implied probability ignoring vig: P=100/(odds+100) if odds>0 else |odds|/(|odds|+100)
    price = row["price"]
    if pd.isna(price): return np.nan
    if price > 0:
        imp = 100.0 / (price + 100.0)
    else:
        imp = abs(price) / (abs(price) + 100.0)
    # Edge = model_prob - implied_prob
    return row["team_win_prob"] - imp

def main():
    a = get_args()
    preds = pd.read_csv(a.preds)
    odds = pd.read_csv(a.odds)

    # Normalize times
    for df in (preds, odds):
        if "commence_time" in df.columns:
            df["commence_time"] = pd.to_datetime(df["commence_time"])

    # Build join keys
    can_use_game_id = ("game_id" in preds.columns) and ("game_id" in odds.columns)
    if not can_use_game_id:
        # Construct a composite key (lowercased) to match
        def k(df):
            return (df["home_team"].str.lower().str.replace(r"\s+","", regex=True)
                    + "_" +
                    df["away_team"].str.lower().str.replace(r"\s+","", regex=True))
        for df in (preds, odds):
            df["teams_key"] = k(df)

        # Merge within a time tolerance
        odds["t0"] = odds["commence_time"].dt.floor("min")
        preds["t0"] = preds["commence_time"].dt.floor("min")
        merged = pd.merge_asof(
            preds.sort_values("t0"),
            odds.sort_values("t0"),
            by="teams_key",
            left_on="t0",
            right_on="t0",
            direction="nearest",
            tolerance=pd.Timedelta(minutes=a.kickoff_tolerance_min)
        )
    else:
        merged = preds.merge(odds, on="game_id", how="left", suffixes=("","_odds"))

    # Compute per-market summaries
    # Example: moneyline edge for the team the row refers to
    if {"market","price","name","team","team_win_prob"}.issubset(merged.columns):
        ml = merged[merged["market"]=="h2h"].copy()
        # Align name (book outcome) to team name used in preds
        ml = ml[ml["name"].str.lower() == ml["team"].str.lower()]
        ml["edge_moneyline"] = ml.apply(compute_moneyline_edge, axis=1)
        merged.loc[ml.index, "edge_moneyline"] = ml["edge_moneyline"]

    # Spread edge (model margin vs line point)
    if {"market","point","pred_margin","team"}.issubset(merged.columns):
        sp = merged[merged["market"]=="spreads"].copy()
        # Convention: positive pred_margin favors home; adjust to team perspective if needed
        # Edge ~ (pred_margin - (-point)) for home, (pred_margin - point) for away — depends on schema.
        # For simplicity assume row is TEAM=home for home rows; otherwise away.
        is_home = (sp["team"].str.lower() == sp["home_team"].str.lower())
        sp.loc[is_home, "spread_edge_pts"] = sp["pred_margin"] + sp["point"]  # home favored by pred vs book
        sp.loc[~is_home, "spread_edge_pts"] = -sp["pred_margin"] + sp["point"]
        merged.loc[sp.index, "spread_edge_pts"] = sp["spread_edge_pts"]

    # Total edge (model total vs line)
    if {"market","point","pred_total"}.issubset(merged.columns):
        tot = merged[merged["market"]=="totals"].copy()
        tot["total_edge_pts"] = tot["pred_total"] - tot["point"]
        merged.loc[tot.index, "total_edge_pts"] = tot["total_edge_pts"]

    # Best line per market/book side (optional)
    # Example: get best price for each (game, market, name)
    if {"game_id","market","name","price","bookmaker"}.issubset(merged.columns):
        merged["is_best_price"] = (
            merged.groupby(["game_id","market","name"])["price"]
                  .transform(lambda s: s == s.max())
        )

    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(a.out, index=False)
    print(f"Wrote {a.out} with {len(merged)} rows")

if __name__ == "__main__":
    main()
