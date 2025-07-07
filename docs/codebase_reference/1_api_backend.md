# Codebase Reference: API Backend

This document provides a summary of the core Python files that make up the FastAPI backend application.

---

## 1. `main.py`

*   **Purpose**: The main entry point for the FastAPI application.
*   **Key Components**:
    *   Creates the `FastAPI` app instance.
    *   Imports and includes the routers from the `routers/` directory (`manage_backtesting`, `manage_files`, `manage_market_data`).
    *   Sets up CORS (Cross-Origin Resource Sharing) middleware to allow the frontend dashboard to communicate with the API.
    *   Defines a root endpoint (`/`) for a basic health check.
*   **Execution**: This file is the target for `uvicorn` when running the server (e.g., `uvicorn main:app --reload`).

---

## 2. `config.py`

*   **Purpose**: Manages application settings and configuration loading.
*   **Key Components**:
    *   Uses Pydantic's `BaseSettings` to load environment variables from a `.env` file.
    *   Defines settings like `HUMMINGBOT_BROKER_HOST`, `HUMMINGBOT_BROKER_PORT`, `BACKEND_API_PORT`, etc.
*   **Usage**: The settings object is instantiated and used throughout the application wherever configuration values are needed, providing a single source of truth.

---

## 3. `models.py`

*   **Purpose**: Defines the Pydantic data models used for API request and response validation.
*   **Key Components**:
    *   `BacktestingConfig`: Defines the structure of the JSON body for the `/run-backtesting` endpoint. This ensures that incoming backtesting requests have the correct data types and fields.
    *   Other models for file management, market data requests, etc.
*   **Usage**: These models are used as type hints in the FastAPI endpoint function signatures, which automatically handles data validation, parsing, and documentation generation.

---

## 4. `routers/manage_backtesting.py`

*   **Purpose**: Contains the primary logic for initiating and managing Hummingbot backtests.
*   **Key Components**:
    *   Defines the `/run-backtesting` POST endpoint.
    *   Receives a `BacktestingConfig` object.
    *   Constructs a `BacktestingEngine` instance.
    *   Calls the `run()` method on the engine to execute the backtest.
    *   Handles results summarization and error catching, returning the final metrics as a JSON response.
    *   Contains the crucial "monkey-patching" logic to fix upstream bugs in the Hummingbot library at runtime.
*   **Interaction**: This is the most critical endpoint for the application's core functionality.

---

## 5. `routers/manage_files.py`

*   **Purpose**: Provides API endpoints for file and configuration management related to bot strategies.
*   **Key Components**:
    *   Endpoints to list, get, and save controller configuration files.
    *   `/controller-config-pydantic/{controller_type}/{controller_name}`: An important endpoint that dynamically returns the Pydantic model for a given controller, allowing frontends to generate configuration forms automatically.
*   **Usage**: Used by the UI and helper scripts to inspect and manage strategy parameters without needing to manually edit files on the server.

---

## 6. `routers/manage_market_data.py`

*   **Purpose**: Handles requests related to fetching and managing market data for backtesting.
*   **Key Components**:
    *   Endpoints for downloading and checking the status of candle data from various exchanges.
    *   `/candles/status`: Checks if the required candle data for a specific exchange, trading pair, and interval is available locally.
    *   `/candles/download`: Initiates a background task to download historical candle data.
*   **Usage**: Ensures that the backtesting engine has the necessary historical data before running a strategy, preventing errors from missing data.

## 7. `routers/manage_performance.py`
*   **Purpose**: Provides an API endpoint for on-demand performance analysis.
*   **Key Features**:
    *   Defines the `/get-performance-results` POST endpoint.
    *   It accepts a list of trade `executors` in the request body.
    *   It uses the `BacktestingEngineBase` to re-calculate and summarize performance metrics for those specific trades.
*   **Usage**: Allows the frontend or other services to get standardized performance reports for arbitrary sets of trades without running a full backtest.

