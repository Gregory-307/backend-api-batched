#!/usr/bin/env python3
"""
A super-simple, hardcoded script to run a single backtest and see if it works.
"""
import json
import time
from datetime import datetime, timezone
import socket

import requests
from requests.auth import HTTPBasicAuth

# ----------------------------------------------------------------------
# 🔧 USER GLOBALS
# ----------------------------------------------------------------------
BASE_URL: str = "http://localhost:8000"
USERNAME, PASSWORD = "admin", "admin"


def wait_for_api(host="localhost", port=8000, timeout=30):
    """Wait for the API to be ready before sending requests."""
    print(f"⏳ Waiting for API at {host}:{port}...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                print("✅ API is ready.")
                return
        time.sleep(1)
    raise RuntimeError(f"API not ready after {timeout} seconds.")


def to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD (interpreted as midnight UTC) to unix timestamp."""
    year, month, day = map(int, date_str.split("-"))
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    return int(dt.timestamp())


def run_backtest(body: dict, auth: HTTPBasicAuth, retries: int = 0) -> dict:
    """POST /run-backtesting and return decoded JSON (or error)."""
    attempt = 0
    while True:
        try:
            print("▶️  Sending request to /run-backtesting...")
            r = requests.post(f"{BASE_URL}/run-backtesting", json=body, auth=auth, timeout=1200)
            print(f"◀️  Received response (status: {r.status_code})")

            try:
                data = r.json()
            except ValueError:
                data = {"error": "non-JSON response", "raw": r.text[:500]}

            is_error = (r.status_code != 200) or (isinstance(data, dict) and data.get("error"))

            if is_error:
                print("\n--- FAILED REQUEST ---")
                print("Request Body:")
                print(json.dumps(body, indent=2))
                print("\nResponse:")
                print(r.text)
                print("----------------------")
            
            if r.status_code != 200:
                data.setdefault("error", f"HTTP {r.status_code}")

            return data
        
        except requests.exceptions.RequestException as exc:
            if attempt >= retries:
                return {"error": f"Request failed after {retries+1} attempts: {exc}"}
            wait = 2 ** attempt
            print(f"  ⚠️  Network error, retrying in {wait}s... ({exc})")
            time.sleep(wait)
            attempt += 1


def run_single_test(test_name: str, config: dict, auth: HTTPBasicAuth):
    """Runs a single, hardcoded backtest and prints the result."""
    print(f"🚀  Starting test: {test_name}...")

    payload = {
        "start_time": to_timestamp("2024-03-11"),
        "end_time":   to_timestamp("2024-03-13"),
        "backtesting_resolution": "3m",
        "trade_cost": 0.001,
        "config": config,
    }

    result = run_backtest(payload, auth)

    print(f"\n--- TEST '{test_name}' COMPLETE ---")
    if result.get("error"):
        print("❌  FAILURE")
        print(f"Error: {result['error']}")
        if 'raw' in result:
             print(f"Raw Response: {result['raw']}")
    else:
        print("✅  SUCCESS")
        # Pretty print the main results, excluding the huge 'processed_data' if it exists
        # if 'results' in result and 'processed_data' in result['results']:
        #     del result['results']['processed_data']
        print(json.dumps(result.get("results"), indent=2))
    print("─" * 50)


def main():
    """Runs a series of simple, hardcoded backtests."""
    wait_for_api()  # Wait for the server to be up
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    # --- Test 1: PMM Dynamic (restoring all keys) ---
    pmm_dynamic_config = {
        "controller_name": "pmm_dynamic",
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20.0,
        "cooldown_time": 15,
        "executor_refresh_time": 3600,
        "stop_loss": 0.05,
        "take_profit": 0.02,
        "time_limit": 720.0,
        "trailing_stop": None,
        "position_mode": "HEDGE",
        "position_rebalance_threshold_pct": "0.05",
        "skip_rebalance": False,
        "id": None,
        "manual_kill_switch": False,
        "initial_positions": [],
        "buy_spreads": "0.01",
        "sell_spreads": "0.01",
        "buy_amounts_pct": "100",
        "sell_amounts_pct": "100",
        "candles_connector": "kucoin",
        "candles_trading_pair": "BTC-USDT",
        "interval": "3m",
        "macd_fast": 21,
        "macd_slow": 42,
        "macd_signal": 9,
        "natr_length": 14,
        "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}]
    }
    run_single_test("PMM Dynamic (Restored)", pmm_dynamic_config, auth)

    # --- Test 2: PMM Simple (with non-null amounts) ---
    # Key difference: Providing explicit amounts instead of None
    pmm_simple_config = {
        "controller_name": "pmm_simple",
        "controller_type": "market_making",
        "total_amount_quote": 100,
        "manual_kill_switch": False,
        "candles_config": [{"connector": "kucoin", "trading_pair": "WLD-USDT", "interval": "3m"}],
        "initial_positions": [],
        "connector_name": "kucoin",
        "trading_pair": "WLD-USDT",
        "buy_spreads": "0.005,0.01",
        "sell_spreads": "0.005,0.01",
        "buy_amounts_pct": "50,50",
        "sell_amounts_pct": "50,50",
        "executor_refresh_time": 300,
        "cooldown_time": 15,
        "leverage": 20,
        "position_mode": "HEDGE",
        "stop_loss": "0.03",
        "take_profit": "0.02",
        "time_limit": 2700,
        "take_profit_order_type": "OrderType.LIMIT",
        "trailing_stop": None,
        "position_rebalance_threshold_pct": "0.05",
        "skip_rebalance": False
    }
    # run_single_test("PMM Simple (with amounts)", pmm_simple_config, auth)

    # --- Test 3: DMAN v3 (Directional) ---
    dman_v3_config = {
        "controller_name": "dman_v3",
        "controller_type": "directional_trading",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20.0,
        "cooldown_time": 60,
        "stop_loss": 0.05,
        "take_profit": 0.02,
        "time_limit": 720.0,
        "trailing_stop": "0.015,0.005",
        "position_mode": "HEDGE",
        "id": None,
        "manual_kill_switch": False,
        "initial_positions": [],
        "max_executors_per_side": 4,
        "take_profit_order_type": "OrderType.LIMIT",
        "candles_connector": "kucoin",
        "candles_trading_pair": "BTC-USDT",
        "interval": "3m",
        "bb_length": 20,
        "bb_std": 1.5,
        "bb_long_threshold": 0.3,
        "bb_short_threshold": 0.3,
        "dca_spreads": "0.001,0.01,0.03,0.06",
        "dca_amounts_pct": "25,25,25,25",
        "dynamic_order_spread": False,
        "dynamic_target": False,
        "activation_bounds": None,
        "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}]
    }
    run_single_test("DMAN v3 (Directional - Patched)", dman_v3_config, auth)

    # --- Test 4: DMAN Maker v2 (Corrected Config) ---
    dman_maker_v2_config = {
        "controller_name": "dman_maker_v2",
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20,
        "position_rebalance_threshold_pct": "0.05",
        "dca_spreads": "0.01,0.02,0.04,0.08",
        "dca_amounts": "1,1,1,1",
        "buy_spreads": "0.01,0.02,0.04,0.08",
        "sell_spreads": "0.01,0.02,0.04,0.08",
        "buy_amounts_pct": "25,25,25,25",
        "sell_amounts_pct": "25,25,25,25",
        "cooldown_time": 15,
        "executor_refresh_time": 3600,
        "stop_loss": 0.03,
        "take_profit": 0.02,
        "time_limit": 2700,
        "position_mode": "HEDGE",
        "take_profit_order_type": "OrderType.LIMIT",
        "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}],
        "manual_kill_switch": False,
        "initial_positions": [],
        "trailing_stop": None,
        "executor_activation_bounds": None,
        "top_executor_refresh_time": None
    }
    run_single_test("DMAN Maker v2 (Corrected)", dman_maker_v2_config, auth)

    # --- Test 5: PMM Dynamic 2 (New Custom Controller) ---
    pmm_dynamic_2_config = {
        "controller_name": "pmm_dynamic_2",
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20,
        "buy_spreads": "0.01",
        "sell_spreads": "0.01",
        "buy_amounts_pct": "100",
        "sell_amounts_pct": "100",
        "cooldown_time": 15,
        "executor_refresh_time": 3600,
        "stop_loss": 0.05,
        "take_profit": 0.02,
        "time_limit": 720.0,
        "position_mode": "HEDGE",
        "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}],
    }
    run_single_test("PMM Dynamic 2", pmm_dynamic_2_config, auth)


if __name__ == "__main__":
    main()
