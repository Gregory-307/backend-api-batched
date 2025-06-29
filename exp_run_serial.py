#!/usr/bin/env python3
"""
Simplified Experiment Runner for Hummingbot (SERIAL VERSION)
============================================================

This script is a lighter version of *experiment_runner.py* that focuses only on
`pmm_simple` and `pmm_dynamic` strategies.  Before any network calls it performs
an exhaustive validation of every generated configuration against the blueprint
stored in ``bots/hummingbot_files/schema/all_controller_configs.json``.
The run is **aborted** if *any* mismatch is detected so that no back-tests are
executed with invalid payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import json as _json

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

# ----------------------------------------------------------------------
# 🔧 USER GLOBALS
# ----------------------------------------------------------------------
MARKET_CONNECTOR: str = "kucoin"
PAIR: str = "BTC-USDT"
BASE_URL: str = "http://localhost:8000"
RESULTS_CSV_PATH: str = "bots/hummingbot_files/results/backtest_results.csv"
USERNAME, PASSWORD = "admin", "admin"

# Location of the blueprint file (produced by fetch_all_controller_configs.py)
SCHEMA_PATH: str = "bots/hummingbot_files/schema/all_controller_configs.json"

# ----------------------------------------------------------------------
# ⏰  TIMEFRAMES (edit as desired)
# ----------------------------------------------------------------------
TIMEFRAMES: Dict[str, Tuple[str, str, str, float]] = {
    "intraday": ("2024-07-01", "2024-07-02", "1m", 0.001),
    "swing":    ("2024-07-01", "2024-07-02", "5m", 0.001),
}

# ----------------------------------------------------------------------
# 📐  COMMON GRID  (shared across strategies)
# ----------------------------------------------------------------------
COMMON_GRID: Dict[str, List] = {
    # Risk Management
    "stop_loss":   [0.05],
    "take_profit": [0.02],
    "time_limit":  [720],

    # Trailing Stop
    "trailing_stop_activation_price_delta": [0.018],
    "trailing_stop_trailing_delta": [0.002],

    # Spread for level-1
    "level_spread": [0.01],

    # General
    "leverage": [20],
}

# ----------------------------------------------------------------------
# 🎛️  STRATEGY-SPECIFIC GRIDS
# ----------------------------------------------------------------------
STRAT_GRIDS: Dict[str, Dict[str, List]] = {
    "pmm_simple": {},  # uses only the common grid

    "pmm_dynamic": {
        "n_levels": [1, 2, 3],
        "candles_interval": ["3m"],
        "macd_fast": [21],
        "macd_slow": [42],
        "macd_signal": [9],
        "natr_length": [14],
    },

    # dman_maker_v2 requires a grid for DCA spreads
    "dman_maker_v2": {
        "dca_spreads": ["0.01,0.02,0.04,0.08"],
        "dca_amounts": ["0.1,0.2,0.4,0.8"],
    },

    # RoniMethod (variant of dynamic)
    "ronimethod": {
        "n_levels": [1, 2, 3],
        "candles_interval": ["3m"],
        "macd_fast": [12, 21],
        "macd_slow": [26, 50],
        "macd_signal": [9],
        "natr_length": [14],
        "price_adjustment_factor": [5e-05],
        "spread_multiplier_factor": [0.05],
    },
}


# ----------------------------------------------------------------------
# 🏗️  CONFIG BUILDERS
# ----------------------------------------------------------------------

def build_common_config(controller_name: str, common: Dict) -> Dict:
    spread_lvl1 = common["level_spread"]
    n_levels = common.get("n_levels", 1)  # Default to 1 level if not specified

    # Build n-level symmetric spreads based on the first level's spread
    spreads = [round(spread_lvl1 * (i + 1), 4) for i in range(n_levels)]
    spreads_str = ",".join(map(str, spreads))

    # Distribute 100% across n-levels, ensuring the total is exactly 100
    if n_levels > 0:
        amounts = [round(100 / n_levels, 2) for _ in range(n_levels)]
        remainder = round(100 - sum(amounts), 2)
        if remainder != 0:
            amounts[-1] += remainder
        # Clean up floating point representation for display
        amounts_pct = [f"{pct:.2f}".rstrip('0').rstrip('.') for pct in amounts]
    else:
        amounts_pct = []
    
    equal_pct = ','.join(amounts_pct)

    cfg = {
        "controller_name": controller_name,
        "controller_type": "market_making",
        "connector_name": MARKET_CONNECTOR,
        "trading_pair": PAIR,
        "total_amount_quote": 1000,
        "leverage": common["leverage"],

        # Execution timings
        "cooldown_time": 15,
        "executor_refresh_time": 300,

        # Risk management (flat fields + optional trailing)
        "stop_loss":   str(common["stop_loss"]),
        "take_profit": str(common["take_profit"]),
        "take_profit_order_type": "OrderType.LIMIT",
        "time_limit": common["time_limit"],
        "trailing_stop": None,  # disable by default, use None for null

        # Positioning & rebalancing
        "position_mode": "HEDGE",
        "position_rebalance_threshold_pct": "0.05",
        "skip_rebalance": False,

        # Misc flags / identifiers
        "id": None,
        "manual_kill_switch": False,
        "initial_positions": [],
        "candles_config": [],

        # Spread & size definition
        "buy_spreads":  spreads_str,
        "sell_spreads": spreads_str,
        "buy_amounts_pct":  equal_pct,
        "sell_amounts_pct": equal_pct,
    }

    # ------------------------------------------------------------------
    # Ensure at least one candles_config entry so backend can load data
    # ------------------------------------------------------------------
    if not cfg["candles_config"]:
        cfg["candles_config"] = [{
            "connector": MARKET_CONNECTOR,
            "trading_pair": PAIR,
            "interval": "1m",
        }]

    return cfg


def build_pmm_simple(common: Dict, extra: Dict) -> Dict:
    # pmm_simple expects exactly 2 levels and null amounts, overriding n_levels
    common['n_levels'] = 2
    cfg = build_common_config("pmm_simple", common)
    # The backend fails with null amounts, so we let the common builder set them.
    return cfg


def build_pmm_dynamic(common: Dict, extra: Dict) -> Dict:
    cfg = build_common_config("pmm_dynamic", common)

    # strategy-specific augmentations
    cfg.update({
        "candles_connector": MARKET_CONNECTOR,
        "candles_trading_pair": PAIR,
        "interval": extra["candles_interval"],
        "macd_fast": extra["macd_fast"],
        "macd_slow": extra["macd_slow"],
        "macd_signal": extra["macd_signal"],
        "natr_length": extra["natr_length"],
        "candles_config": [{
            "connector": MARKET_CONNECTOR,
            "trading_pair": PAIR,
            "interval": extra["candles_interval"],
        }],
    })
    return cfg


def build_dman_maker_v2(common: Dict, extra: Dict) -> Dict:
    cfg = build_common_config("dman_maker_v2", common)
    # overrides / additions
    cfg.update({
        "dca_spreads": extra["dca_spreads"],
        "dca_amounts": extra.get("dca_amounts", "0.1,0.2,0.4,0.8"),
        # leave buy/sell_spreads as set in common_cfg (0.01,0.02)
    })
    # The backend fails with null amounts, so we let the common builder set them.
    return cfg


def build_roni_method(common: Dict, extra: Dict) -> Dict:
    # Base on dynamic copy / RoniMethod blueprint
    cfg = build_common_config("RoniMethod", common)
    # RoniMethod blueprint doesn't include MACD/NATR fields; we only keep price & spread factors if present
    cfg.update({
        "price_adjustment_factor": str(extra["price_adjustment_factor"]),
        "spread_multiplier_factor": str(extra["spread_multiplier_factor"]),
    })
    # The backend fails with null amounts, so we let the common builder set them.
    return cfg


BUILDER_MAP = {
    "pmm_simple": build_pmm_simple,
    "pmm_dynamic": build_pmm_dynamic,
    "dman_maker_v2": build_dman_maker_v2,
    "ronimethod": build_roni_method,
}



# ----------------------------------------------------------------------
# 🛠️  UTILITY HELPERS
# ----------------------------------------------------------------------

def combo_dict(grid: Dict[str, List]) -> List[Dict]:
    """Cartesian-product expansion of a parameter grid."""
    if not grid:
        return [{}]
    keys, values = zip(*grid.items())
    return [dict(zip(keys, v)) for v in itertools.product(*values)]


def short_hash(obj: Dict) -> str:
    """10-char deterministic hash for a dict (order-independent)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.md5(blob).hexdigest()[:10]


