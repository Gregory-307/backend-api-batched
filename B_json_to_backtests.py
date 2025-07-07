#!/usr/bin/env python3
"""
B_json_to_backtests.py – Batch Back-Tester for Hummingbot Controllers
===================================================================

Why another script?
-------------------
`exp_run_serial.py` grew into an all-singing, all-dancing behemoth.  When you
just want to throw **N** controller-configs at `/run-backtesting` and capture
results, you shouldn't have to read 700 lines of code.

This file is ~150 lines.  It focuses on:

* Waiting for the API to be ready.
* Reading a JSON/YAML list of controller configs (or generating a tiny demo set).
* POSTing each payload with retry/back-off.
* Writing a tidy CSV (or JSON) of results.
* Printing a colourised summary table.

Usage examples
--------------
```bash
# 1. Quick demo run (uses 3 hard-coded configs)
python3 B_json_to_backtests.py --demo

# 2. Point at your own file (list or dict of configs)
python3 B_json_to_backtests.py --file my_tests.json --outfile results.csv

# 3. Run with 4 parallel workers and 2 retries on network errors
python3 B_json_to_backtests.py --file tests.yml --workers 4 --retries 2
```

The input file may be JSON **or** YAML.
Each element must look like the `config` section of `/run-backtesting`.

See the bottom of this file for a minimal example.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import requests
from requests.auth import HTTPBasicAuth

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

try:
    from rich import box, print
    from rich.console import Console
    from rich.table import Table
except ImportError:  # pragma: no cover
    print("⚠️  Install rich for prettier tables: pip install rich", file=sys.stderr)
    Console = None  # type: ignore
    Table = None  # type: ignore

# Optional progress bar -----------------------------------------------------
try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class TestPayload:
    label: str
    config: Dict[str, Any]
    start: int
    end: int
    resolution: str = "3m"
    fee: float = 0.001
    sweep_params: Dict[str, Any] | None = None

    def to_body(self) -> Dict[str, Any]:
        return {
            "start_time": self.start,
            "end_time": self.end,
            "backtesting_resolution": self.resolution,
            "trade_cost": self.fee,
            "config": self.config,
        }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_URL: str = os.getenv("HB_API", "http://localhost:8000")
USERNAME: str = os.getenv("HB_USER", "admin")
PASSWORD: str = os.getenv("HB_PASS", "admin")
BLUEPRINT_PATH: str = os.getenv("HB_SCHEMA", "bots/hummingbot_files/schema/all_controller_configs.json")


def to_timestamp(date_str: str) -> int:
    """YYYY-MM-DD -> unix ts (UTC midnight)."""
    y, m, d = map(int, date_str.split("-"))
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


def wait_for_api(host: str = "localhost", port: int = 8000, timeout: int = 30) -> None:
    import socket
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                return
        time.sleep(1)
    raise RuntimeError("API not ready after %s s" % timeout)


def run_backtest(body: Dict[str, Any], auth: HTTPBasicAuth, retries: int = 1) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            r = requests.post(f"{BASE_URL}/run-backtesting", json=body, auth=auth, timeout=1200)
            try:
                data = r.json()
            except ValueError:
                data = {"error": "non-json response", "raw": r.text[:400]}
            if r.status_code != 200:
                data.setdefault("error", f"HTTP {r.status_code}")
            return data
        except requests.exceptions.RequestException as exc:
            if attempt >= retries:
                return {"error": str(exc)}
            time.sleep(2 ** attempt)
            attempt += 1


def load_tests_from_file(path: str) -> List[TestPayload]:
    raw_txt = Path(path).read_text()
    if path.endswith(('.yml', '.yaml')):
        if yaml is None:
            sys.exit("Install PyYAML to read YAML files.")
        data = yaml.safe_load(raw_txt)
    else:
        data = json.loads(raw_txt)

    if isinstance(data, dict):
        # single block -> wrap in list
        data = [data]

    tests: List[TestPayload] = []
    for i, cfg in enumerate(data):
        # If payload is already wrapper with 'config'
        if "config" in cfg:
            inner = cfg.pop("config")
            start = cfg.pop("start", "2024-03-11")
            end = cfg.pop("end", "2024-03-13")
            label = cfg.get("label") or inner.get("controller_name") or f"test{i+1}"
            tests.append(
                TestPayload(
                    label=label,
                    config=inner,
                    start=to_timestamp(start),
                    end=to_timestamp(end),
                    resolution=str(cfg.get("resolution", "3m")),
                    fee=float(cfg.get("fee", 0.001)),
                    sweep_params=cfg.pop("_sweep_params", None) if isinstance(cfg, dict) else None,
                )
            )
        else:
            label = cfg.get("label") or cfg.get("controller_name") or f"test{i+1}"
            start = cfg.pop("start", "2024-03-11")
            end = cfg.pop("end", "2024-03-13")
            tests.append(
                TestPayload(
                    label=label,
                    config=cfg,
                    start=to_timestamp(start),
                    end=to_timestamp(end),
                    resolution=str(cfg.get("resolution", "3m")),
                    fee=float(cfg.get("fee", 0.001)),
                    sweep_params=cfg.pop("_sweep_params", None) if isinstance(cfg, dict) else None,
                )
            )
    return tests


def demo_tests() -> List[TestPayload]:
    demo_cfgs: List[TestPayload] = []
    base = {
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20,
    }
    demo_cfgs.append(
        TestPayload(
            "pmm_dynamic_demo",
            {
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
            },
            start=to_timestamp("2024-03-11"),
            end=to_timestamp("2024-03-13"),
        )
    )
    demo_cfgs.append(
        TestPayload(
            "dman_v3_demo",
            {
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
                "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}],
            },
            start=to_timestamp("2024-03-11"),
            end=to_timestamp("2024-03-13"),
        )
    )
    return demo_cfgs

# --- Blueprint helpers -------------------------------------------------------


def _normalize_blueprints(raw: dict) -> dict:
    """Lower-case keys for easy lookup."""
    norm: dict = {}
    for ctype, ctrls in raw.items():
        norm[ctype.lower()] = {n.lower(): cfg for n, cfg in ctrls.items()}
    return norm


def validate_against_blueprint(cfg: dict, blueprints: dict) -> List[str]:
    """Return list of error strings; empty = ok."""
    ctype = cfg.get("controller_type", "").lower()
    cname = cfg.get("controller_name", "").lower()
    tmpl = blueprints.get(ctype, {}).get(cname)
    if tmpl is None:
        return [f"Unknown controller {ctype}/{cname} in blueprint"]

    missing = set(tmpl) - set(cfg)
    extra = set(cfg) - set(tmpl)
    errs: List[str] = []
    if missing:
        errs.append(f"missing {sorted(missing)}")
    # only warn on extra keys, not error
    for k in tmpl:
        if k in cfg and cfg[k] is None and tmpl[k] is not None:
            errs.append(f"null where {k} expects {type(tmpl[k]).__name__}")
    return errs

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Simple batch back-tester")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="JSON/YAML file with list of configs")
    g.add_argument("--demo", action="store_true", help="Run built-in demo")
    p.add_argument("--workers", type=int, default=4, help="Parallel workers")
    p.add_argument("--retries", type=int, default=1, help="Network retry count")
    p.add_argument("--outfile", default="batch_results.csv", help="Where to save CSV")
    p.add_argument("--no-schema", action="store_true", help="Skip blueprint validation")
    p.add_argument("--single-run", action="store_true", help="Run only the first payload from the file")
    args = p.parse_args(argv)

    wait_for_api()
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    tests = demo_tests() if args.demo else load_tests_from_file(args.file)
    if args.single_run and tests:
        tests = tests[:1]
        print("🔂 --single-run flag detected – executing only the first payload.")

    # load blueprint if available and validation requested
    blueprints = None
    if not args.no_schema and Path(BLUEPRINT_PATH).exists():
        try:
            blueprints = _normalize_blueprints(json.loads(Path(BLUEPRINT_PATH).read_text()))
        except Exception as exc:
            print(f"⚠️  Could not load blueprint ({exc}) – skipping validation")

    if not tests:
        sys.exit("No tests loaded.")

    # --------------------------------------------------------------------
    # Detail packet directory  (results/detail_packets/<outfile_stem>/)
    # --------------------------------------------------------------------
    stem_out = Path(args.outfile).stem
    global DETAILS_DIR  # override module-level placeholder
    DETAILS_DIR = Path(os.getenv("HB_DETAIL_DIR", f"results/detail_packets/{stem_out}"))
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    print(f"🗒  Total tests scheduled: {len(tests)}  •  Workers: {args.workers}")

    total_tests = len(tests)
    # Initialise progress bar or counter
    pbar = tqdm(total=total_tests, desc="Backtests", unit="run") if tqdm else None
    done_ctr = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut_map = {ex.submit(run_backtest, t.to_body(), auth, args.retries): t for t in tests}
        for fut in as_completed(fut_map):
            t = fut_map[fut]
            res = fut.result()

            if blueprints:
                errs = validate_against_blueprint(t.config, blueprints)
                if errs:
                    res.setdefault("error", "; ".join(errs))

            # Persist full response packet for later visualisation / debugging
            try:
                safe_label = ''.join(c if c.isalnum() or c in ('-_') else '_' for c in t.label)
                out_json = DETAILS_DIR / f"{safe_label}.json"
                tmp_path = out_json.with_suffix(out_json.suffix + ".tmp")
                with tmp_path.open("w") as fp:
                    json.dump(res, fp, indent=2)
                tmp_path.replace(out_json)
            except Exception as exc:
                print(f"⚠️  Could not save detail packet for {t.label}: {exc}")

            raw_row = {"label": t.label, **res.get("results", res)}
            if t.sweep_params:
                raw_row.update(t.sweep_params)

            def _coerce(val):
                if isinstance(val, (list, dict)):
                    return json.dumps(val, separators=(",", ":"))
                return val

            rows.append({k: _coerce(v) for k, v in raw_row.items()})

            # ---------------- Additional diagnostic columns ----------------
            try:
                execs = res.get("executors", [])
                if execs:
                    execs_sorted = sorted(
                        execs,
                        key=lambda e: e.get("timestamp") or e.get("entry_timestamp", 0),
                    )
                    def _side(e):
                        val = e.get("side") or e.get("config", {}).get("side")
                        return "buy" if str(val) in ("1", "buy", "BUY") else "sell"

                    first_buy = next((e for e in execs_sorted if _side(e) == "buy"), None)
                    first_sell = next((e for e in execs_sorted if _side(e) == "sell"), None)

                    if first_buy is not None:
                        rows[-1]["first_buy_price"] = first_buy.get("entry_price")
                        rows[-1]["first_buy_ts"] = first_buy.get("timestamp") or first_buy.get("entry_timestamp")
                    if first_sell is not None:
                        rows[-1]["first_sell_price"] = first_sell.get("entry_price")
                        rows[-1]["first_sell_ts"] = first_sell.get("timestamp") or first_sell.get("entry_timestamp")
            except Exception:
                # Keep the batch run resilient; swallow any parsing errors.
                pass
            # Status icon logic: green check=success with trades, yellow alert=no trades, red cross=error
            if "error" in res:
                status = "❌"
                reason = res.get("error", "error")
            else:
                trades = res.get("results", {}).get("trades") if isinstance(res.get("results"), dict) else None
                if trades in (0, None):
                    status = "⚠️"
                    reason = "no trades"
                else:
                    status = "✅"
                    reason = ""

            # Render progress ------------------------------------------------
            msg = f"{status} {t.label} {reason}"
            if pbar is not None:
                pbar.update(1)
                pbar.write(msg)
            else:
                done_ctr += 1
                print(f"[{done_ctr}/{total_tests}] {msg}", flush=True)

    import pandas as pd

    df = pd.json_normalize(rows)
    outfile = Path(args.outfile)
    # Always write full header to avoid column-mismatch tokenising errors on reload.
    # Keeping historical rows: we read existing CSV (if any), union its columns with new df, and rewrite.
    if outfile.exists():
        try:
            prev = pd.read_csv(outfile)
            df = pd.concat([prev, df], ignore_index=True)
        except Exception:
            # Corrupt or incompatible old CSV – we overwrite.
            pass
    df.to_csv(outfile, index=False)

    if Console and Table:
        tbl = Table(box=box.SIMPLE)
        for col in df.columns[:10]:  # show first 10 cols
            tbl.add_column(col)
        for _, r in df.head(50).iterrows():  # limit
            tbl.add_row(*[str(r[c]) for c in df.columns[:10]])
        Console().print(tbl)

    if pbar is not None:
        pbar.close()


if __name__ == "__main__":
    main() 