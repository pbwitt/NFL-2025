PLAYER_CSV=./data/weekly_player_stats.csv
LOOKBACKS=1 3 5
HOLDOUT=2024
SEASON?=2023
WEEK?=10

.PHONY: update qb rb wrte fppr preds

update:
\tpython scripts/pull_nfl_player_data.py --latest-week --out ./data --csv
\tpython scripts/pull_nfl_supplemental_data.py --latest-week --out ./data --csv

qb:
\tpython scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
\t  --target passing_yards --positions QB --lookbacks $(LOOKBACKS) \
\t  --split season_holdout --holdout_season $(HOLDOUT) \
\t  --predict_season $(SEASON) --predict_week $(WEEK) \
\t  --save_preds ./preds/$(SEASON)_wk$(WEEK)_qb_pass.csv

rb:
\tpython scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
\t  --target rushing_yards --positions RB --lookbacks $(LOOKBACKS) \
\t  --split season_holdout --holdout_season $(HOLDOUT) \
\t  --predict_season $(SEASON) --predict_week $(WEEK) \
\t  --save_preds ./preds/$(SEASON)_wk$(WEEK)_rb_rush.csv

wrte:
\tpython scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
\t  --target receiving_yards --positions WR TE --lookbacks $(LOOKBACKS) \
\t  --split season_holdout --holdout_season $(HOLDOUT) \
\t  --predict_season $(SEASON) --predict_week $(WEEK) \
\t  --save_preds ./preds/$(SEASON)_wk$(WEEK)_wrte_rec.csv

fppr:
\tpython scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
\t  --target fantasy_points_ppr --positions QB RB WR TE --lookbacks $(LOOKBACKS) \
\t  --split season_holdout --holdout_season $(HOLDOUT) \
\t  --predict_season $(SEASON) --predict_week $(WEEK) \
\t  --save_preds ./preds/$(SEASON)_wk$(WEEK)_fppr.csv

preds: qb rb wrte fppr
