#!/usr/bin/env python3
"""dev_mode_batch.py – Run ONE quick back-test against every local controller.

The goal is instant developer feedback: generate a small CSV that the dashboard
can open (results/detail_packets/*.json + dev_results.csv).

Usage
-----
python3 scripts/dev_mode_batch.py --workers 4 --outfile dev_results.csv

It reuses the helper functions from B_json_to_backtests.py so there is no duplicated
logic.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Ensure project root on PYTHONPATH *before* importing local modules
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Now we can safely import helpers from the main backtesting script
from B_json_to_backtests import (
    run_backtest,
    TestPayload,
    to_timestamp,
    wait_for_api,
    BASE_URL,
    USERNAME,
    PASSWORD,
    DETAILS_DIR,
)

import os
from datetime import datetime, timezone
from requests.auth import HTTPBasicAuth
import csv
import importlib, inspect
from pydantic import BaseModel

CONTROLLERS_DIR = ROOT / "bots" / "controllers"


def discover_controller_files() -> List[tuple[str, str]]:
    """Return list of (controller_type, controller_name) for every .py file."""
    items: List[tuple[str, str]] = []
    for ctype_dir in CONTROLLERS_DIR.iterdir():
        if not ctype_dir.is_dir():
            continue
        ctype = ctype_dir.name
        for pyfile in ctype_dir.glob("*.py"):
            if pyfile.stem in {"__init__"}:
                continue
            items.append((ctype, pyfile.stem))
    return sorted(items)


# ---------------------------------------------------------------------------
# Build default config per controller
# ---------------------------------------------------------------------------

def default_config(ctype: str, cname: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "controller_name": cname,
        "controller_type": ctype,
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        "total_amount_quote": 1000.0,
        "leverage": 20.0,
        # Basic risk params common to MM & directional
        "stop_loss": 0.03,
        "take_profit": 0.02,
        "time_limit": 1800,
        "position_mode": "HEDGE",
        "manual_kill_switch": False,
        "initial_positions": [],
        # Provide candle feed by default (most controllers expect it)
        "candles_config": [
            {
                "connector": "kucoin",
                "trading_pair": "BTC-USDT",
                "interval": "3m",
            }
        ],
    }

    # Market-making specific sensible defaults
    if ctype == "market_making":
        cfg.update(
            {
                "buy_spreads": "0.01",
                "sell_spreads": "0.01",
                "buy_amounts_pct": "100",
                "sell_amounts_pct": "100",
                "executor_refresh_time": 600,
                "cooldown_time": 15,
            }
        )

    # Special-case overrides ------------------------------------------------
    if cname == "pmm_skew":
        cfg["skew_factor"] = 0.0
    if cname == "dman_maker_v2":
        cfg.update(
            {
                "dca_spreads": "0.001,0.01,0.03,0.06",
                "dca_amounts_pct": "25,25,25,25",
            }
        )
    if cname.startswith("dman_v"):
        cfg["max_executors_per_side"] = 4
    # Directional strategies typically need bollinger/macd params but they have defaults.

    # ------------------------------------------------------------------
    # Auto-merge defaults from the controller's *Config class ------------
    # ------------------------------------------------------------------
    try:
        mod_path = f"bots.controllers.{ctype}.{cname}"
        mod = importlib.import_module(mod_path)
        cfg_cls = None
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if inspect.isclass(obj) and attr.endswith("Config"):
                cfg_cls = obj
                break

        if cfg_cls and issubclass(cfg_cls, BaseModel):
            for field_name, field_info in cfg_cls.model_fields.items():
                if field_name in cfg:
                    continue  # already set via hard-coded block above
                default_val = field_info.default
                # Only copy if the model provides an explicit default that is
                # JSON-serialisable and not a sentinel (…)
                if default_val is not None and default_val != ...:
                    # Filter out NumPy NaN or other non-serialisable values
                    try:
                        import math, numbers

                        if isinstance(default_val, float) and (math.isnan(default_val) or math.isinf(default_val)):
                            continue
                    except Exception:
                        pass

                    cfg[field_name] = default_val
    except Exception as import_exc:
        print(f"⚠️  Could not introspect defaults for {cname}: {import_exc}")

    return cfg


def build_payloads() -> List[TestPayload]:
    tests: List[TestPayload] = []
    start = to_timestamp("2024-03-11")
    end = to_timestamp("2024-03-13")
    for ctype, cname in discover_controller_files():
        cfg = default_config(ctype, cname)
        # Ensure candles_config entries carry start/end for consistent candle window
        if isinstance(cfg.get("candles_config"), list):
            for cd in cfg["candles_config"]:
                if isinstance(cd, dict):
                    cd.setdefault("start_time", start)
                    cd.setdefault("end_time", end)

        tests.append(TestPayload(label=cfg["controller_name"], config=cfg, start=start, end=end))
    return tests


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Developer-mode batch over all controllers")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--outfile", default="dev_results.csv", help="CSV output path")
    args = parser.parse_args()

    wait_for_api()
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    tests = build_payloads()
    print(f"Discovered {len(tests)} controllers → running quick batch…")

    # Directory may have been removed by Makefile purge – recreate it.
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    # Re-use B_json_to_backtests.run_backtest but simple thread pool here
    from concurrent.futures import ThreadPoolExecutor, as_completed
    rows: List[Dict[str, Any]] = []
    index_rows: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut_map = {ex.submit(run_backtest, t.to_body(), auth, 1): t for t in tests}
        for fut in as_completed(fut_map):
            t = fut_map[fut]
            res = fut.result()
            status = "✅" if not res.get("error") else "❌"
            print(f"{status} {t.label}")

            if res.get("error"):
                # Remove any stale packet
                stale = DETAILS_DIR / f"{t.label}.json"
                if stale.exists():
                    stale.unlink(missing_ok=True)
                # skip adding to CSV; only successful runs keep
                continue

            # Save detail packet for dashboard ------------------------------
            try:
                safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in t.label)
                out_json = DETAILS_DIR / f"{safe}.json"
                tmp_path = out_json.with_suffix(out_json.suffix + ".tmp")
                import json

                with tmp_path.open("w") as fp:
                    json.dump(res, fp, indent=2)
                tmp_path.replace(out_json)
            except Exception as exc:
                print(f"⚠️  Could not save detail packet for {t.label}: {exc}")

            rows.append({"label": t.label, **res.get("results", res)})
            # also include flattened config keys for parameter inspection
            for k, v in t.config.items():
                if k not in rows[-1]:
                    rows[-1][k] = v

            # assemble index row
            packet_path = DETAILS_DIR / f"{t.label}.json"
            event_csv = res.get("event_log_csv", "")
            index_rows.append({
                "label": t.label,
                "file_path": str(packet_path),
                "size": packet_path.stat().st_size if packet_path.exists() else 0,
                "mtime": int(packet_path.stat().st_mtime) if packet_path.exists() else 0,
                "event_log_csv": event_csv,
                "valid": 1,
                "note": "",
            })

    # Write CSV ------------------------------------------------------------
    import pandas as pd

    df = pd.json_normalize(rows)
    df.to_csv(args.outfile, index=False)
    print(f"Saved → {args.outfile} ({len(df)} rows)")

    # Write index CSV
    if index_rows:
        idx_df = pd.DataFrame(index_rows)
        idx_df.to_csv(DETAILS_DIR / "_index.csv", index=False)
        print(f"Updated index → {DETAILS_DIR / '_index.csv'} ({len(idx_df)} rows)")

    # Debug: list files written
    pkt_files = list(DETAILS_DIR.glob("*.json"))
    print(f"Wrote {len(pkt_files)} detail packets to {DETAILS_DIR}")


if __name__ == "__main__":
    main() 