# Codebase Reference: Testing & Automation Framework

This document summarizes the Python scripts used for running automated backtests, parameter sweeps, and regression tests.

---

## 1. `batch_tester.py`

*   **Purpose**: The primary tool for running multiple backtests in parallel. It is designed to be a lightweight and focused replacement for the older `exp_run_serial.py`.
*   **Key Features**:
    *   Reads a list of controller configurations from a JSON or YAML file.
    *   Uses a `ThreadPoolExecutor` to send multiple requests to the `/run-backtesting` endpoint concurrently.
    *   Includes logic to wait for the API to be available before starting.
    *   Implements retries with exponential backoff for network requests.
    *   Saves a summary of all results to a CSV file (e.g., `batch_results.csv`).
    *   **Crucially, it saves the full JSON response for each individual run (the "detail packet") to the `results/detail_packets/` directory for later in-depth analysis and visualization in the dashboard.**
    *   Prints a colorized summary table to the console using the `rich` library.
*   **Usage**: The main driver for parameter optimization and strategy performance comparison. Invoked via `make batch` or `make run_file`.

---

## 2. `simple_test.py`

*   **Purpose**: Acts as a critical regression and smoke-test harness for the backend API.
*   **Key Features**:
    *   Contains a hard-coded list of several known-good controller configurations (e.g., for `pmm_dynamic`, `dman_v3`).
    *   Runs each test serially against the `/run-backtesting` endpoint.
    *   Performs assertions on the results, checking that the backtest completes without an error and produces the expected data structure.
    *   Prints a clear "PASS" or "FAIL" status for each test with colorized diffs for unexpected results.
*   **Usage**: Essential for CI/CD and local development to ensure that changes to the backend or controller logic have not broken existing, working strategies. Run with `python3 simple_test.py`.

---

## 3. `grid_builder.py`

*   **Purpose**: Generates a list of JSON configuration payloads from a single, concise YAML sweep file.
*   **Key Features**:
    *   Takes a YAML file with a `base` configuration and a `grid` of parameters to sweep.
    *   Calculates the Cartesian product of all grid parameters.
    *   For each combination, it creates a full controller configuration dictionary by overlaying the grid values onto the base config.
    *   Injects metadata like `start_time`, `end_time`, and `trade_cost` into each payload.
    *   Outputs a single JSON file that is a list of these generated configurations.
*   **Usage**: The first step in running a parameter sweep. It allows you to define complex sweeps in a human-readable YAML file. Invoked via `make grid`. The output JSON is then fed into `batch_tester.py`.

---

## 4. `api_explorer.py`

*   **Purpose**: A utility script for developers to interactively inspect the backend API's file management and controller schema endpoints.
*   **Key Features**:
    *   Provides Python functions that wrap `requests.get` calls to various endpoints.
    *   Example functions include `get_controller_config`, `get_all_controllers`, and `get_controller_pydantic_schema`.
*   **Usage**: Helpful for debugging or understanding the exact structure of controller configurations as seen by the API, without needing to use the Swagger UI.

---

## 5. Legacy Tools

### `archive/legacy_scripts/exp_run_serial.py`
*   **Purpose**: An early, simplified experiment runner that runs backtests serially (one after another).
*   **Key Differences from `batch_tester.py`**:
    *   It defines the parameter grids directly within the script instead of reading them from external YAML files.
    *   It performs a rigid validation against a static JSON schema before running any tests.
    *   It lacks the parallelism, retry logic, and detailed result-saving capabilities of the modern `batch_tester.py`.
*   **Usage**: This script is kept in the archive for historical reference. It provides valuable context for understanding the evolution and design choices of the current, more advanced testing framework.

### `archive/legacy_scripts/dev_mode_batch.py`
*   **Purpose**: A developer-focused script that discovers all available controllers, generates a default configuration for each, and runs a quick backtest.
*   **Key Features**:
    *   Introspects the `bots/controllers` directory to find all strategies.
    *   Attempts to create a "sensible default" configuration for each one.
    *   Runs all backtests in parallel to provide a rapid "does it run?" check for all controllers.
*   **Usage**: Designed to give developers instant feedback after making changes that might affect multiple strategies.

### `archive/legacy_scripts/simple_test.py`
*   **Purpose**: The original, hard-coded regression test script.
*   **Key Features**:
    *   Contains a series of hand-written, known-good configurations for specific controllers.
    *   Runs each test serially and prints the result.
*   **Usage**: Served as the primary smoke test before the more robust `simple_test.py` was developed. It is retained for historical context. 