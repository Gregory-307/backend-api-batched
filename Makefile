.ONESHELL:
.SHELLFLAGS := -c

.PHONY: run
.PHONY: uninstall
.PHONY: install
.PHONY: install-pre-commit
.PHONY: docker_build
.PHONY: docker_run
.PHONY: grid run_grid run_file run_sweeps
.PHONY: payloads lint_sweeps
.PHONY: smoke test_all
.PHONY: list_runs scaffold
.PHONY: help
.PHONY: ui


detect_conda_bin := $(shell bash -c 'if [ "${CONDA_EXE} " == " " ]; then \
    CONDA_EXE=$$((find /opt/conda/bin/conda || find ~/anaconda3/bin/conda || \
    find /usr/local/anaconda3/bin/conda || find ~/miniconda3/bin/conda || \
    find /root/miniconda/bin/conda || find ~/Anaconda3/Scripts/conda || \
    find $$CONDA/bin/conda) 2>/dev/null); fi; \
    if [ "${CONDA_EXE}_" == "_" ]; then \
    echo "Please install Anaconda w/ Python 3.10+ first"; \
    echo "See: https://www.anaconda.com/distribution/"; \
    exit 1; fi; \
    echo $$(dirname $${CONDA_EXE})')

CONDA_BIN := $(detect_conda_bin)

run:
	uvicorn main:app --reload

uninstall:
	conda env remove -n backend-api -y

install:
	if conda env list | grep -q '^backend-api '; then \
	    echo "Environment already exists."; \
	else \
	    conda env create -f environment.yml; \
	fi
	conda activate backend-api
	$(MAKE) install-pre-commit

install-pre-commit:
	/bin/bash -c 'source "${CONDA_BIN}/activate" backend-api && \
	if ! conda list pre-commit | grep pre-commit &> /dev/null; then \
	    pip install pre-commit; \
	fi && pre-commit install'

docker_build:
	docker build -t hummingbot/backend-api:latest .

docker_run:
	docker compose up -d

# ===========================================================================
# Core Commands & Helpers
# ===========================================================================

# Generate a JSON payload from a YAML grid file.
# Usage: make grid GRID=sweep_demo.yml OUT=sweep_tests.json
# Defaults: OUT is same base name with .json extension.

grid:
	@if [ -z "$(GRID)" ]; then echo 'Specify GRID=<yaml-file>'; exit 1; fi
	@out_file="${OUT}"; \
	if [ -z "$${out_file}" ]; then \
	  out_file="$(shell basename $(GRID) .yml).json"; \
	fi; \
	meta_arg=""; [ -n "$(META)" ] && meta_arg="--meta-file $(META)"; \
	python3 A_yml_to_json.py --in $$PWD/$(GRID) --out $$PWD/$$out_file $$meta_arg

# ---------------------------------------------------------------------------
# run_file – Execute a JSON payload list via B_json_to_backtests.py
# Variables:
#   FILE=<path.json>   (required)
#   WORKERS=<n>        (optional, default 4)
#   OUTFILE=<path.csv> (optional) Write results to custom CSV
# Example:
#   make run_file FILE=my_payloads.json OUTFILE=results/summaries/pmm_dynamic_2.csv
# ---------------------------------------------------------------------------
run_file:
	@if [ -z "$(FILE)" ]; then echo 'Specify FILE=<json-file>'; exit 1; fi
	@workers=$(WORKERS); if [ -z "$$workers" ]; then workers=4; fi; \
	outcsv="$(OUTFILE)"; \
	if [ -z "$$outcsv" ]; then \
	  base=$$(basename $(FILE) .json); \
	  mkdir -p results/summaries; \
	  outcsv="results/summaries/$${base}_results.csv"; \
	fi; \
	outfile_arg="--outfile $$outcsv"; \
	single_arg=""; [ -n "$(SINGLE_RUN)" ] && single_arg="--single-run"; \
	python3 B_json_to_backtests.py --file $$PWD/$(FILE) --workers $$workers $$outfile_arg $$single_arg

# ---------------------------------------------------------------------------
# run_grid – Build YAML sweep to JSON and execute it
# Variables:
#   GRID=<path.yml>    (required)
#   WORKERS=<n>        (optional, default 4)
#   OUT=<json_file>    (optional) output JSON path (defaults: same basename)
#   OUTFILE=<csv_file> (optional) final CSV name (forwarded to run_file)
# Example:
#   make run_grid GRID=sweeps/pmm_dynamic_2_sweep.yml OUTFILE=results/summaries/pmm_dynamic_2.csv
# ---------------------------------------------------------------------------
run_grid:
	@$(MAKE) grid GRID=$(GRID) OUT=$(OUT)
	@json_file="${OUT}"; if [ -z "$$json_file" ]; then json_file="$(shell basename $(GRID) .yml).json"; fi; \
	$(MAKE) run_file FILE=$$json_file WORKERS=$(WORKERS) OUTFILE=$(OUTFILE) SINGLE_RUN=$(SINGLE_RUN)

# Run all market_making sweeps in sweeps/ (curated + generated fallbacks)
run_sweeps:
	@set -e; \
	dt=$$(date +%F_%H%M%S); \
	workers="$(WORKERS)"; [ -z "$$workers" ] && workers=4; \
	meta_arg=""; [ -n "$(META)" ] && meta_arg="--meta-file $(META)"; \
	single_arg=""; [ -n "$(SINGLE_RUN)" ] && single_arg="--single-run"; \
	run_id="mm_$$dt"; \
	mkdir -p results/summaries; \
	echo "🚀 Running all market making sweeps..."; \
	python3 C_multi_yml_to_backtests.py \
	  --sweeps sweeps \
	  --workers $$workers \
	  $$meta_arg \
	  $$single_arg \
	  --run-id $$run_id \
	  --outfile results/summaries/$$run_id.csv

