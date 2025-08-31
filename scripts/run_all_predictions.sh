#!/bin/sh
set -eu

PLAYER_CSV=./data/weekly_player_stats.csv
SEASON=2023      # change to 2025 in-season
WEEK=10          # change weekly
HOLDOUT=2024     # last full season
LOOKBACKS="1 3 5"

mkdir -p preds

run() {
  name="$1"; shift
  echo "=== Running $name for ${SEASON} Wk ${WEEK} ==="
  python scripts/ml_player_pipeline.py \
    --player_csv "$PLAYER_CSV" \
    "$@" \
    --lookbacks $LOOKBACKS \
    --split season_holdout --holdout_season "$HOLDOUT" \
    --predict_season "$SEASON" --predict_week "$WEEK" \
    --save_preds "./preds/${SEASON}_wk${WEEK}_${name}.csv"
}

# Jobs
run qb_pass  --target passing_yards      --positions QB
run rb_rush  --target rushing_yards      --positions RB
run wrte_rec --target receiving_yards    --positions WR TE
run fppr     --target fantasy_points_ppr --positions QB RB WR TE
