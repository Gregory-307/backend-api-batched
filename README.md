# Backend API 

## Overview
Backend-api is a dedicated solution for managing Hummingbot instances. It offers a robust backend API to streamline the deployment, management, and interaction with Hummingbot containers. This tool is essential for administrators and developers looking to efficiently handle various aspects of Hummingbot operations.

## Features
- **Deployment File Management**: Manage files necessary for deploying new Hummingbot instances.
- **Container Control**: Effortlessly start and stop Hummingbot containers.
- **Archiving Options**: Securely archive containers either locally or on Amazon S3 post-removal.
- **Direct Messaging**: Communicate with Hummingbots through the broker for effective control and coordination.

## Getting Started

### Conda Installation
1. Install the environment using Conda:
   ```bash
   conda env create -f environment.yml
   ```
2. Activate the Conda environment:
   ```bash
   conda activate backend-api
   ```

### Running the API with Conda
Run the API using uvicorn with the following command:
   ```bash
   uvicorn main:app --reload
   ```

### Docker Installation and Running the API
For running the project using Docker, follow these steps:

1. **Set up Environment Variables**:
   - Execute the `set_environment.sh` script to configure the necessary environment variables in the `.env` file:
     ```bash
     ./set_environment.sh
     ```

2. **Build and Run with Docker Compose**:
   - After setting up the environment variables, use Docker Compose to build and run the project:
     ```bash
     docker compose up --build
     ```

   - This command will build the Docker image and start the containers as defined in your `docker-compose.yml` file.

### Usage
This API is designed for:
- **Deploying Hummingbot instances**
- **Starting/Stopping Containers**
- **Archiving Hummingbots**
- **Messaging with Hummingbot instances**

To test these endpoints, you can use the [Swagger UI](http://localhost:8000/docs) or [Redoc](http://localhost:8000/redoc).

## Contributing
Contributions are welcome! For support or queries, please contact us on Discord.

---
## Usage Guide (Quick Reference)
> _Updated 2025-06-26 – Docker-first workflow; Make targets explained_

### 0. One-time prerequisites
* Docker & Docker Compose installed (Docker Desktop on Windows/Mac or `docker-ce` on Linux).
* **Optional for local Python runs**: Conda ≥23 / Miniconda.  _Skip if you will only use Docker._

### 1. Run with Docker (recommended)
```bash
# Build image & start backend + broker (EMQX)
docker compose up --build 
backend-api  # Ctrl-C to stop

# Optional: background mode
docker compose up -d 
backend-api
```
* FastAPI API → http://localhost:8000  (docs at /docs)
* Streamlit dashboard is _not_ in the container; run locally (step 2).

### 2. Front-end (Streamlit) with auto-watch
```bash
# Start smoke-tests + dashboard (requires host Python, no Conda needed)
python3 scripts/dev_watch.py     # opens http://localhost:8501
```
The watcher sequence:
1. Python compile test (`quick_smoke.py`)
2. Headless UI test (`ui_smoke.py`)
3. Launches Streamlit with hot-reload if both pass.

### 3. Makefile helpers (batch tests & sweeps)
| Target | Description |
|--------|-------------|
| `make docker_build` | Build backend Docker image (`Dockerfile`). |
| `make docker_run`   | `docker compose up -d` shortcut. |
| `make grid GRID=*.yml` | Convert YAML sweep → JSON payload list. |
| `make payloads` | Build JSON payloads for every sweep into `payloads/<date>/`. |
| `make lint_sweeps` | Static validation of all sweep YAMLs. |
| `make test_all WORKERS=4` | Lint + run full multi-sweep, CSV saved under `results/summaries/`. |
| `make dev WORKERS=4` | Quick smoke-test run (see previous behaviour). |
| `make run_file FILE=tests.json WORKERS=4` | Run `batch_tester.py` over JSON list. |
| `make run_grid GRID=grid.yml WORKERS=4`   | Build JSON _and_ batch test it. |
| `make run_sweeps WORKERS=4` | Full multi-sweep run; CSV in `results/summaries/` |
| `make smoke WORKERS=4` | Quick lint + mini-run smoke test. |
| `make scaffold` | Generate stub YAML sweeps for every controller; writes to `sweeps/generated/`. |

### 4. Local Python env (optional)
```

#### Example – run a single sweep and save to a named CSV

```bash
# full grid scan just for the curated pmm_dynamic_2 sweep
make run_grid \
    GRID=sweeps/pmm_dynamic_2_sweep.yml \
    WORKERS=4 \
    OUTFILE=results/summaries/pmm_dynamic_2.csv
```

The sequence:

1. Converts the YAML to JSON (`pmm_dynamic_2_sweep.json`).
2. Batch-tests every payload in that JSON with 4 parallel workers.
3. Writes the summary results to `results/summaries/pmm_dynamic_2.csv` and detail packets to `results/detail_packets/pmm_dynamic_2/`.