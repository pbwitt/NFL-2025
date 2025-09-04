#!/usr/bin/env python3
"""
Build edges for player props by merging raw props with model params and computing:
- model_prob (row-wise; fills O/U from mu/sigma/point when missing)
- per-book de-vig fair probs (two-way, proportional method)
- consensus de-vig fair probs (aggregate across books)
- EV and edges vs book & consensus
- best book/price by EV per (game, player_key, market_std, point)
"""
import argparse, math
import numpy as np
import pandas as pd
from datetime import datetime, timezone

def _reset_if_indexed(df: pd.DataFrame, cols) -> pd.DataFrame:
    idx_names = [n for n in (df.index.names or []) if n is not None]
    if set(idx_names) & set(cols):
        return df.reset_index(drop=False)
    return df


# ---------- tiny helpers (simple, not vectorized) ----------
def american_to_decimal(a):
    try:
        a = float(a)
    except Exception:
        return np.nan
    return 1.0 + (a/100.0 if a > 0 else 100.0/abs(a))

def prob_to_american(p):
    if p is None or (isinstance(p, float) and (np.isnan(p) or p <= 0 or p >= 1)):
        return np.nan
    return int(round(-100*p/(1-p))) if p >= 0.5 else int(round(100*(1-p)/p))

def norm_cdf(x, mu=0.0, sigma=1.0):
    if x is None or mu is None or sigma is None:
        return np.nan
    try:
        x = float(x); mu = float(mu); sigma = float(sigma)
    except Exception:
        return np.nan
    if sigma <= 0: return np.nan
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))

def fair_from_two_way(dec_over, dec_under):
    """De-vig via proportional method: q_i=1/dec, p_i=q_i/sum(q)."""
    try:
        do = float(dec_over); du = float(dec_under)
    except Exception:
        return (np.nan, np.nan)
    if do <= 1 or du <= 1: return (np.nan, np.nan)
    q_over, q_under = 1.0/do, 1.0/du
    s = q_over + q_under
    if s <= 0: return (np.nan, np.nan)
    return (q_over/s, q_under/s)

def expected_value(p_model, dec_offered):
    """EV per $1 stake (not de-vig): p*(d-1) - (1-p)."""
    try:
        p = float(p_model); d = float(dec_offered)
    except Exception:
        return np.nan
    if not (0 < p < 1) or d <= 1: return np.nan
    return p*(d-1) - (1-p)

def as_iso_str(iso_utc):
    try:
        dt = datetime.fromisoformat(str(iso_utc).replace("Z","+00:00")).astimezone(timezone.utc)
        return dt.isoformat()
    except Exception:
        return iso_utc

def is_over(name):
    s = str(name).strip().lower()
    return s in ("over", "o")

