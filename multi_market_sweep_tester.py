#!/usr/bin/env python3
"""multi_market_sweep_tester.py – Run all market-making sweeps in one go

This script discovers *\*_sweep.yml files whose base.controller_type == 'market_making',
expands them via grid_builder, fires the payloads at `/run-backtesting` in parallel
(using the same logic as `batch_tester.py`), and concatenates the results into a
single CSV for easy comparison.

Usage
-----
python3 multi_market_sweep_tester.py --sweeps sweeps/ --workers 8 --outfile mm_master_results.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

import requests
from requests.auth import HTTPBasicAuth

try:
    import yaml  # type: ignore
except ImportError:
    sys.exit("Install PyYAML first: pip install pyyaml")

import pandas as pd

from grid_builder import build_payloads
from batch_tester import (
    run_backtest,
    validate_against_blueprint,
    _normalize_blueprints,
    TestPayload,
    BLUEPRINT_PATH,
    BASE_URL,
    USERNAME,
    PASSWORD,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_api(host: str = "localhost", port: int = 8000, timeout: int = 30) -> None:
    import socket, time
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                return
        time.sleep(1)
    raise RuntimeError("API not ready after %s s" % timeout)


def sweep_yaml_files(sweeps_dir: Path) -> List[Path]:
    return sorted(p for p in sweeps_dir.glob("*_sweep.yml"))


def tests_from_sweep(path: Path) -> List[TestPayload]:
    raw = yaml.safe_load(path.read_text())
    base = raw.get("base", {})
    if base.get("controller_type", "").lower() != "market_making":
        return []
    grid = raw.get("grid", {})
    meta = raw.get("meta", {})
    payloads = build_payloads(base, grid, meta)
    # convert to TestPayload objects (reuse batch_tester logic via tmp json)
    tmp = Path(tempfile.gettempdir()) / f"{path.stem}_payloads.json"
    tmp.write_text(json.dumps(payloads, default=str))
    from batch_tester import load_tests_from_file  # late import to avoid cycles

    return load_tests_from_file(str(tmp))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run all market-making sweeps")
    ap.add_argument("--sweeps", default="sweeps", help="Directory containing *_sweep.yml files")
    ap.add_argument("--workers", type=int, default=8, help="ThreadPool workers")
    ap.add_argument("--outfile", default="mm_master_results.csv", help="Output CSV")
    ap.add_argument("--retries", type=int, default=1, help="Network retry attempts")
    ap.add_argument("--no-schema", action="store_true", help="Skip schema validation")
    args = ap.parse_args(argv)

    sweeps_path = Path(args.sweeps)
    if not sweeps_path.is_dir():
        sys.exit(f"No such sweeps dir: {sweeps_path}")

    wait_for_api()
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    # collect tests
    tests: List[TestPayload] = []
    for yml in sweep_yaml_files(sweeps_path):
        subtests = tests_from_sweep(yml)
        if subtests:
            print(f"Found {len(subtests)} payloads in {yml.name}")
            tests.extend(subtests)

    if not tests:
        sys.exit("No market_making sweeps found.")

    # blueprint
    blueprints = None
    if not args.no_schema and Path(BLUEPRINT_PATH).exists():
        try:
            blueprints = _normalize_blueprints(json.loads(Path(BLUEPRINT_PATH).read_text()))
        except Exception as exc:
            print(f"⚠️  Could not load blueprint ({exc}) – skipping validation")

    rows: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fut_map = {ex.submit(run_backtest, t.to_body(), auth, args.retries): t for t in tests}
        for fut in as_completed(fut_map):
            t = fut_map[fut]
            res = fut.result()
            if blueprints:
                errs = validate_against_blueprint(t.config, blueprints)
                if errs:
                    res.setdefault("error", "; ".join(errs))
            algo = t.config.get("controller_name", "unknown")
            rows.append({"algo": algo, "label": t.label, **res.get("results", res)})
            status = "✅" if "error" not in res else "❌"
            print(f"{status} {t.label}")

    df = pd.json_normalize(rows)
    df.to_csv(args.outfile, index=False)
    print(f"Saved → {args.outfile} ({len(df)} rows)")


if __name__ == "__main__":
    main() 