## 8. `routers/manage_accounts.py`
*   **Purpose**: Provides a comprehensive set of API endpoints for managing user accounts and their exchange credentials.
*   **Key Features**:
    *   Endpoints to list, add, and delete accounts.
    *   Functions to add, delete, and list encrypted connector credentials for each account.
    *   Retrieves the real-time and historical state of account balances.
    *   Exposes available connectors and their specific configuration fields.
*   **Usage**: This is the primary interface for the frontend to manage all user credentials and monitor account portfolios.

## 9. `routers/manage_broker_messages.py`
*   **Purpose**: Exposes API endpoints to interact with live, running Hummingbot instances via the MQTT message broker.
*   **Key Features**:
    *   Wraps the `BotsManager` service to provide control over live bots.
    *   Endpoints to get the status of all active bots, start/stop a specific bot, and import a strategy.
*   **Usage**: Allows a UI or external service to control and monitor live trading bots without direct terminal access.

## 10. `routers/manage_databases.py`
*   **Purpose**: Provides API endpoints for managing and inspecting Hummingbot's SQLite database files.
*   **Key Features**:
    *   Lists available database files.
    *   Reads multiple databases and returns their contents (orders, trades, etc.) as JSON.
    *   Creates a "checkpoint" by aggregating data from multiple healthy databases into a single new SQLite file.
    *   Loads data from a previously created checkpoint.
*   **Usage**: Used by the data analysis and dashboard components to load and process historical trading data.

## 11. `routers/manage_docker.py`
*   **Purpose**: Provides API endpoints to interact with the Docker daemon for managing Hummingbot instances.
*   **Key Features**:
    *   Endpoints to check if Docker is running, list available images, and see active/exited containers.
    *   Functions to start, stop, and remove containers.
    *   A key endpoint to `create-hummingbot-instance`, which sets up the necessary directories, configurations, and volumes to launch a new bot as a Docker container.
*   **Usage**: The core of the automated bot deployment and management system.

---

## Core Services

### 1. `services/bots_orchestrator.py`
*   **Purpose**: The central service for discovering, monitoring, and interacting with live, containerized Hummingbot instances.
*   **Key Components**:
    *   `BotsManager`: The main class that connects to Docker to find running Hummingbot containers.
    *   It uses the `hbotrc` library to establish a connection to each bot's MQTT broker.
    *   `HummingbotPerformanceListener`: A listener that subscribes to performance and log topics for each bot, collecting data in real-time.
    *   Provides methods to start, stop, and configure bots remotely.
*   **Usage**: This service is the backbone of the live trading management system, enabling centralized control and monitoring of a fleet of trading bots.

### 2. `services/bot_archiver.py`
*   **Purpose**: A utility service for archiving the data directories of bot instances.
*   **Key Components**:
    *   `BotArchiver`: A class with methods to compress a bot's instance directory into a `.tar.gz` file.
    *   It supports archiving to a local `bots/archived` directory.
    *   It can optionally upload the archive to an AWS S3 bucket for long-term storage and then clean up the local files.
*   **Usage**: Used for data management, allowing users to save the complete state of a bot run before deleting the instance.

### 3. `services/accounts_service.py`
*   **Purpose**: A high-level service responsible for managing all user accounts, their connector configurations, and their balance information.
*   **Key Features**:
    *   Runs a background loop to periodically update and store the balance and state of all connected accounts.
    *   Initializes and manages `ConnectorBase` instances for each set of credentials.
    *   Provides a centralized point for fetching account data, abstracting the complexity from the API routers.
*   **Usage**: Acts as the engine behind the `manage_accounts.py` router, handling the core logic of account management.

### 4. `services/docker_service.py`
*   **Purpose**: A service that provides a clean, high-level interface for interacting with the Docker daemon.
*   **Key Features**:
    *   `DockerManager`: The main class that wraps the `docker-py` library.
    *   Provides methods to list, create, start, stop, and remove containers.
    *   Contains the detailed logic for creating a new Hummingbot instance, including setting up directories, copying credentials, and configuring volumes.
