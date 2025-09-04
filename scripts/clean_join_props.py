#!/usr/bin/env python3
import argparse, pathlib, sys
import pandas as pd
from typing import Dict

# --- 1) Canonical market mapping ---
CANON_MAP: Dict[str, str] = {
    # passing
    "player_pass_yds": "pass_yds",
    "passing_yards": "pass_yds",
    "pass_yds": "pass_yds",
    "player_pass_tds": "pass_tds",
    "passing_tds": "pass_tds",
    "pass_tds": "pass_tds",
    "player_pass_attempts": "pass_att",
    "pass_attempts": "pass_att",
    "player_pass_completions": "pass_cmp",
    "pass_completions": "pass_cmp",
    "player_pass_interceptions": "pass_int",
    "interceptions": "pass_int",

    # receiving
    "player_receptions": "rec",
    "receptions": "rec",
    "player_reception_yds": "rec_yds",
    "receiving_yards": "rec_yds",
    "rec_yds": "rec_yds",
    "player_reception_tds": "rec_tds",
    "receiving_tds": "rec_tds",

    # rushing
    "player_rush_yds": "rush_yds",
    "rushing_yards": "rush_yds",
    "player_rush_attempts": "rush_att",
    "rushing_attempts": "rush_att",
    "player_rush_tds": "rush_tds",
    "rushing_tds": "rush_tds",

    # defense / kickers / specials
    "player_sacks": "sacks",
    "player_solo_tackles": "solo_tk",
    "player_tackles_assists": "tkl_ast",
    "player_field_goals": "fg_made",
    "player_kicking_points": "k_pts",
    "player_anytime_td": "anytime_td",
}

def canon_market(x: str) -> str:
    if not isinstance(x, str): return "unknown"
    key = x.strip().lower().replace(" ", "_")
    return CANON_MAP.get(key, key)

def canon_player(x: str) -> str:
    # normalize name "D.J. Moore" -> "dj moore"
    return " ".join(x.replace(".", "").split()).lower() if isinstance(x, str) else x