def is_under(name):
    s = str(name).strip().lower()
    return s in ("under", "u")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week",   type=int, required=True)
    ap.add_argument("--props_csv",  required=True)
    ap.add_argument("--params_csv", required=True)
    ap.add_argument("--out",        required=True)
    args = ap.parse_args()

    # Read input CSVs (keep it simple)
    props  = pd.read_csv(args.props_csv, low_memory=False)
    params = pd.read_csv(args.params_csv, low_memory=False)

    # Ensure expected columns exist
    need_props  = ["game_id","player_key","market_std","bookmaker","name","price","point","commence_time",
                   "home_team","away_team","player","market","team_key"]
    need_params = ["player_key","market_std","mu","sigma","model_line","model_prob"]
    for c in need_props:
        if c not in props.columns:  props[c] = np.nan
    for c in need_params:
        if c not in params.columns: params[c] = np.nan

    # ---- Merge safely: only bring model columns from params to avoid overlap on 'player'/'market' ----
    join_keys = ["player_key","market_std"]
    model_cols = [c for c in ["mu","sigma","model_line","model_prob"] if c in params.columns]
    params_narrow = params[join_keys + model_cols].drop_duplicates(subset=join_keys, keep="first")
    df = props.merge(params_narrow, on=join_keys, how="left", validate="many_to_one").copy()

    # Basic numeric casts we rely on
    for c in ("point","mu","sigma","price"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Offered decimal odds
    df["dec_offered"] = df["price"].apply(american_to_decimal)

    # ---- Compute/Fill model_prob (row-wise; avoids slice assignment issues) ----
    def compute_model_prob_row(r):
        mp = r.get("model_prob")
        if pd.notna(mp):
            return mp
        mu, sigma, point = r.get("mu"), r.get("sigma"), r.get("point")
        if pd.isna(mu) or pd.isna(sigma) or pd.isna(point):
            return np.nan
        nm = r.get("name", "")
        if is_over(nm):
            return 1.0 - norm_cdf(point, mu, sigma)
        if is_under(nm):
            return       norm_cdf(point, mu, sigma)
        # For Yes/No legs, leave as NaN unless you have a binary model
        return np.nan

    df["model_prob"] = df.apply(compute_model_prob_row, axis=1)

    # ---- Per-book de-vig fair probability (two-way) ----
    df["_is_over"] = df["name"].apply(is_over)

    def book_fair(g: pd.DataFrame) -> pd.DataFrame:
        over_row  = g[g["_is_over"]==True].head(1)
        under_row = g[g["_is_over"]==False].head(1)
        if over_row.empty or under_row.empty:
            g["fair_prob_book"] = np.nan
            return g
        dec_o = over_row["dec_offered"].iloc[0]
        dec_u = under_row["dec_offered"].iloc[0]
        p_o, p_u = fair_from_two_way(dec_o, dec_u)
        g.loc[over_row.index,  "fair_prob_book"] = p_o
        g.loc[under_row.index, "fair_prob_book"] = p_u
        return g

    keys_book = ["game_id","player_key","market_std","point","bookmaker"]
    df = _reset_if_indexed(df, keys_book)
    df = df.groupby(keys_book, group_keys=False).apply(book_fair)

    # ---- Consensus de-vig (aggregate across all books for the same leg) ----
    def cons_fair(g: pd.DataFrame) -> pd.DataFrame:
        over_rows  = g[g["_is_over"]==True]
        under_rows = g[g["_is_over"]==False]
        if over_rows.empty or under_rows.empty:
            g["fair_prob_cons"] = np.nan
            return g
        q_over  = (1.0 / over_rows["dec_offered"]).sum()
        q_under = (1.0 / under_rows["dec_offered"]).sum()
        s = q_over + q_under
        if s <= 0:
            g["fair_prob_cons"] = np.nan
            return g
        p_over, p_under = q_over/s, q_under/s
        g.loc[over_rows.index,  "fair_prob_cons"] = p_over
        g.loc[under_rows.index, "fair_prob_cons"] = p_under
        return g

    keys_cons = ["game_id","player_key","market_std","point
    df = _reset_if_indexed(df, keys_cons)   # <-- add this line
    df = df.groupby(keys_cons, group_keys=False).apply(cons_fair)

    # ---- Edges & EV (straightforward) ----
    df["edge_bps_book"] = (df["model_prob"] - df["fair_prob_book"]) * 1e4
    df["edge_bps_cons"] = (df["model_prob"] - df["fair_prob_cons"]) * 1e4
    df["edge_bps"]      = df["edge_bps_cons"]  # preferred ranking signal
    df["ev"]            = df.apply(lambda r: expected_value(r["model_prob"], r["dec_offered"]), axis=1)
    df["ev_bps"]        = df["ev"] * 1e4

    # ---- Best book per leg by EV ----
    idx = df.groupby(keys_cons, sort=False)["ev_bps"].idxmax()
    best = df.loc[idx, keys_cons + ["bookmaker","price","ev_bps"]].copy()
    best.rename(columns={"bookmaker":"best_book","price":"best_price","ev_bps":"best_ev_bps"}, inplace=True)
    df = df.merge(best, on=keys_cons, how="left", validate="many_to_one")

    # ---- Model price from model_prob ----
    df["model_price"] = df["model_prob"].apply(prob_to_american)

    # ---- Friendly outputs for pages ----
    df["kick_et"]  = df["commence_time"].apply(as_iso_str)
    def _fmt_point(x):
        if pd.isna(x): return ""
        try:
            xf = float(x)
            return str(int(xf)) if float(int(xf)) == xf else f"{xf:g}"
        except Exception:
            return str(x)
    df["line_disp"] = df["point"].apply(_fmt_point)

    # Final selection & write
    keep = [
        "home_team","away_team","player","market","name","point","price","bookmaker",
        "game_id","commence_time","kick_et","player_key","market_std","team_key",
        "model_line","mu","sigma","model_prob","model_price",
        "fair_prob_book","fair_prob_cons",
        "edge_bps_book","edge_bps_cons","edge_bps",
        "dec_offered","ev","ev_bps","best_book","best_price","best_ev_bps","line_disp"
    ]
    out = df[[c for c in keep if c in df.columns]].copy()
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    out.sort_values(["edge_bps","best_ev_bps"], ascending=False, inplace=True)

    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(out):,} rows for season={args.season}, week={args.week}")

if __name__ == "__main__":
    main()
