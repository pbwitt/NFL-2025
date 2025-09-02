# =====================================
# NFL-2025 — Single Clean Makefile
# =====================================
# One-shot full pipeline (edges + props) → static site → publish to docs/
# Supports Week-1 bootstrap and normal Week-2+ weekly runs.

# ---------- Python / env ----------
PY ?= python3

# ---------- Season knobs ----------
SEASON ?= 2025
# Default to Week 2 going forward; override as needed: `make weekly WEEK=3`
WEEK   ?= 1

# Load .env if present (e.g., ODDS_API_KEY)
ifneq (,$(wildcard .env))
-include .env
export ODDS_API_KEY
export
endif


# ---------- Data paths ----------
DATA_DIR      := data
ODDS_OUTDIR   := $(DATA_DIR)/odds
PRED_OUT      := $(DATA_DIR)/predictions/latest_predictions.csv
MERGED_OUT    := $(DATA_DIR)/merged/latest_with_edges.csv

# Player CSV (for ML position models)
PLAYER_CSV    := $(DATA_DIR)/weekly_player_stats.csv
LOOKBACKS     := 1 3 5
HOLDOUT       := 2024

# ---------- Site paths ----------
SITE_DIR      := site
PAGES_DIR     := docs

# ---------- PHONY ----------
.PHONY: help \
        update qb rb wrte fppr preds \
        odds elo predict merge site serve clean \
        props_odds_all player_props_pred_all props_merge_all site_props \
        props_now monday weekly week1_bootstrap week1_all monday_all \
        site_home publish_site

.PHONY: check_key
check_key:
	@echo "ODDS_API_KEY prefix: $${ODDS_API_KEY:0:6}******"


# ----------------------------------
# Help
# ----------------------------------
help:
	@echo "Targets:"
	@echo "  monday_all       - Run EVERYTHING (edges + props) and publish (Week $(WEEK), Season $(SEASON))"
	@echo "  weekly           - Same as monday_all (alias)"
	@echo "  week1_all        - One-time Week-1 bootstrap (edges + props) + publish"
	@echo "  props_now        - Only refresh player props (all steps) + publish"
	@echo "  serve            - Local preview of docs/ at http://127.0.0.1:8080"
	@echo "  clean            - Remove built CSV/merged outputs (keeps site/docs)"
	@echo ""
	@echo "Player models:"
	@echo "  update           - Refresh player CSVs"
	@echo "  qb|rb|wrte|fppr  - Run position models; 'preds' runs all four"
	@echo ""
	@echo "Team edges pipeline:"
	@echo "  odds -> elo -> predict -> merge -> site"
	@echo ""
	@echo "Props pipeline:"
	@echo "  props_odds_all -> player_props_pred_all -> props_merge_all -> site_props"
	@echo ""
	@echo "Publish:"
	@echo "  publish_site     - Copy site/ -> docs/, add .nojekyll, commit, push"

# ----------------------------------
# Player prediction pipeline (optional, if/when you use player-level ML)
# ----------------------------------
update:
	$(PY) scripts/pull_nfl_player_data.py --latest-week --out $(DATA_DIR) --csv
	$(PY) scripts/pull_nfl_supplemental_data.py --latest-week --out $(DATA_DIR) --csv

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

# ----------------------------------
# Team edges pipeline (odds → elo → predict → merge → site)
# ----------------------------------
odds:
	$(PY) scripts/fetch_odds.py --markets h2h,spreads,totals --regions us

elo:
	$(PY) scripts/build_elo_2024.py

predict: elo
	@test -f $(ODDS_OUTDIR)/latest.csv || (echo "ERROR: $(ODDS_OUTDIR)/latest.csv not found. Run 'make odds' first." && exit 1)
	$(PY) scripts/make_predictions_from_elo.py \
	  --odds $(ODDS_OUTDIR)/latest.csv \
	  --elo data/models/elo_2024.csv \
	  --out $(PRED_OUT)

merge: predict
	$(PY) scripts/join_predictions_with_odds.py \
	  --preds $(PRED_OUT) \
	  --odds $(ODDS_OUTDIR)/latest.csv \
	  --out $(MERGED_OUT)