def load_csv(path: str) -> pd.DataFrame:
    p = pathlib.Path(path)
    if not p.exists():
        sys.exit(f"ERROR: file not found: {path}")
    return pd.read_csv(p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props_csv", required=True, help="Raw props CSV (from fetch_all_player_props.py)")
    ap.add_argument("--params_csv", required=True, help="Model params per (player,market) — e.g., data/props/params_weekX.csv")
    ap.add_argument("--out_merged", required=True, help="Output merged CSV with model vs line edges")
    ap.add_argument("--out_coverage", required=True, help="Output coverage CSV by market")
    ap.add_argument("--week", type=int, default=1)
    args = ap.parse_args()

    props = load_csv(args.props_csv)
    params = load_csv(args.params_csv)

    # --- 2) Normalize key fields ---
    # expect props to have at least: player, team (or home/away & player_team), market, line, price, bookmaker, event_time, etc.
    if "player" not in props.columns or "market" not in props.columns:
        sys.exit("ERROR: props CSV must contain 'player' and 'market' columns.")

    props["player_key"]  = props["player"].map(canon_player)
    props["market_std"]  = props["market"].map(canon_market)

    # Common team field if present
    team_col = "team" if "team" in props.columns else None
    if not team_col and "player_team" in props.columns:
        team_col = "player_team"
    if team_col:
        props["team_key"] = props[team_col].astype(str).str.upper().str.strip()
    else:
        props["team_key"] = ""

    # Params expectation: at minimum (player, market) or (player, market, team) + some model fields
    needed_params_cols = {"player","market"}
    if not needed_params_cols.issubset(set(params.columns)):
        sys.exit("ERROR: params CSV must have at least 'player' and 'market' columns.")
    params["player_key"] = params["player"].map(canon_player)
    params["market_std"] = params["market"].map(canon_market)
    if "team" in params.columns:
        params["team_key"] = params["team"].astype(str).str.upper().str.strip()
    else:
        params["team_key"] = ""

    # --- 3) Define model output columns (adapt if your params file uses different names) ---
    # Try common possibilities; keep whatever exists.
    candidate_model_cols = [
        "model_line", "pred", "prediction", "mu", "mean",   # central value
        "sigma", "std", "stdev",                            # dispersion
        "p_over", "p_under", "edge", "ev"                   # probabilities / value
    ]
    model_cols = [c for c in candidate_model_cols if c in params.columns]

    # --- 4) Robust merge with safe fallback (no shape-mismatch assignments) ---

    # Choose model-related columns that actually exist in params
    _base_model_cols = [
        "model_line", "pred", "prediction", "mean", "mu", "sigma",
        "model_prob", "model_price"  # these may exist after anytime-TD patch
    ]
    model_cols = [c for c in _base_model_cols if c in params.columns]

    key_cols = ["player_key", "market_std", "team_key"]

    # 4.1 Primary merge on (player, market, team)
    merged = props.merge(
        params[key_cols + model_cols],
        on=key_cols, how="left", suffixes=("", "_model")
    )

    # 4.2 Fallback on (player, market) only — aligned to props row-for-row
    fb = props[["player_key", "market_std"]].merge(
        params[["player_key", "market_std"] + model_cols].drop_duplicates(subset=["player_key", "market_std"]),
        on=["player_key", "market_std"],
        how="left",
        suffixes=("", "_fb")
    )

    # 4.3 Fill NaNs from the fallback columns (same length as props/merged)
    for c in model_cols:
        merged[c] = merged[c].fillna(fb[c])

    # --- 5) Compute edges/leans for continuous markets (when a numeric book line exists) ---
    # Prefer a column named 'point' for sportsbook line; otherwise try common alternates.
    line_col = None
    for guess in ["point", "line", "prop_line", "odds_line", "value", "total"]:
        if guess in merged.columns:
            line_col = guess
            break

    # If we still don't have model_line, derive it from typical central-tendency columns
    # --- Derive a usable model_line for all markets ---
    # Ensure the column exists
    if "model_line" not in merged.columns:
        merged["model_line"] = pd.NA

    # Fill in missing model_line values from other model outputs
    for src in ["pred", "prediction", "mean", "mu"]:
        if src in merged.columns:
            merged["model_line"] = merged["model_line"].fillna(merged[src])

    # Edge only makes sense when a numeric sportsbook line exists (yards/attempts/etc.)
    if line_col and "model_line" in merged.columns:
        merged["edge"] = merged["model_line"] - merged[line_col]
        merged["edge_abs"] = merged["edge"].abs()
        merged["lean"] = merged["edge"].apply(
            lambda x: "OVER" if pd.notna(x) and x > 0 else ("UNDER" if pd.notna(x) and x < 0 else "")
        )

    # --- 6) Coverage report (treat binary markets as covered if model_prob is present) ---
    has_model = merged["model_line"].notna()
    if "model_prob" in merged.columns:
        has_model = has_model | merged["model_prob"].notna()

    coverage = (
        merged.assign(has_model=has_model)
              .groupby("market_std", as_index=False)
              .agg(total=("market_std", "size"), with_model=("has_model", "sum"))
    )
    coverage["coverage_pct"] = (coverage["with_model"] / coverage["total"]).round(3)

    # --- 7) Save outputs ---
    out_merged = pathlib.Path(args.out_merged); out_merged.parent.mkdir(parents=True, exist_ok=True)
    out_cov    = pathlib.Path(args.out_coverage); out_cov.parent.mkdir(parents=True, exist_ok=True)

    merged.to_csv(out_merged, index=False)
    coverage.sort_values(["coverage_pct","market_std"], ascending=[False, True]).to_csv(out_cov, index=False)

    print(f"[props] merged -> {out_merged}  ({len(merged):,} rows; NaN model_line = {merged['model_line'].isna().sum()})")
    print(f"[props] coverage -> {out_cov}")


if __name__ == "__main__":
    main()