def to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD (interpreted as midnight UTC) to unix timestamp."""
    year, month, day = map(int, date_str.split("-"))
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    return int(dt.timestamp())


def run_backtest(body: Dict, auth: HTTPBasicAuth, retries: int = 2) -> Dict:
    """POST /run-backtesting with retries and return decoded JSON (or error)."""
    attempt = 0
    debug_mode = 'DEBUG_MODE' in globals() and DEBUG_MODE
    while True:
        try:
            r = requests.post(f"{BASE_URL}/run-backtesting", json=body, auth=auth, timeout=1200)

            try:
                data = r.json()
            except ValueError:
                data = {"error": "non-JSON response", "raw": r.text[:300]}

            is_error = (r.status_code != 200) or (isinstance(data, dict) and data.get("error"))

            if debug_mode and is_error:
                print("--- FAILED REQUEST BODY ---")
                print(json.dumps(body, indent=2)[:1000])
                print(f"--- RESPONSE {r.status_code} ---")
                print(r.text[:1000])
                print("--------------------------------")

            if is_error:
                data.setdefault("raw", r.text)
                if r.status_code != 200:
                    data.setdefault("error", f"HTTP {r.status_code}")
            return data
        except Exception as exc:
            if attempt >= retries:
                return {"error": f"request failed after {retries+1} attempts: {exc}"}
            wait = 2 ** attempt
            print(f"  ⚠️  network error, retrying in {wait}s … ({exc})")
            time.sleep(wait)
            attempt += 1

# ----------------------------------------------------------------------
# 🔎  BLUEPRINT VALIDATION
# ----------------------------------------------------------------------

def _normalize_blueprints(raw: dict) -> dict:
    """Lower-case blueprint dict keys for easier lookup."""
    norm: dict = {}
    for ctype, controllers in raw.items():
        norm_ctype = ctype.lower()
        norm[norm_ctype] = {name.lower(): cfg for name, cfg in controllers.items()}
    return norm


try:
    _raw_blueprints = json.loads(Path(SCHEMA_PATH).read_text())
    BLUEPRINTS: dict = _normalize_blueprints(_raw_blueprints)
except FileNotFoundError:
    sys.exit(f"❌  Cannot find blueprint file {SCHEMA_PATH}. Run fetch_all_controller_configs.py first.")
except json.JSONDecodeError as e:
    sys.exit(f"❌  {SCHEMA_PATH} is not valid JSON: {e}")


def validate_against_blueprint(cfg: dict, blueprints: dict) -> List[str]:
    """
    Return list of error strings; empty list means cfg matches.
    Checks for missing keys, extra keys, and type mismatches.
    """
    ctype = cfg.get("controller_type", "").lower()
    cname = cfg.get("controller_name", "").lower()
    errs: List[str] = []

    template = blueprints.get(ctype, {}).get(cname)
    if template is None:
        return [f"Unknown controller {ctype}/{cname} in blueprint"]

    expected_keys = set(template.keys())
    actual_keys = set(cfg.keys())

    # 1. Find missing keys
    if missing := sorted(list(expected_keys - actual_keys)):
        errs.append(f"missing keys → {missing}")

    # 2. Find extra keys (more complex, depends on strategy)
    # The base blueprints are sometimes extended with additional parameters.
    # We will check for extra keys that are not part of the base or known extensions.
    
    # NOTE: This is a hardcoded assumptions of which keys are allowed to be added
    #       to the base blueprint.
    allowed_extra_keys = set()
    if cname == "pmm_dynamic":
        allowed_extra_keys.update([
            "candles_connector", "candles_trading_pair", "interval",
            "macd_fast", "macd_slow", "macd_signal", "natr_length",
        ])
    elif cname == "ronimethod":
        allowed_extra_keys.update([
            "price_adjustment_factor", "spread_multiplier_factor"
        ])
    
    unexpected_keys = actual_keys - expected_keys - allowed_extra_keys
    if unexpected_keys:
        errs.append(f"unexpected keys → {sorted(list(unexpected_keys))}")

    # 3. Check for type mismatches on common keys
    for key in expected_keys.intersection(actual_keys):
        # Strict check for None/null values
        if template[key] is None:
            if cfg[key] is not None:
                errs.append(f"type mismatch for '{key}': expected null, got {type(cfg[key]).__name__} ({cfg[key]})")
            continue

        if cfg[key] is None:
            errs.append(f"type mismatch for '{key}': expected {type(template[key]).__name__}, got null")
            continue

        expected_type = type(template[key])
        actual_type = type(cfg[key])

        # Be flexible with int/float comparisons
        if isinstance(cfg[key], (int, float)) and isinstance(template[key], (int, float)):
            continue

        if expected_type != actual_type:
            errs.append(f"type mismatch for '{key}': expected {expected_type.__name__}, got {actual_type.__name__}")

    return errs

# ----------------------------------------------------------------------
# 🧩  FILL DEFAULTS FROM BLUEPRINT
# ----------------------------------------------------------------------

def fill_defaults(cfg: dict) -> dict:
    """Populate any missing keys from the blueprint template (non-destructive)."""
    ctype = cfg.get("controller_type", "").lower()
    cname = cfg.get("controller_name", "").lower()
    template = BLUEPRINTS.get(ctype, {}).get(cname)
    if template:
        for k, v in template.items():
            cfg.setdefault(k, v)
    return cfg

# ----------------------------------------------------------------------
# 🧪  EXPERIMENT GENERATION
# ----------------------------------------------------------------------

def generate_experiments(fast: bool = False) -> List[Tuple[str, Dict, Dict, str]]:
    experiments: List[Tuple[str, Dict, Dict, str]] = []

    def shrink(grid: Dict[str, List]) -> Dict[str, List]:
        return {k: [v[0]] for k, v in grid.items()} if fast else grid

    common_variants = combo_dict(shrink(COMMON_GRID))
    # In fast mode run only the highest-resolution (1m) timeframe to minimise data volume.
    tf_items = (
        [(k, v) for k, v in TIMEFRAMES.items() if v[2] == "1m"]
        if fast else list(TIMEFRAMES.items())
    )

    for strat_key, extra_grid in STRAT_GRIDS.items():
        builder = BUILDER_MAP[strat_key]
        extra_variants = combo_dict(shrink(extra_grid)) if extra_grid else [{}]

        for common_params in common_variants:
            for extra_params in extra_variants:
                cfg = builder(common_params, extra_params)

                # fill defaults from blueprint to avoid missing-key errors
                cfg = fill_defaults(cfg)

                tag_common = "_".join(f"{k}{v}" for k, v in common_params.items())
                tag_extra = "_".join(f"{k}{v}" for k, v in extra_params.items())

                for tf_label, (start_str, end_str, resolution, fee) in tf_items:
                    tag_parts = [tf_label, strat_key, tag_common, tag_extra]
                    tag = "__".join(filter(None, tag_parts))

                    meta = {
                        "start_time": start_str,
                        "end_time": end_str,
                        "resolution": resolution,
                        "trade_cost": fee,
                    }
                    cfg_hash = short_hash(cfg | meta)
                    experiments.append((tag, cfg, meta, cfg_hash))

    return experiments

# ----------------------------------------------------------------------
# 🚀  EXECUTION & PERSISTENCE
# ----------------------------------------------------------------------

def _worker(payload_tuple: Tuple[str, Dict, Dict, str], auth: HTTPBasicAuth, retries: int) -> Dict:
    """Prepare and execute a single backtest, returning a results dictionary."""
    tag, cfg, meta, cfg_hash = payload_tuple

    if 'FETCH_CANDLES' in globals() and FETCH_CANDLES:
        # ensure candles for every interval specified in the config
        intervals = {c.get("interval", meta["resolution"]) for c in cfg.get("candles_config", [])}
        for ivl in intervals:
            ensure_candles(cfg["connector_name"], cfg["trading_pair"], ivl,
                           to_timestamp(meta["start_time"]), to_timestamp(meta["end_time"]), auth)

        # robust wait: poll until candles exist (max 60s)
        deadline = time.time() + 60
        while True:
            all_ready = True
            for ivl in intervals:
                try:
                    r = requests.get(
                        f"{BASE_URL}/candles-count",
                        params={
                            "connector": cfg["connector_name"],
                            "trading_pair": cfg["trading_pair"],
                            "interval": ivl,
                            "start_time": to_timestamp(meta["start_time"]),
                            "end_time": to_timestamp(meta["end_time"]),
                        },
                        auth=auth,
                        timeout=10,
                    )
                    if r.status_code != 200 or r.json().get("count", 0) == 0:
                        all_ready = False
                        break
                except Exception:
                    all_ready = False
                    break

            if all_ready:
                break

            if time.time() > deadline:
                return {
                    "experiment": tag,
                    "config_hash": cfg_hash,
                    "error": "timeout waiting for candles",
                }
            time.sleep(2)

    payload = {
        "start_time": to_timestamp(meta["start_time"]),
        "end_time":   to_timestamp(meta["end_time"]),
        "backtesting_resolution": meta["resolution"],
        "trade_cost": meta["trade_cost"],
        "config": cfg,
    }
    t0 = time.perf_counter()
    res = run_backtest(payload, auth, retries=retries)
    runtime = round(time.perf_counter() - t0, 2)

    if isinstance(res, dict) and "results" in res and isinstance(res["results"], dict):
        res.update(res.pop("results"))

    return {
        "experiment": tag,
        "config_hash": cfg_hash,
        "runtime_sec": runtime,
        "timestamp_run": datetime.utcnow().isoformat(timespec="seconds"),
        **meta,
        **res,
    }


def execute_experiments(
    experiments: List[Tuple[str, Dict, Dict, str]],
    retries: int = 2,
) -> None:
    os.makedirs(os.path.dirname(RESULTS_CSV_PATH), exist_ok=True)

    existing_df = pd.DataFrame()
    existing_hashes: set[str] = set()
    if os.path.exists(RESULTS_CSV_PATH):
        try:
            existing_df = pd.read_csv(RESULTS_CSV_PATH, low_memory=False)
            if "config_hash" in existing_df.columns:
                existing_hashes = set(existing_df["config_hash"].dropna().astype(str))
        except Exception:
            print("⚠️  Could not read existing results – starting fresh.")

    to_run = [e for e in experiments if e[3] not in existing_hashes]
    print(f"Will run {len(to_run)} new experiments (skipping {len(experiments) - len(to_run)} duplicates)")

    auth = HTTPBasicAuth(USERNAME, PASSWORD)
    progress_iter = tqdm(to_run, desc="Running") if tqdm else to_run
    success_rows, errors = [], []

    for payload_tuple in progress_iter:
        row = _worker(payload_tuple, auth, retries)
        if row.get("error"):
            errors.append(row)
            err_msg = str(row["error"])
            raw_snippet = row.get("raw", "")
            if raw_snippet:
                raw_snippet = raw_snippet.replace("\n", " ")[:300] + (" …" if len(raw_snippet) > 300 else "")
            if len(err_msg) > 160:
                err_msg = err_msg[:160] + " …"
            print(f"⚠️  {row['experiment']} → {err_msg}")
            if raw_snippet:
                print(f"   ↳ raw: {raw_snippet}")
        else:
            success_rows.append(row)

    if not success_rows:
        print("No new experiments executed. All caught up!")
        return

    new_df = pd.json_normalize(success_rows)
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined.to_csv(RESULTS_CSV_PATH, index=False)
    print(f"\n✅  Saved {len(new_df)} successful rows → {RESULTS_CSV_PATH} (total {len(combined)})")

    if errors:
        print("\n────────── ERROR SUMMARY ──────────")
        for row in errors:
            raw_snippet = row.get("raw", "")
            raw_snippet = raw_snippet.replace("\n", " ")[:300] + (" …" if len(raw_snippet) > 300 else "")
            print(f"• {row['experiment']}  → {row['error']}")
            if raw_snippet:
                print(f"   ↳ raw: {raw_snippet}")
        print("See details in CSV; fix inputs or backend accordingly.")

# ------------------------------------------------------------------
# 📥  Candle pre-fetch helper (defined early so _worker can use it)
# ------------------------------------------------------------------


def ensure_candles(connector: str, pair: str, interval: str, start: int, end: int, auth: HTTPBasicAuth):
    """Fire-and-forget POST /historical-candles to make sure data exists."""
    try:
        url = f"{BASE_URL}/historical-candles"
        body = {
            "connector": connector,
            "trading_pair": pair,
            "interval": interval,
            "start_time": start,
            "end_time": end,
        }
        requests.post(url, json=body, auth=auth, timeout=60)
    except Exception:
        pass  # non-fatal; backend will error if data still missing 



# ----------------------------------------------------------------------
# 🏁  CLI ENTRYPOINT
# ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate & run back-test experiments sequentially.")
    parser.add_argument("--fast", action="store_true", help="Run a minimal subset for quick tests.")
    parser.add_argument("--retries", type=int, default=2, help="Retry count on network/HTTP errors.")
    parser.add_argument("--skip-blueprint-check", action="store_true", help="Bypass blueprint validation (not recommended).")
    parser.add_argument("--debug", action="store_true", help="Print request and response payloads for troubleshooting.")
    parser.add_argument("--only", type=str, help="Run only experiments whose tag contains this substring.")
    parser.add_argument("--fetch-candles", action="store_true", help="Pre-download candles before each run.")
    parser.add_argument("--config-file", type=str, help="Path to JSON file containing a single controller config to back-test (bypasses generation).")
    parser.add_argument("--start-date", type=str, help="Start date YYYY-MM-DD (used with --config-file)")
    parser.add_argument("--end-date", type=str, help="End date YYYY-MM-DD (used with --config-file)")
    parser.add_argument("--resolution", type=str, default="1m", help="Backtesting resolution for --config-file mode")
    parser.add_argument("--fee", type=float, default=0.001, help="Trade cost fee for --config-file mode")
    args = parser.parse_args()

    global DEBUG_MODE, FETCH_CANDLES
    DEBUG_MODE = args.debug
    FETCH_CANDLES = args.fetch_candles

    # ------------------------------------------------------------------
    # 🛠️  1️⃣  Manual single-config mode (if --config-file is provided)
    # ------------------------------------------------------------------
    if args.config_file:
        if not (args.start_date and args.end_date):
            sys.exit("❌  --start-date and --end-date are required when using --config-file")

        try:
            cfg_manual = json.loads(Path(args.config_file).read_text())
        except Exception as exc:
            sys.exit(f"❌  Cannot read JSON from {args.config_file}: {exc}")

        cfg_manual = fill_defaults(cfg_manual)
        cfg_manual = _sanitize_cfg(cfg_manual)

        # optional blueprint validation unless skipped
        if not args.skip_blueprint_check:
            errs = validate_against_blueprint(cfg_manual, BLUEPRINTS)
            if errs:
                print("❌  Manual config mismatches blueprint:")
                for e in errs:
                    print(f"  – {e}")
                sys.exit("🚫  Fix the above errors or pass --skip-blueprint-check to override.")

        meta_single = {
            "start_time": args.start_date,
            "end_time": args.end_date,
            "resolution": args.resolution,
            "trade_cost": args.fee,
        }

        tag_single = f"manual::{cfg_manual.get('controller_name','unknown')}"
        experiments_single = [(tag_single, cfg_manual, meta_single, short_hash(cfg_manual | meta_single))]

        execute_experiments(experiments_single, retries=args.retries)
        return

    # ------------------------------------------------------------------
    # 🧪 2️⃣  Normal experiment-grid generation mode
    # ------------------------------------------------------------------
    experiments = generate_experiments(fast=args.fast)

    if args.only:
        experiments = [e for e in experiments if args.only in e[0]]
        if not experiments:
            print(f"No experiment tag contains '{args.only}'. Exiting.")
            return

    # --------------------------------------------------
    # 🔍  Blueprint Validation (pre-flight)
    # --------------------------------------------------
    if not args.skip_blueprint_check:
        print("☎️  Validating generated configs against blueprint …")
        bad: List[Tuple[str, List[str]]] = []
        for tag, cfg, meta, _ in experiments:
            errs = validate_against_blueprint(cfg, BLUEPRINTS)
            if errs and DEBUG_MODE:
                template = BLUEPRINTS.get(cfg.get("controller_type", "").lower(), {}).get(cfg.get("controller_name", "").lower())
                print("════════════════ CONFIG VS BLUEPRINT ════════════════")
                print(f"TAG: {tag}\n-- Generated Config --")
                print(_json.dumps(cfg, indent=2)[:1000])
                print("-- Blueprint Template --")
                if template:
                    print(_json.dumps(template, indent=2)[:1000])
                else:
                    print("<None - controller not in blueprint>")
                print("════════════════════════════════════════════════════")
            if errs:
                bad.append((tag, errs))

        if bad:
            print("❌  Found inconsistencies:\n────────────────────────")
            for tag, errs in bad:
                print(f"• {tag}")
                for e in errs:
                    print(f"   – {e}")
                print()
            sys.exit("🚫  Abort: fix the above mismatches before running back-tests.")
        print("✅  All configs match the blueprint – proceeding.\n")

    print("─" * 70)
    mode_label = "FAST" if args.fast else "FULL"
    print(f"[{mode_label} MODE] Generated {len(experiments)} experiment combinations.")
    if experiments:
        print("Example experiment tag:")
        print(f"  {experiments[0][0]}")
    print("─" * 70)

    execute_experiments(experiments, retries=args.retries)



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