*   **Usage**: Abstracting direct Docker calls, it's used by the `manage_docker.py` router to execute container-related tasks.

---

## Core Utilities

### 1. `utils/event_logger.py`
*   **Purpose**: A lightweight, in-memory event logger designed to capture a sequence of events during a single backtest run.
*   **Key Components**:
    *   `BTEventLogger`: A class that stores event dictionaries in a list. It is designed to be thread-local to avoid mixing logs from concurrent backtests.
    *   `add()`: Adds a new event (row) to the log.
    *   `dump()`: Writes all captured events to both a CSV and a JSON file.
*   **Usage**: Provides a simple way to log and persist detailed event data from a backtest for later analysis.

### 2. `utils/candles_cache.py`
*   **Purpose**: A critical performance enhancement that monkey-patches the Hummingbot library to add a disk-based cache for candlestick data.
*   **Key Features**:
    *   It intercepts calls to fetch candle data (`get_candles_df`).
    *   It stores the results in Parquet files in the `data/candles_cache` directory.
    *   Subsequent requests for the same data are served from the local cache, which dramatically reduces API calls, avoids rate-limiting, and speeds up backtesting sweeps.
    *   The patching is idempotent (safe to import multiple times).
*   **Usage**: Imported at application startup to transparently enable caching for all backtesting operations.

### 3. `utils/check_candles.py`
*   **Purpose**: A simple, standalone diagnostic script to test and debug the `BacktestingDataProvider`.
*   **Key Features**:
    *   It initializes a `BacktestingDataProvider`.
    *   It then attempts to fetch candle data for a hard-coded exchange and trading pair with various `max_records` values.
    *   It prints the result of each fetch attempt, making it easy to see if the data provider is working correctly and if the candle cache is being hit.
*   **Usage**: A helpful tool for developers to quickly diagnose issues with candle data fetching without running a full backtest.

### 4. `utils/etl_databases.py`
*   **Purpose**: A utility that provides tools for Extract, Transform, and Load (ETL) operations on Hummingbot SQLite databases.
*   **Key Components**:
    *   `HummingbotDatabase`: A class to connect to a single Hummingbot database file and read its tables (`Orders`, `TradeFill`, etc.) into pandas DataFrames.
    *   `ETLPerformance`: A class that can create a new "checkpoint" database and insert data from multiple source databases into it.
*   **Usage**: This is the core logic behind the `manage_databases.py` router, enabling the aggregation of data from multiple bot runs.

### 5. `utils/file_system.py`
*   **Purpose**: A comprehensive utility class that centralizes all file and directory operations.
*   **Key Features**:
    *   Provides methods for common tasks like listing, creating, copying, and deleting files and folders.
    *   Includes helpers for reading and writing YAML files.
    *   Contains crucial logic for dynamically discovering and loading `*Config` classes from controller and script files, which is essential for the system's modularity.
*   **Usage**: Used throughout the application wherever file system interaction or dynamic module loading is required.

### 6. `utils/models.py`
*   **Purpose**: Defines a custom Pydantic model adapter for handling encrypted configuration settings.
*   **Key Components**:
    *   `BackendAPIConfigAdapter`: A subclass of `ClientConfigAdapter` from the Hummingbot library.
    *   It overrides the default methods for encrypting and decrypting secret fields (like API keys) to integrate with the project's custom `BackendAPISecurity` secrets manager.
*   **Usage**: Ensures that all strategy and connector configurations handle sensitive data securely and consistently.

### 7. `utils/security.py`
*   **Purpose**: A core utility that manages the encryption and decryption of all sensitive configuration data, such as API keys and secrets.
*   **Key Components**:
    *   `BackendAPISecurity`: A subclass of Hummingbot's `Security` class.
    *   It manages the user's password and uses it to encrypt/decrypt connector configuration files stored on disk.
    *   It provides methods to log in, validate the password, and load all decrypted configurations into memory for use by the application.
*   **Usage**: This is the central component for ensuring the security of all user credentials. 