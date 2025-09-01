#!/usr/bin/env python3
# scripts/join_all_player_props_with_preds.py
import math, pathlib
import pandas as pd
import numpy as np
from math import erf, sqrt, exp

PROPS = pathlib.Path("data/props/latest_all_props.csv")
PREDS = pathlib.Path("data/predictions/player_all_props_params.csv")
OUT   = pathlib.Path("data/merged/player_props_latest.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

def american_to_prob(odds):
    if pd.isna(odds): return np.nan
    o = float(odds)
    return 100.0/(o+100.0) if o>0 else abs(o)/(abs(o)+100.0)

# vectorized normal CDF
_vec_erf = np.vectorize(erf)
def norm_cdf_vec(z_arr):
    return 0.5*(1.0 + _vec_erf(z_arr/np.sqrt(2.0)))

def poisson_sf(lam, L):
    """P(X > L) for Poisson(lam), with L possibly fractional (uses floor)."""
    if lam <= 0: return 0.0
    k = int(math.floor(L))
    cdf = 0.0
    term = exp(-lam)  # k=0
    cdf += term
    for i in range(1, k+1):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)

# ---- Friendly market labels ----
MARKET_LABELS = {
    "player_pass_yds": "QB Passing Yards",
    "player_pass_tds": "QB Passing TDs",
    "player_pass_attempts": "Pass Attempts",
    "player_pass_completions": "Completions",
    "player_pass_interceptions": "Interceptions",
    "player_receptions": "Receptions",
    "player_reception_yds": "Receiving Yards",
    "player_reception_tds": "Receiving TDs",
    "player_rush_yds": "Rushing Yards",
    "player_rush_attempts": "Rush Attempts",
    "player_rush_tds": "Rushing TDs",
    "player_field_goals": "Field Goals Made",
    "player_kicking_points": "Kicking Points",
    "player_sacks": "Sacks",
    "player_solo_tackles": "Solo Tackles",
    "player_tackles_assists": "Tackles + Assists",
    "player_anytime_td": "Anytime TD",
}

def friendly_market(key: str) -> str:
    if key in MARKET_LABELS:
        return MARKET_LABELS[key]
    # fallback: strip prefix, title-case, tidy common abbreviations
    x = key.replace("player_", "").replace("_", " ").title()
    x = x.replace("Yds", "Yards").replace("Tds", "TDs").replace("Td", "TD")
    return x

def main():
    if not PROPS.exists():
        raise SystemExit(f"Missing props file: {PROPS}. Run: make props_odds_all")
    if not PREDS.exists():
        raise SystemExit(f"Missing predictions file: {PREDS}. Run: make player_props_pred_all")

    props = pd.read_csv(PROPS, low_memory=False)
    preds = pd.read_csv(PREDS, low_memory=False)

    # Normalize join keys
    for df in (props, preds):
        df["player"] = df["player"].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()
        df["market"] = df["market"].astype(str)

    df = props.merge(preds, on=["player","market"], how="left")

    # If nothing merged, still write empty file gracefully
    if df.empty:
        df["market_label"] = []
        df.to_csv(OUT, index=False)
        print(f"Wrote {OUT} (0 rows)")
        return

    # Friendly labels
    df["market_label"] = df["market"].apply(friendly_market)

    side = df["name"].astype(str).str.lower()   # "over"/"under" or "yes"/"no"
    line = pd.to_numeric(df["point"], errors="coerce")
    price_prob = df["price"].apply(american_to_prob) / 100.0

    model = df["model"].fillna("normal").astype(str).values
    mu    = pd.to_numeric(df.get("mu"), errors="coerce").fillna(0.0)
    sd    = pd.to_numeric(df.get("sigma"), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(lower=1e-6)
    lam   = pd.to_numeric(df.get("lam"), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.001).clip(lower=1e-9)
    p_yes = pd.to_numeric(df.get("p"), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.05).clip(lower=1e-6, upper=0.999)

    # P(Over)
    z = ((line.fillna(0.0) - mu) / sd).to_numpy()
    p_over_norm = 1.0 - norm_cdf_vec(z)
    line_np, lam_np = line.fillna(0.0).to_numpy(), lam.to_numpy()
    p_over_pois = np.array([poisson_sf(Lv, lv) for Lv, lv in zip(line_np, lam_np)])
    p_over_bern = p_yes.to_numpy()

    p_over = np.where(model=="normal",  p_over_norm,
              np.where(model=="poisson", p_over_pois, p_over_bern))

    side_over = side.isin(["over","yes"]).to_numpy()
    df["model_prob"]   = np.where(side_over, p_over, 1.0 - p_over)
    df["implied_prob"] = price_prob.fillna(np.nan).to_numpy()
    df["edge_prob"]    = df["model_prob"] - df["implied_prob"]

    # Points-based edge (EV gap vs line)
    ev_gap = np.where(model=="normal",  (mu - line.fillna(0.0)).to_numpy(),
              np.where(model=="poisson", (lam - line.fillna(0.0)).to_numpy(), np.nan))
    df["edge_pts"] = np.where(side_over, ev_gap, -ev_gap)

    keep = [
        "game_id","commence_time","home_team","away_team","bookmaker",
        "market","market_label","player","name","price","point",
        "model","mu","sigma","lam","p","games",
        "model_prob","implied_prob","edge_prob","edge_pts"
    ]
    df = df[[c for c in keep if c in df.columns]].copy()
    df.sort_values(["market_label","edge_prob","edge_pts"], ascending=[True, False, False], inplace=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT} with {len(df):,} rows")

if __name__ == "__main__":
    main()
