#!/usr/bin/env python3
import argparse, re, math
import pandas as pd
import numpy as np

# ---------- Helpers ----------

def keyify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

def norm_market(s: str) -> str:
    s0 = (s or "").strip().lower().replace(" ", "_")
    aliases = {
        # TD
        "player_anytime_td": "anytime_td", "any_time_touchdown": "anytime_td",
        "anytime_touchdown": "anytime_td", "touchdown_anytime": "anytime_td", "atd": "anytime_td",

        # Yardage / receptions (continuous)
        "player_rush_yds": "rushing_yds", "rushing_yards": "rushing_yds", "player_rushing_yards": "rushing_yds",
        "player_reception_yds": "receiving_yds", "receiving_yards": "receiving_yds", "player_receiving_yards": "receiving_yds",
        "player_pass_yds": "passing_yds", "passing_yards": "passing_yds", "player_passing_yards": "passing_yds",
        "player_receptions": "receptions",

        # Attempts/completions (treat as continuous-ish with Normal)
        "player_pass_attempts": "pass_attempts",
        "player_pass_completions": "pass_completions",
        "player_rush_attempts": "rush_attempts",

        # Discrete counts (Poisson-ish)
        "player_pass_tds": "passing_tds", "player_rush_tds": "rushing_tds", "player_receiving_tds": "receiving_tds",
        "player_pass_interceptions": "interceptions",
        "player_sacks": "sacks",
        "player_tackles_assists": "tackles_assists",
        "player_solo_tackles": "solo_tackles",
        "player_field_goals": "field_goals",
        "player_kicking_points": "kicking_points",
    }
    return aliases.get(s0, s0)

def american_to_prob(odds):
    if pd.isna(odds): return np.nan
    o = float(odds)
    return 100/(-o+100) if o < 0 else 100/(o+100)

def prob_to_american(p):
    if p is None or (isinstance(p,float) and (np.isnan(p) or p<=0 or p>=1)):
        return np.nan
    return -100*p/(1-p) if p>=0.5 else 100*(1-p)/p

# Normal CDF
def norm_cdf(x, mu, sigma):
    if sigma is None or sigma<=0 or np.isnan(sigma): return None
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))

# Poisson
def poisson_pmf(k, lam):
    if lam is None or lam<0 or np.isnan(lam) or k<0: return 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def poisson_cdf(k, lam):
    k = int(math.floor(k))
    s = 0.0
    for i in range(0, k+1):
        s += poisson_pmf(i, lam)
    return s

# ---------- Core modeling ----------

def compute_model_prob(row):
    mkt = (row.get("market_std") or "").lower()
    name = (row.get("name") or row.get("outcome") or "").lower()
    mu = row.get("mu", np.nan)
    sigma = row.get("sigma", np.nan)
    point = row.get("point", np.nan)

    # Anytime TD
    if mkt == "anytime_td":
        if not pd.isna(row.get("model_prob", np.nan)):
            return row["model_prob"]
        if pd.isna(mu): return None
        return 1.0 - math.exp(-float(mu))

    # Continuous (Normal CDF)
    continuous = {"rushing_yds","receiving_yds","receptions","passing_yds",
                  "pass_attempts","pass_completions","rush_attempts"}
    if mkt in continuous:
        if pd.isna(mu) or pd.isna(sigma) or pd.isna(point): return None
        cdf = norm_cdf(float(point), float(mu), float(sigma))
        if cdf is None: return None
        if "over" in name:  return max(0.0, min(1.0, 1.0 - cdf))
        if "under" in name: return max(0.0, min(1.0, cdf))
        return None

    # Discrete counts (Poisson)
    poisson_disc = {"passing_tds","rushing_tds","receiving_tds","interceptions",
                    "sacks","tackles_assists","solo_tackles","field_goals","kicking_points"}
    if mkt in poisson_disc:
        if pd.isna(mu) or pd.isna(point): return None
        lam = float(mu); line = float(point)
        if "over" in name:
            k = int(math.floor(line) + 1)
            return max(0.0, min(1.0, 1.0 - poisson_cdf(k-1, lam)))
        if "under" in name:
            k = int(math.floor(line))
            return max(0.0, min(1.0, poisson_cdf(k, lam)))
        return None

    return None

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props_csv", required=True)
    ap.add_argument("--params_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--markets", default="all", help="comma list or 'all'")
    ap.add_argument("--strict_inner", action="store_true", help="drop props with no model rows")
    args = ap.parse_args()

    props = pd.read_csv(args.props_csv)
    params = pd.read_csv(args.params_csv)

    # normalize
    props["player_key"] = (props["player_key"] if "player_key" in props.columns else props.get("player", props.get("name",""))).map(keyify)
    params["player_key"] = (params["player_key"] if "player_key" in params.columns else params.get("player", params.get("name",""))).map(keyify)

    props["market_std"] = (props["market_std"] if "market_std" in props.columns else props.get("market","")).astype(str).map(norm_market)
    if "market_std" in params.columns or "market" in params.columns:
        params["market_std"] = (params["market_std"] if "market_std" in params.columns else params.get("market","")).astype(str).map(norm_market)

    # filter
    if args.markets.strip().lower() != "all":
        wanted = [m.strip().lower() for m in args.markets.split(",") if m.strip()]
        props = props[props["market_std"].isin(wanted)].copy()
        if "market_std" in params.columns:
            params = params[params["market_std"].isin(wanted)].copy()

    # join
    on_cols = ["player_key"]
    if "game_id" in props.columns and "game_id" in params.columns: on_cols.append("game_id")
    if "market_std" in props.columns and "market_std" in params.columns: on_cols.append("market_std")

    how = "inner" if args.strict_inner else "left"
    merged = props.merge(params, on=on_cols, how=how, suffixes=("", "_m"))

    if "player_m" in merged.columns and "player" in merged.columns:
        merged.drop(columns=["player_m"], inplace=True)

    # implied probs
    if "price" in merged.columns:
        merged["market_prob"] = merged["price"].map(american_to_prob)

    # model probs
    merged["model_prob"] = merged.apply(compute_model_prob, axis=1)

    # fair odds & edge
    merged["model_price"] = merged["model_prob"].apply(prob_to_american)
    if "market_prob" in merged.columns:
        merged["edge_prob"] = merged["model_prob"] - merged["market_prob"]

    merged.to_csv(args.out_csv, index=False)
    print(f"[merge_td_model] Wrote {len(merged)} rows to {args.out_csv}")

if __name__ == "__main__":
    main()