# Build the weekly site under ./site (edges page & home)
site: merge
	$(PY) scripts/export_weekly_site.py
	# If you also render a separate edges page, keep this:
	# $(PY) scripts/export_homepage.py

# ----------------------------------
# Player props pipeline (all props → params → merge → site/props)
# ----------------------------------
props_odds_all:
	$(PY) scripts/fetch_all_player_props.py

player_props_pred_all:
	# For WEEK=1 this script should automatically use prior-season history.
	$(PY) scripts/make_player_prop_params.py --season $(SEASON) --week $(WEEK)

props_merge_all:
	$(PY) scripts/join_all_player_props_with_preds.py

site_props:
	$(PY) scripts/export_props_site.py

# Quick props-only refresh + publish

# ----------------------------------
# Combined one-shots
# ----------------------------------

# Normal weekly run (Week 2 and beyond): edges + props + publish
weekly: odds merge site props_odds_all player_props_pred_all props_merge_all site_props publish_site
	@echo "✅ weekly (Season=$(SEASON) Week=$(WEEK)) complete"

# Alias that matches your habit
monday_all: weekly

# Week-1 bootstrap (no current-season stats yet): edges + props + publish
# Override WEEK on call if needed: `make week1_all WEEK=1`
week1_bootstrap:
	@echo "• Week-1 bootstrap: using Elo 2024 + opening odds"
	$(MAKE) odds
	$(MAKE) merge
	$(MAKE) site

week1_all: week1_bootstrap props_odds_all
	# For WEEK=1, player params script is expected to backfill from prior season
	$(MAKE) player_props_pred_all WEEK=1
	$(MAKE) props_merge_all
	$(MAKE) site_props
	$(MAKE) publish_site
	@echo "🎉 week1_all complete"

# Back-compat alias if you still type this
monday: weekly

# ----------------------------------
# Publish to GitHub Pages (docs/)
# ----------------------------------

# Local preview & housekeeping
# ----------------------------------
serve:
	$(PY) -m http.server 8080 -d $(PAGES_DIR)

clean:
	rm -f $(PRED_OUT) $(MERGED_OUT)

# Optional: build a homepage separately if you keep that script
site_home:
	$(PY) scripts/export_homepage.py

player_props_params:
	@if [ -z "$(WEEK)" ]; then \
		echo "ERROR: you must pass WEEK, e.g. make player_props_params WEEK=1"; \
		exit 1; \
	fi
		@mkdir -p data/props
		python3 scripts/make_player_prop_params.py \
			--season $(SEASON) --week $(WEEK) \
			--out data/props/params_week$(WEEK).csv

	# Load env (safe: ignores if .env missing)
	# --- NFL-2025 publish targets ---
-include .env

.PHONY: edges_now props_now monday_all publish_site

edges_now:
	python3 scripts/build_edges_site.py --out docs/edges/index.html

props_now:
	python3 scripts/build_props_site.py --out docs/props/index.html --days 7
	touch docs/.nojekyll
	git add -A docs
	git commit -m "props: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || echo "Nothing to commit"
	git push

odds:
	python3 scripts/fetch_odds.py

monday_all:
	@$(MAKE) edges_now
	@$(MAKE) props_now

publish_site:
	touch docs/.nojekyll
	git add -A docs
	git commit -m "publish: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || echo "Nothing to commit"
	git push



	# TD props merge & page
td_merge:
	python3 scripts/merge_td_model.py \
  	--props_csv data/props/latest_all_props.csv \
		--params_csv data/props/params_week$(WEEK).csv \
		--out_csv data/props/props_with_model_week$(WEEK).csv \
		--market anytime_td

td_page:
	python3 scripts/build_td_edges_page.py \
	--merged_csv data/props/props_with_model_week$(WEEK).csv \
	--out docs/props/index.html \
	--min_prob 0.02 \
	--limit 250

props_now: td_merge td_page
	@touch docs/.nojekyll
	@mkdir -p docs/props
	git add -A docs
	git commit -m "publish TD props: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || true
	git push -u origin main || true




td_page:
python3 scripts/build_props_site.py \
	--merged_csv data/props/props_with_model_week$(WEEK).csv \
	--out docs/props/index.html \
	--title "NFL-2025 — TD Props (Week $(WEEK))" \
	--min_prob 0.01 \
	--limit 3000