# ===========================================================================
# Development & CI
# ===========================================================================

# Run one backtest per controller
DEV_RUN_FLAGS ?= --sweeps sweeps --single-run --mode dev --workers $(WORKERS) --no-cache

dev_run:
	@echo "🔧 Running dev suite (one test per controller, fresh runs)..."
	@python3 C_multi_yml_to_backtests.py $(DEV_RUN_FLAGS)
	@echo "✅ Results saved → results/summaries/dev_results.csv"

# Quick smoke test: run the demo sweep.
smoke:
	@echo "💨 Running smoke test (sweep_demo.yml)..."
	@$(MAKE) run_grid GRID=sweep_demo.yml WORKERS=$(WORKERS) META=$(META)

# Build JSON payloads for every YAML in sweeps/ → payloads/<YYYY-MM-DD>/name.json
# Usage: make payloads
payloads:
	@outdir=payloads/$$(date +%F); mkdir -p $$outdir; \
	for yml in sweeps/*_sweep.yml; do \
	  name=$$(basename $$yml .yml); \
	  echo "Building $$name.json"; \
	  python3 A_yml_to_json.py --in $$yml --out $$outdir/$$name.json;
	done

# Lint all sweep files – YAML validity + grid_builder expansion
# Fails if any sweep cannot be processed.
lint_sweeps:
	python3 scripts/lint_sweeps.py sweeps

# test_all
 test_all:
	@$(MAKE) lint_sweeps; \
	set -e; \
	dt=$$(date +%F_%H%M%S); \
	workers="$(WORKERS)"; [ -z "$$workers" ] && workers=4; \
	meta_arg=""; [ -n "$(META)" ] && meta_arg="--meta-file $(META)"; \
	single_arg=""; [ -n "$(SINGLE_RUN)" ] && single_arg="--single-run"; \
	run_id="mmfull_$$dt"; \
	mkdir -p results/summaries; \
	echo "🚀 Linting and running all market making sweeps..."; \
	python3 C_multi_yml_to_backtests.py \
	  --sweeps sweeps \
	  --workers $$workers \
	  $$meta_arg \
	  $$single_arg \
	  --run-id $$run_id \
	  --outfile results/summaries/$$run_id.csv

# ===========================================================================
# Aliases & Backward-Compatibility
# ===========================================================================

.PHONY: batch sweep mmsweep dev events
batch:
	@echo "⚠️  'batch' is deprecated; use 'make run_file FILE=<json>'."; \
	$(MAKE) run_file FILE=$(FILE) WORKERS=$(WORKERS)

sweep:
	@echo "⚠️  'sweep' is deprecated; use 'make run_grid'."; \
	$(MAKE) run_grid GRID=$(GRID) WORKERS=$(WORKERS)

mmsweep:
	@echo "⚠️  'mmsweep' is deprecated; use 'make run_sweeps'."; \
	$(MAKE) run_sweeps WORKERS=$(WORKERS)

dev:
	@echo "✅ Forwarding 'dev' to 'dev_run'..."
	@$(MAKE) dev_run WORKERS=$(WORKERS) META=$(META)

events:
	@echo "⚠️  'events' is deprecated; this command is no longer supported."

list_runs:
	ls -lh results/summaries | grep "\.csv" | awk '{print $$6,$$7,$$8,$$9,$$5}'

scaffold:
	@flags=""; \
	if [ "$(show_diff)" = "true" ]; then \
	  flags="--show-diff"; \
	fi; \
	python3 scripts/scaffold_sweeps.py $$flags

# Launch the Streamlit dashboard with dev-watch (auto reload + smoke tests)
ui:
	python3 scripts/dev_watch.py

help:
	@echo "Usage: make <target> [OPTIONS...]"
	@echo ""
	@echo "Core Commands:"
	@echo "  run_file FILE=<f.json> [OUTFILE=results.csv] [WORKERS=<n>]  Run a pre-built JSON payload file."
	@echo "  run_grid GRID=<f.yml>  [OUTFILE=results.csv] [WORKERS=<n>] Build YAML sweep to JSON, then run it."
	@echo "  run_sweeps            Run all market_making sweeps (curated + generated)."
	@echo "  dev_run               Run one test for each controller (curated + generated)."
	@echo ""
	@echo "Development & CI:"
	@echo "  smoke                 Run a quick smoke test using sweep_demo.yml."
	@echo "  test_all              Lint and run all market_making sweeps."
	@echo "  lint_sweeps           Statically validate all sweep YAML files."
	@echo "  scaffold [show_diff=t]Generate stub YAMLs from controller configs."
	@echo ""
	@echo "Helpers:"
	@echo "  grid GRID=<f.yml>       Build a single YAML sweep to a JSON payload."
	@echo "  payloads              Build all YAML sweeps into a dated payloads/ dir."
	@echo "  list_runs             List completed backtest summary CSVs."
	@echo ""
	@echo "Options:"
	@echo "  WORKERS=<n>           Number of parallel backtesting workers (default: 4)."
	@echo "  META=<meta.yml>       Override dates, pair, etc., for a run."
	@echo "  OUT=<out.json>        Specify output file for 'grid' target."
	@echo "  ui                    Run Streamlit dashboard with auto-watch."

.DEFAULT_GOAL := help

# Default python interpreter (override via `make PY=python3.11 dev_run`)
PY ?= python3
