#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A_yml_to_json.py (formerly *grid_builder.py*)
------------------------------------------------
Convert a terse YAML sweep file into the JSON payload structure expected by
*B_json_to_backtests.py* (formerly *batch_tester.py*).

The CLI accepts `--meta-file` to merge date / resolution / fee overrides so
downstream automation (Makefile targets, etc.) continues to work unchanged
after removal of legacy wrapper scripts.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.exit("Install PyYAML first: pip install pyyaml")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def expand_grid(grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Cartesian-product expansion of the parameter grid."""
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values = list(grid.values())
    return [dict(zip(keys, combo)) for combo in product(*values)]


META_KEYS = {"start", "end", "resolution", "fee"}


def build_payloads(
    base: Dict[str, Any],
    grid: Dict[str, List[Any]] | None,
    meta: Dict[str, Any] | None,
    sweep: Dict[str, List[Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Build the list of payloads, adding `_sweep_params` for downstream CSV writing."""

    grid = grid or {}
    sweep = sweep or {}
    meta = meta or {}

    variants: List[Dict[str, Any]] = []

    # 1. Cartesian-product grid ------------------------------------------------
    variants.extend(expand_grid(grid))  # returns [{}] if grid empty

    # 2. Linear sweeps (vary one key at a time) --------------------------------
    for key, values in sweep.items():
        for v in (values or []):
            variants.append({key: v})

    out: List[Dict[str, Any]] = []
    for idx, variant in enumerate(variants, 1):
        cfg = {**base, **variant}

        # Ensure spreads are lists (schema requires list[float]) – but only
        # if the key exists; do NOT introduce empty lists that break models
        for k in ("buy_spreads", "sell_spreads"):
            if k in cfg and not isinstance(cfg[k], list):
                cfg[k] = [cfg[k]]

        # If corresponding amounts pct missing, generate equal allocation – but
        # only when spreads key exists in the original config.
        for spread_key, amt_key in (("buy_spreads", "buy_amounts_pct"), ("sell_spreads", "sell_amounts_pct")):
            if spread_key in cfg:
                if amt_key not in cfg:
                    spreads_list = cfg.get(spread_key) or []
                    if spreads_list:
                        equal = round(1.0 / len(spreads_list), 6)
                        cfg[amt_key] = [equal] * len(spreads_list)

        # Propagate start/end into candles_config for robust data retrieval
        if "candles_config" in cfg and isinstance(cfg["candles_config"], list):
            for feed in cfg["candles_config"]:
                if isinstance(feed, dict):
                    if "start_time" not in feed and meta.get("start"):
                        feed["start_time"] = meta["start"]
                    if "end_time" not in feed and meta.get("end"):
                        feed["end_time"] = meta["end"]

        # Validate spread/amount pairing – warn user if config is incomplete
        for s_key, a_key in (("buy_spreads", "buy_amounts_pct"), ("sell_spreads", "sell_amounts_pct")):
            raw_spreads = cfg.get(s_key, [])
            if raw_spreads is None:
                raw_spreads = []
            if not isinstance(raw_spreads, list):
                raw_spreads = [raw_spreads]

            spreads = raw_spreads

            raw_amounts = cfg.get(a_key)
            if raw_amounts is not None and not isinstance(raw_amounts, list):
                raw_amounts = [raw_amounts]
            amounts = raw_amounts

            # If amounts missing but spreads present → auto-equal & warn
            if s_key in cfg and spreads and not amounts:
                print(f"⚠️  {cfg.get('controller_name')} missing {a_key} for spreads {s_key}; defaulting to equal distribution.")
                cfg[a_key] = [round(1 / len(spreads), 6)] * len(spreads)
            elif s_key in cfg and amounts and len(amounts) != len(spreads):
                print(f"⚠️  {cfg.get('controller_name')} – length mismatch {s_key} vs {a_key}; trimming to min length.")
                m = min(len(spreads), len(amounts))
                cfg[s_key] = spreads[:m]
                cfg[a_key] = amounts[:m]
            else:
                # write back coerced lists when key exists
                if s_key in cfg:
                    cfg[s_key] = spreads
                    if amounts is not None:
                        cfg[a_key] = amounts

        payload: Dict[str, Any] = {"config": cfg}
        # copy meta keys out; unknown meta items fall back into config
        for k, v in meta.items():
            if k in META_KEYS:
                payload[k] = v
            else:
                cfg[k] = v

        # Label for nicer reporting
        payload.setdefault("label", f"{cfg.get('controller_name','unknown')}_{idx}")

        # Embed sweep parameters so downstream scripts can write them to CSV
        sweep_cols = list(grid.keys()) + list(sweep.keys())
        payload["_sweep_params"] = {k: cfg.get(k) for k in sweep_cols}

        # dman_maker_v2 requires list for activation_bounds
        if cfg.get("controller_name") == "dman_maker_v2" and "executor_activation_bounds" not in cfg:
            cfg["executor_activation_bounds"] = []

        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input YAML grid file")
    ap.add_argument("--out", required=True, help="Output JSON file for batch_tester")
    ap.add_argument("--meta-file", help="YAML file containing meta overrides (start, end, resolution, fee, etc.)")
    ap.add_argument("--no-schema", action="store_true", help="Include no_schema flag in each payload so batch_tester skips schema validation")
    args = ap.parse_args(argv)

    data = yaml.safe_load(Path(args.inp).read_text())
    base = data.get("base", {})
    grid = data.get("grid", {})
    sweep = data.get("sweep", {})
    meta = data.get("meta", {})

    # Optional meta overrides (same semantics as the legacy wrapper)
    if args.meta_file:
        try:
            meta_override = yaml.safe_load(Path(args.meta_file).read_text()) or {}
        except Exception as exc:
            sys.exit(f"Could not read --meta-file {args.meta_file}: {exc}")
        for k, v in meta_override.items():
            if k in META_KEYS:
                meta[k] = v
            else:
                base[k] = v

    if args.no_schema:
        meta = {**meta, "no_schema": True}
    payloads = build_payloads(base, grid, meta, sweep=sweep)
    Path(args.out).write_text(json.dumps(payloads, indent=2, default=str))
    print(f"Wrote {len(payloads)} payloads → {args.out}")


if __name__ == "__main__":
    main()