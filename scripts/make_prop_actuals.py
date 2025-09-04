#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np

# expected actuals schema:
# game_id, player_key, market_std, actual_value, outcome  # outcome ∈ {Over,Under,Yes,No}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--merged_csv", required=True, help="props_with_model_weekX.csv")
    ap.add_argument("--actuals_csv", required=True, help="your scraped/entered results")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    m = pd.read_csv(args.merged_csv)
    a = pd.read_csv(args.actuals_csv)

    keys = ["game_id","player_key","market_std"]
    df = m.merge(a, on=keys, how="left", suffixes=("","_act"))

    # grade: win if model sided with actual outcome
    df["bet_side"] = df["name"].str.title()  # Over/Under/Yes/No
    df["won"] = np.where(df["bet_side"]==df["outcome"], 1, 0)

    # realized EV (approx) using offered price at bet side
    # if you later track which book/price you actually took, replace with that
    dec = 1/((df["price"].abs()+100)/100.0)  # American→prob (quick way for dec: same as in edges)
    # actually compute dec from price:
    dec = np.where(df["price"]>=0, 1+df["price"]/100.0, 1+100.0/df["price"].abs())
    df["payout"] = np.where(df["won"]==1, dec-1.0, -1.0)

    df.to_csv(args.out, index=False)
    print(f"Wrote graded results → {args.out} with {len(df):,} rows")

if __name__ == "__main__":
    main()
