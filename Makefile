.ONESHELL:
.SHELLFLAGS := -c

.PHONY: run
.PHONY: uninstall
.PHONY: install
.PHONY: install-pre-commit
.PHONY: docker_build
.PHONY: docker_run
.PHONY: grid batch sweep
.PHONY: mmsweep


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

# ---------------------------------------------------------------------------
# Helper targets
# ---------------------------------------------------------------------------

# Generate a JSON payload list from a YAML grid file.
# Usage: make grid GRID=sweep_demo.yml OUT=sweep_tests.json
# Defaults: OUT is same base name with .json extension.

grid:
	@if [ -z "$(GRID)" ]; then echo 'Specify GRID=<yaml-file>'; exit 1; fi
	@out_file="${OUT}"; \
	if [ -z "$$out_file" ]; then \
	  out_file="$(shell basename $(GRID) .yml).json"; \
	fi; \
	python3 grid_builder.py --in $$PWD/$(GRID) --out $$PWD/$$out_file

# Run batch_tester over a payload list.
# Usage: make batch FILE=sweep_tests.json WORKERS=4
# Defaults: WORKERS=4
batch:
	@if [ -z "$(FILE)" ]; then echo 'Specify FILE=<json-file>'; exit 1; fi
	@workers=$(WORKERS); if [ -z "$$workers" ]; then workers=4; fi; \
	python3 batch_tester.py --file $$PWD/$(FILE) --workers $$workers

# Convenience: build JSON from YAML grid and immediately batch test it.
# Usage: make sweep GRID=sweep_demo.yml WORKERS=4
sweep:
	@$(MAKE) grid GRID=$(GRID) OUT=$(OUT)
	@json_file="${OUT}"; if [ -z "$$json_file" ]; then json_file="$(shell basename $(GRID) .yml).json"; fi; \
	$(MAKE) batch FILE=$$json_file WORKERS=$(WORKERS)

# Run all market_making sweeps in sweeps/ directory
mmsweep:
	python3 multi_market_sweep_tester.py --sweeps sweeps --workers $(WORKERS) --outfile mm_master_results.csv
