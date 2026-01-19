@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: Hummingbot Batch Backtest Runner
:: =============================================================================
:: This script starts the backend, runs backtests, and shows results.
::
:: FIRST RUN: Downloads and installs everything automatically:
::   - Miniconda base image (~400MB)
::   - Hummingbot trading framework
::   - All Python dependencies
::   This takes 5-10 minutes. Subsequent runs are fast (cached).
::
:: PREREQUISITE: Docker Desktop must be installed
::   Download: https://www.docker.com/products/docker-desktop/
::
:: Usage:
::   run_backtest.bat              Run demo backtest
::   run_backtest.bat my_sweep.yml Run custom sweep file
::   run_backtest.bat --stop       Stop the backend containers
:: =============================================================================

set SWEEP_FILE=%1

:: Handle --stop command
if "%SWEEP_FILE%"=="--stop" (
    echo Stopping containers...
    docker compose down
    exit /b 0
)

:: Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

:: Start backend in detached mode (if not already running)
echo.
echo [1/4] Starting backend services...
echo      (First run downloads Hummingbot + dependencies - may take 5-10 min)
echo.
docker compose up -d --build

:: Wait for API to be ready
echo.
echo [2/4] Waiting for API to be ready...
set RETRIES=120
set API_URL=http://localhost:8000/docs

:wait_loop
curl -s -o nul -w "" %API_URL% >nul 2>&1
if not errorlevel 1 (
    echo API is ready!
    goto :api_ready
)
set /a RETRIES-=1
if %RETRIES% leq 0 (
    echo ERROR: API did not start within 2 minutes.
    echo Check logs with: docker compose logs backend-api
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_loop

:api_ready

:: Install Python dependencies if needed
echo.
echo [3/4] Checking Python dependencies...
pip show requests >nul 2>&1 || pip install requests pyyaml rich pandas

:: Run the backtest
echo.
echo [4/4] Running backtests...
echo.

if "%SWEEP_FILE%"=="" (
    :: No argument - run demo
    echo Running demo backtest...
    python batch_tester.py --demo --fetch-candles --outfile demo_results.csv
) else (
    :: Custom sweep file provided
    if not exist "%SWEEP_FILE%" (
        echo ERROR: Sweep file not found: %SWEEP_FILE%
        pause
        exit /b 1
    )

    echo Generating test configs from %SWEEP_FILE%...
    python grid_builder.py "%SWEEP_FILE%" > _temp_tests.json

    echo Running backtests...
    python batch_tester.py --file _temp_tests.json --fetch-candles --workers 4

    del _temp_tests.json 2>nul
)

echo.
echo ============================================================================
echo DONE! Results saved to batch_results.csv (or demo_results.csv for demo)
echo.
echo Commands:
echo   - View logs:     docker compose logs -f backend-api
echo   - Stop backend:  run_backtest.bat --stop
echo   - Dashboard:     streamlit run dashboard/app.py
echo ============================================================================
echo.

pause
