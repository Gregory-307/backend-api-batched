#!/usr/bin/env python3
"""multi_market_sweep_tester.py – Run all market-making sweeps in one go

This script discovers *_sweep.yml files whose base.controller_type == 'market_making',
expands them via A_yml_to_json (former grid_builder), fires the payloads at `/run-backtesting` in parallel
(using the same logic as `B_json_to_backtests.py`, formerly `batch_tester.py`), and concatenates the results into a
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
import hashlib

import requests
from requests.auth import HTTPBasicAuth

try:
    import yaml  # type: ignore
except ImportError:
    sys.exit("Install PyYAML first: pip install pyyaml")

import pandas as pd

from A_yml_to_json import build_payloads
from B_json_to_backtests import (
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
    """Return one YAML per controller.

    Priority order (highest → lowest):
    1. File inside `sweeps/generated/` with canonical name `<ctrl>_sweep.yml`.
    2. If not present, any fallback file ending in `.new.yml` under generated/.
    3. Finally, the curated stub in the top-level `sweeps/` folder.

    This lets fresh scaffolds override stale curated files without the
    developer having to manually copy or delete anything, fixing the
    "missing kucoin connector" situation the user hit earlier.
    """
    chosen: Dict[str, Path] = {}

    gen_dir = sweeps_dir / "generated"
    if gen_dir.is_dir():
        # First take canonical files
        for p in gen_dir.glob("*_sweep.yml"):
            chosen[p.stem] = p
        # Then .new.yml if controller not already chosen
        for p in gen_dir.glob("*_sweep.new.yml"):
            key = p.stem.replace(".new", "")
            chosen.setdefault(key, p)

    # Finally curated files, but only if not overridden
    for p in sweeps_dir.glob("*_sweep.yml"):
        chosen.setdefault(p.stem, p)

    return sorted(chosen.values())


def tests_from_sweep(path: Path, meta_override: Dict[str, Any] | None = None) -> List[TestPayload]:
    raw = yaml.safe_load(path.read_text())
    base = raw.get("base", {}) or {}
    grid = raw.get("grid", {}) or {}
    sweep = raw.get("sweep", {}) or {}
    meta = raw.get("meta", {}) or {}

    if meta_override:
        for k, v in meta_override.items():
            if k in {"start", "end", "resolution", "fee"}:
                meta[k] = v
            else:
                base[k] = v
    payloads = build_payloads(base, grid, meta, sweep=sweep)
    # convert to TestPayload objects (reuse B_json_to_backtests logic via tmp json)
    tmp = Path(tempfile.gettempdir()) / f"{path.stem}_payloads.json"
    tmp.write_text(json.dumps(payloads, default=str))
    from B_json_to_backtests import load_tests_from_file  # late import to avoid cycles

    return load_tests_from_file(str(tmp))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run all market-making sweeps")
    ap.add_argument("--sweeps", default="sweeps", help="Directory containing *_sweep.yml files")
    ap.add_argument("--workers", type=int, default=8, help="ThreadPool workers")
    ap.add_argument("--outfile", default=None, help="Output CSV (default based on run-id)")
    ap.add_argument("--retries", type=int, default=1, help="Network retry attempts")
    ap.add_argument("--no-schema", action="store_true", help="Skip schema validation")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh backtests (ignore results/cache)")
    ap.add_argument("--single-run", action="store_true", help="Run only the first payload from each sweep file.")
    ap.add_argument("--meta-file", help="YAML file with meta overrides (start, end, resolution, fee, trading_pair, etc.)")
    ap.add_argument("--run-id", help="Optional run identifier (used for CSV + detail dir). Default: <mode>_<YYYY-MM-DD_HHMMSS>")
    ap.add_argument("--mode", default="mm", help="Label prefix for run-id (mm, dev, smoke, etc.)")
    args = ap.parse_args(argv)

    if not args.run_id:
        if args.mode in {"dev", "development"}:
            args.run_id = "dev_results"
        elif args.mode in {"demo", "smoke"}:
            args.run_id = "demo_results"
        else:
            from datetime import datetime
            ts = datetime.utcnow().strftime("%F_%H%M%S")
            args.run_id = f"{args.mode}_{ts}"

    if not args.outfile:
        # Stable file naming per mode ----------------------------------------------------
        if args.mode in {"dev", "development"}:
            args.outfile = "results/summaries/dev_results.csv"
        elif args.mode in {"demo", "smoke"}:
            args.outfile = "results/summaries/demo_results.csv"
        else:
            args.outfile = "results/summaries/main_results.csv"

    sweeps_path = Path(args.sweeps)
    if not sweeps_path.is_dir():
        sys.exit(f"No such sweeps dir: {sweeps_path}")

    wait_for_api()
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    meta_override: Dict[str, Any] | None = None
    if args.meta_file:
        meta_override = yaml.safe_load(Path(args.meta_file).read_text()) or {}

    # collect tests
    tests: List[TestPayload] = []
    for yml in sweep_yaml_files(sweeps_path):
        subtests = tests_from_sweep(yml, meta_override=meta_override)
        if subtests:
            if args.single_run:
                tests.append(subtests[0])
                print(f"➕ Collected 1 payload from {yml.name} (single-run)")
            else:
                tests.extend(subtests)
                print(f"➕ Collected {len(subtests)} payloads from {yml.name}")

    if not tests:
        sys.exit("No market_making sweeps found.")

    print(f"🗒  Total tests scheduled: {len(tests)}")

    # blueprint
    blueprints = None
    if not args.no_schema and Path(BLUEPRINT_PATH).exists():
        try:
            blueprints = _normalize_blueprints(json.loads(Path(BLUEPRINT_PATH).read_text()))
        except Exception as exc:
            print(f"⚠️  Could not load blueprint ({exc}) – skipping validation")

    rows: List[Dict[str, Any]] = []

    # Directory for detail packets (shared with B_json_to_backtests)
    DETAILS_DIR = Path("results/detail_packets") / args.run_id
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    CACHE_DIR = Path("results/cache")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        def submit_test(payload: TestPayload):
            body = payload.to_body()
            blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
            hsh = hashlib.sha256(blob.encode()).hexdigest()[:16]
            cache_file = CACHE_DIR / f"{hsh}.json"
            if not args.no_cache and cache_file.exists():
                with cache_file.open() as fp:
                    data = json.load(fp)
                data.setdefault("cached", True)
                return (payload, data)
            res = run_backtest(body, auth, args.retries)
            try:
                cache_file.write_text(json.dumps(res, indent=2))
            except Exception:
                pass
            res["cached"] = False
            return (payload, res)

        fut_map = {ex.submit(submit_test, t): t for t in tests}
        for fut in as_completed(fut_map):
            t = fut_map[fut]
            try:
                p, res = fut.result()
            except Exception as exc:
                res = {"error": str(exc)}
                p = t
            if blueprints:
                errs = validate_against_blueprint(p.config, blueprints)
                if errs:
                    res.setdefault("error", "; ".join(errs))
            algo = p.config.get("controller_name", "unknown")
            # Persist full detail packet
            try:
                safe_label = ''.join(c if c.isalnum() or c in ('-_') else '_' for c in p.label)
                out_json = DETAILS_DIR / f"{safe_label}.json"
                if not out_json.exists():
                    with out_json.open("w") as fp:
                        json.dump(res, fp, indent=2)
            except Exception as exc:
                print(f"⚠️  Could not save detail packet for {p.label}: {exc}")
            has_err = "error" in res
            # Determine status icon (✅ success & trades, ⚠️ no trades, ❌ error)
            trades_val = res.get("results", {}).get("trades") if isinstance(res.get("results"), dict) else None
            if has_err:
                status = "❌"
            elif trades_val in (0, None):
                status = "⚠️"
            else:
                status = "✅"
            # Prefix config keys to avoid clash with result metrics
            cfg_prefixed = {f"cfg_{k}": v for k, v in p.config.items()}
            rows.append({"algo": algo, "label": p.label, "cached": res.get("cached", False), **cfg_prefixed, **res.get("results", res)})
            msg = res.get("error", "")[:160]
            if res.get("cached"):
                status = "⏩"  # skipped from cache
            prefix = "⚠️" if has_err else status
            print(f"{prefix} {p.label}{' – ' + msg if has_err else ''}")

    df = pd.json_normalize(rows)
    out_csv = Path(args.outfile)
    if out_csv.exists():
        try:
            prev = pd.read_csv(out_csv)
            df = pd.concat([prev, df], ignore_index=True)
        except Exception:
            pass
    df.to_csv(out_csv, index=False)

    n_fail = sum(1 for r in rows if "error" in r)
    n_ok = len(rows) - n_fail
    print("────────────────────────────────────────")
    print(f"Finished. Success: {n_ok}  Failures: {n_fail}. Saved → {out_csv}")


if __name__ == "__main__":
    main() 