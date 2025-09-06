# =====================================
# NFL-2025 — Single Clean Makefile (fixed)
# =====================================
# --- publishing guard ---
SHELL := bash
.ONESHELL:  # each recipe runs in one shell

load_env = set -a; source .env 2>/dev/null || true; set +a


PUBLISH ?= 0           # default: build only
CONFIRM ?=             # to publish, call with CONFIRM=LIVE

.DEFAULT_GOAL := help

# ---------- Python / env ----------
PY ?= python3

# ---------- Season knobs ----------
SEASON ?= 2025
WEEK   ?= 1

.PHONY: props_now_pages

props_now_pages:
	@mkdir -p docs/props
	python3 scripts/build_props_site.py --merged_csv data/props/props_with_model_week1.csv --out docs/props/index.html --title "NFL-2025 — Player Props (Week 1)"
	python3 scripts/build_top_picks.py   --merged_csv data/props/props_with_model_week1.csv --out docs/props/top.html --week 1
	python3 scripts/build_consensus_page.py --merged_csv data/props/props_with_model_week1.csv --out docs/props/consensus.html --week 1
	touch docs/.nojekyll

# ---------- .env (e.g., ODDS_API_KEY) ----------
ifneq (,$(wildcard .env))
-include .env
export ODDS_API_KEY
export
endif

# ---------- Paths ----------
DATA_DIR      := data
PROPS_DIR     := $(DATA_DIR)/props
DOCS_DIR      := docs

# Files (props)
PROPS_LATEST  := $(PROPS_DIR)/latest_all_props.csv
PARAMS_CSV    := $(PROPS_DIR)/params_week$(WEEK).csv
MERGED_PROPS  := $(PROPS_DIR)/props_with_model_week$(WEEK).csv
PROPS_HTML    := $(DOCS_DIR)/props/index.html
CONS_HTML     := $(DOCS_DIR)/props/consensus.html

# Files (edges/home)

.PHONY: odds
ODDS_OUTDIR := data/odds

odds: setup
	$(load_env)
	@mkdir -p $(ODDS_OUTDIR)
	@$(PY) scripts/fetch_odds.py \
		--sport_key americanfootball_nfl \
		--markets h2h,spreads,totals \
		--regions us \
		--odds_format american \
		> $(ODDS_OUTDIR)/latest.csv
	@echo ">> wrote $(ODDS_OUTDIR)/latest.csv"









PRED_OUT      := $(DATA_DIR)/predictions/latest_predictions.csv
MERGED_OUT    := $(DATA_DIR)/merged/latest_with_edges.csv

TOP_HTML  := $(DOCS_DIR)/props/top.html


# ---------- PHONY ----------
.PHONY: help setup check_key serve clean \
        odds elo predict merge site_home \
        fetch_props make_params make_edges build_props build_consensus \
        props_now monday monday_all weekly publish_site \
        td_merge td_page td_props_now

# ----------------------------------
# Help
# ----------------------------------
help:
	@echo "Targets:"
	@echo "  monday_all  - Full run (edges + props + consensus) and publish"
	@echo "  props_now   - Props end-to-end (incl. Consensus) and publish"
	@echo "  td_props_now- TD-only props page and publish"
	@echo "  serve       - Local preview at http://127.0.0.1:8080/"
	@echo "  clean       - Remove generated CSVs (keeps docs/)"
	@echo ""
	@echo "Vars: SEASON=$(SEASON) WEEK=$(WEEK)"

check_key:
	@echo "ODDS_API_KEY prefix: $${ODDS_API_KEY:0:6}******"

setup:
	mkdir -p $(DOCS_DIR)/props $(PROPS_DIR) $(DATA_DIR)/predictions $(DATA_DIR)/merged $(ODDS_OUTDIR)
	touch $(DOCS_DIR)/.nojekyll


# ----------------------------------
# Team edges → Home (keep your existing scripts)
# ----------------------------------


elo:
	$(PY) scripts/build_elo_2024.py

predict: odds elo
	$(PY) scripts/make_predictions_from_elo.py \
	--odds $(ODDS_OUTDIR)/games_latest.csv \
	--elo data/models/elo_2024.csv \
	--out $(PRED_OUT)



merge: predict
	$(PY) scripts/join_predictions_with_odds.py \
	  --preds $(PRED_OUT) \
	  --odds $(ODDS_OUTDIR)/latest.csv \
	  --out $(MERGED_OUT)

.PHONY: site_home
site_home:
	@mkdir -p $(DOCS_DIR)
	@touch $(DOCS_DIR)/.nojekyll
	@echo "[site_home] using static $(DOCS_DIR)/index.html (not overwritten)"

