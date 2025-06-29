#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grid_builder.py
------------------
Convert a terse YAML grid into the JSON structure expected by *batch_tester.py*.
See header comments for example.
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


def build_payloads(base: Dict[str, Any], grid: Dict[str, List[Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of API-ready payload dicts."""
    out: List[Dict[str, Any]] = []
    for idx, variant in enumerate(expand_grid(grid), 1):
        cfg = {**base, **variant}

        # Ensure spreads are lists (schema requires list[float])
        for k in ("buy_spreads", "sell_spreads"):
            if k in cfg and not isinstance(cfg[k], list):
                cfg[k] = [cfg[k]]

        # If corresponding amounts pct missing, generate equal allocation
        for spread_key, amt_key in (("buy_spreads", "buy_amounts_pct"), ("sell_spreads", "sell_amounts_pct")):
            if spread_key in cfg and amt_key not in cfg:
                n = len(cfg[spread_key])
                if n:
                    equal = round(1.0 / n, 6)
                    cfg[amt_key] = [equal] * n

        # Propagate start/end into candles_config for robust data retrieval
        if "candles_config" in cfg and isinstance(cfg["candles_config"], list):
            for feed in cfg["candles_config"]:
                if isinstance(feed, dict):
                    if "start_time" not in feed and meta.get("start"):
                        feed["start_time"] = meta["start"]
                    if "end_time" not in feed and meta.get("end"):
                        feed["end_time"] = meta["end"]

        payload: Dict[str, Any] = {"config": cfg}
        # copy meta keys out; unknown meta items fall back into config
        for k, v in meta.items():
            if k in META_KEYS:
                payload[k] = v
            else:
                cfg[k] = v

        # Add label for nicer reporting
        payload.setdefault("label", f"{cfg.get('controller_name','unknown')}_{idx}")
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input YAML grid file")
    ap.add_argument("--out", required=True, help="Output JSON file for batch_tester")
    ap.add_argument("--no-schema", action="store_true", help="Include no_schema flag in each payload so batch_tester skips schema validation")
    args = ap.parse_args(argv)

    data = yaml.safe_load(Path(args.inp).read_text())
    base = data.get("base", {})
    grid = data.get("grid", {})
    meta = data.get("meta", {})

    if args.no_schema:
        meta = {**meta, "no_schema": True}
    payloads = build_payloads(base, grid, meta)
    Path(args.out).write_text(json.dumps(payloads, indent=2, default=str))
    print(f"Wrote {len(payloads)} payloads → {args.out}")


if __name__ == "__main__":
    main()