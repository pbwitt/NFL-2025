# --- NFL-2025 Makefile (merged: player pipeline + odds/Elo/site) ---

# Python interpreter
PY ?= python3

# ---------- Player-level pipeline knobs ----------
PLAYER_CSV := ./data/weekly_player_stats.csv
LOOKBACKS  := 1 3 5
HOLDOUT    := 2024
SEASON    ?= 2025
WEEK      ?= 1

# ---------- Team/odds/site paths ----------
ODDS_OUTDIR := data/odds
PRED_OUT    := data/predictions/latest_predictions.csv
MERGED_OUT  := data/merged/latest_with_edges.csv

.PHONY: help update qb rb wrte fppr preds odds fetch-odds elo predict merge site serve week1_now monday players_monday clean

# -------- Help --------
help:
	@echo "Targets:"
	@echo "  update           - Refresh player data CSVs"
	@echo "  qb|rb|wrte|fppr - Run player models for the given position(s)"
	@echo "  preds            - Run all player models (qb rb wrte fppr)"
	@echo "  odds             - Fetch latest sportsbook odds (h2h/spreads/totals)"
	@echo "  elo              - Build Elo ratings from 2024 season"
	@echo "  predict          - Make Week-1 predictions from Elo + odds games"
	@echo "  merge            - Join predictions with odds and compute edges"
	@echo "  site             - Export static site to ./site"
	@echo "  serve            - Serve ./site at http://localhost:8000"
	@echo "  week1_now        - One-click: odds → predict → merge → site"
	@echo "  monday           - Weekly run during season: odds → predict → merge → site"
	@echo "  players_monday   - Player data refresh + all player preds (override SEASON/WEEK as needed)"
	@echo "  clean            - Remove generated prediction/merged CSVs"
	@echo ""
	@echo "Examples:"
	@echo "  make week1_now"
	@echo "  make serve"
	@echo "  make preds SEASON=2025 WEEK=1"
	@echo "  make qb SEASON=2025 WEEK=2 LOOKBACKS=\"3 5 8\""

# -------- Player prediction pipeline --------
update:
	$(PY) scripts/pull_nfl_player_data.py --latest-week --out ./data --csv
	$(PY) scripts/pull_nfl_supplemental_data.py --latest-week --out ./data --csv




qb:
	$(PY) scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
	  --target passing_yards --positions QB --lookbacks $(LOOKBACKS) \
	  --split season_holdout --holdout_season $(HOLDOUT) \
	  --predict_season $(SEASON) --predict_week $(WEEK) \
	  --save_preds ./preds/$(SEASON)_wk$(WEEK)_qb_pass.csv

rb:
	$(PY) scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
	  --target rushing_yards --positions RB --lookbacks $(LOOKBACKS) \
	  --split season_holdout --holdout_season $(HOLDOUT) \
	  --predict_season $(SEASON) --predict_week $(WEEK) \
	  --save_preds ./preds/$(SEASON)_wk$(WEEK)_rb_rush.csv

wrte:
	$(PY) scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
	  --target receiving_yards --positions WR TE --lookbacks $(LOOKBACKS) \
	  --split season_holdout --holdout_season $(HOLDOUT) \
	  --predict_season $(SEASON) --predict_week $(WEEK) \
	  --save_preds ./preds/$(SEASON)_wk$(WEEK)_wrte_rec.csv

fppr:
	$(PY) scripts/ml_player_pipeline.py --player_csv $(PLAYER_CSV) \
	  --target fantasy_points_ppr --positions QB RB WR TE --lookbacks $(LOOKBACKS) \
	  --split season_holdout --holdout_season $(HOLDOUT) \
	  --predict_season $(SEASON) --predict_week $(WEEK) \
	  --save_preds ./preds/$(SEASON)_wk$(WEEK)_fppr.csv

preds: qb rb wrte fppr

# -------- Odds, Elo predictions, merge, site --------
odds fetch-odds:
	$(PY) scripts/fetch_odds.py --markets h2h,spreads,totals --regions us

elo:
	$(PY) scripts/build_elo_2024.py

# Predict using Elo + the matchups present in your odds file
predict: elo
	@test -f $(ODDS_OUTDIR)/latest.csv || (echo "ERROR: $(ODDS_OUTDIR)/latest.csv not found. Run 'make odds' first." && exit 1)
	$(PY) scripts/make_predictions_from_elo.py --odds $(ODDS_OUTDIR)/latest.csv --elo data/models/elo_2024.csv --out $(PRED_OUT)

# Join predictions with odds and compute edges
merge: predict
	$(PY) scripts/join_predictions_with_odds.py --preds $(PRED_OUT) --odds $(ODDS_OUTDIR)/latest.csv --out $(MERGED_OUT)

# Export static website to ./site
site: merge
	$(PY) scripts/export_weekly_site.py

# Local preview
serve:
	cd site && $(PY) -m http.server 8000

# One-click Week 1 bootstrap (no current-season stats needed)
week1_now:
	$(MAKE) odds
	$(MAKE) predict
	$(MAKE) merge
	$(MAKE) site

# Weekly during season
monday:
	$(MAKE) odds
	$(MAKE) predict
	$(MAKE) merge
	$(MAKE) site

# Player pipeline weekly helper (override SEASON/WEEK as needed)
players_monday:
	$(MAKE) update
	$(MAKE) preds

clean:
	rm -f $(PRED_OUT) $(MERGED_OUT)


.PHONY: props_odds_all player_props_pred_all props_merge_all site_props

	# 1) Fetch all NFL player props for events in your latest odds file
props_odds_all:
	python3 scripts/fetch_all_player_props.py

	# 2) Build Week-N player parameters (uses last season for WEEK=1, else weeks 1..N-1 of current season)
player_props_pred_all:
	python3 scripts/make_player_prop_params.py --season $(SEASON) --week $(WEEK)


	# 3) Join props with projections and compute edges
props_merge_all:
	python3 scripts/join_all_player_props_with_preds.py

	# 4) Export a props page under site/props/
site_props:
	python3 scripts/export_props_site.py


	.PHONY: props_now monday_all
	props_now:
		$(MAKE) props_odds_all
		$(MAKE) player_props_pred_all
		$(MAKE) props_merge_all
		$(MAKE) site_props

	monday_all:
		$(MAKE) monday      # team edges: odds → predict → merge → site
		$(MAKE) props_now   # player props: odds → params → merge → props site

.PHONY: site_home
site_home:
		python3 scripts/export_homepage.py


.PHONY: publish
	publish:
		rm -rf docs && mkdir -p docs
		cp -R site/* docs/
		@echo "Copied site → docs. Commit & push, then enable GitHub Pages (docs/ on main)."