# ----------------------------------
# All-props pipeline (new, unified)
# ----------------------------------
fetch_props: setup
	$(load_env)
	$(PY) scripts/fetch_all_player_props.py --season $(SEASON) --week $(WEEK) --out $(PROPS_LATEST)
	@echo ">> wrote $(PROPS_LATEST)"


make_params:
	$(PY) scripts/make_player_prop_params.py \
	  --season $(SEASON) --week $(WEEK) \
	  --props_csv $(PROPS_LATEST) \
	  --out $(PARAMS_CSV)

make_edges:
	$(PY) scripts/make_props_edges.py \
	  --season $(SEASON) --week $(WEEK) \
	  --props_csv $(PROPS_LATEST) \
	  --params_csv $(PARAMS_CSV) \
	  --out $(MERGED_PROPS)

props:
	$(PY) scripts/build_props_site.py \
	  --merged_csv $(MERGED_PROPS) \
	  --out $(PROPS_HTML) \
	  --title "NFL-2025 — Player Props (Week $(WEEK))"

build_consensus:
	$(PY) scripts/build_consensus_page.py \
	  --merged_csv $(MERGED_PROPS) \
	  --out $(CONS_HTML) \
	  --title "NFL-2025 — Consensus vs Best Book (Week $(WEEK))"


# One-shot props (with Consensus) + publish
props_now:
	@echo ">> SEASON=$(SEASON)  WEEK=$(WEEK)"
	$(MAKE) fetch_props
	$(MAKE) make_params
	$(MAKE) make_edges
	$(MAKE) build_props
	$(MAKE) build_top
	$(MAKE) build_consensus
	touch docs/.nojekyll
	@echo ">> build complete (Props + Top + Consensus)."
	@if [ "$(PUBLISH)" = "1" ] && [ "$(CONFIRM)" = "LIVE" ]; then \
		echo ">> publishing to GitHub Pages..."; \
		touch docs/.nojekyll; \
		git add -A docs; \
		git commit -m "props: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || true; \
		git push -u origin main || true; \
	else \
		echo ">> SKIP publish (PUBLISH=$(PUBLISH) CONFIRM=$(CONFIRM))"; \
		echo ">> preview locally: make serve  # http://127.0.0.1:8080/props/"; \
	fi


props_now_dev:      ## build only (no publish)
	@$(MAKE) props_now PUBLISH=0

props_now_pub:      ## build + publish (requires CONFIRM=LIVE)
	@$(MAKE) props_now PUBLISH=1 CONFIRM=LIVE

monday_all_pub:     ## full weekly run + publish (requires CONFIRM=LIVE)
	@$(MAKE) monday_all PUBLISH=1 CONFIRM=LIVE





# ----------------------------------
# TD-only quick path (kept from your file, fixed)
# ----------------------------------
td_merge: fetch_props make_params
	$(PY) scripts/merge_td_model.py \
	  --props_csv $(PROPS_LATEST) \
	  --params_csv $(PARAMS_CSV) \
	  --out_csv $(MERGED_PROPS) \
	  --market anytime_td

td_page: td_merge
	$(PY) scripts/build_td_edges_page.py \
	  --merged_csv $(MERGED_PROPS) \
	  --out $(PROPS_HTML) \
	  --min_prob 0.02 \
	  --limit 250
	touch $(DOCS_DIR)/.nojekyll

td_props_now: td_page
	git add -A $(DOCS_DIR)
	git commit -m "publish TD props: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || true
	git push -u origin main || true

# ----------------------------------
# Full weekly run & publish
# ----------------------------------
weekly: odds site_home props_now
	@echo "✅ weekly (Season=$(SEASON) Week=$(WEEK)) complete"

monday_all: weekly
monday: weekly

# ----------------------------------
# Publish / Serve / Clean
# ----------------------------------
publish_site:
	touch $(DOCS_DIR)/.nojekyll
	git add -A $(DOCS_DIR)
	git commit -m "publish: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" || true
	git push -u origin main || true

serve:
	$(PY) -m http.server 8080 -b 127.0.0.1 -d $(DOCS_DIR)

clean:
	rm -f $(PRED_OUT) $(MERGED_OUT) \
	      $(PROPS_DIR)/params_week*.csv \
	      $(PROPS_DIR)/props_with_model_week*.csv

.PHONY: build_top
	build_top: ## Build Top Picks page (cards/filters)
	$(PY) scripts/build_top_picks.py --merged_csv $(TOP_MERGED) --out docs/props/top.html --title "Fourth & Value — Top Picks"
	touch docs/.nojekyll
