#!/usr/bin/env python3
"""scaffold_sweeps.py – generate stub sweep YAMLs for every controller.

The script introspects `bots.controllers` looking for *Config classes that
contain a `controller_name` attribute.  For each such class it builds a
minimal sweep YAML containing:
    base:   defaults pulled from the Pydantic model
    grid:   empty dict (placeholder for user parameters)
    meta:   demo date range (back-test two days)

If a curated sweep with the same controller name already exists in
`sweeps/`, the script **does not overwrite it**.
    • instead writes      → sweeps/generated/<name>_sweep.new.yml
    • prints a unified diff so you can copy/paste changes.

If no sweep exists it writes a ready-to-edit file under
`sweeps/generated/<name>_sweep.yml`.

Usage
-----
    python3 scripts/scaffold_sweeps.py   # scans everything

The script is idempotent and safe to run anytime.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
import difflib
from typing import Any, Dict, List
import numpy as _np
import requests
import os
import argparse

try:
    import yaml  # type: ignore
except ImportError:
    sys.exit("Install PyYAML: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
SWEEP_DIR = ROOT / "sweeps"
GEN_DIR = SWEEP_DIR / "generated"
GEN_DIR.mkdir(parents=True, exist_ok=True)

# Temporary compatibility patch for NumPy ≥2.0 removal of NaN constant
if not hasattr(_np, "NaN"):
    _np.NaN = _np.nan  # type: ignore[attr-defined]

# Ensure project root import works (bots package)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Sanitiser shared by API and local discovery paths
# ---------------------------------------------------------------------------

NULL_BOOL_KEYS = {"dynamic_order_spread", "dynamic_target", "manual_kill_switch"}


def sanitize_base(base_dict: Dict[str, Any], file_stem: str) -> Dict[str, Any]:
    """Mutate & return base_dict in-place applying our sanitation rules."""
    # 1. fill controller_name if blank
    if not base_dict.get("controller_name"):
        base_dict["controller_name"] = file_stem

    original_keys = set(base_dict.keys())

    def _rec(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, (dict, list)):
                    _rec(v)
                else:
                    if v is None and k in NULL_BOOL_KEYS:
                        obj[k] = False
                    elif isinstance(v, str):
                        if (
                            k == "connector_name"
                            or k.endswith("_connector")
                            or k.endswith("connector_name")
                        ) and v.startswith("binance"):
                            obj[k] = "kucoin"
        elif isinstance(obj, list):
            for item in obj:
                _rec(item)

    _rec(base_dict)

    # Remove top-level connector/trading_pair if they were not part of the
    # original payload (avoid "extra inputs not permitted" for configs like
    # Arbitrage, XEMM, QGA that store these inside nested objects only).
    if "connector_name" not in original_keys:
        base_dict.pop("connector_name", None)
    if "trading_pair" not in original_keys:
        base_dict.pop("trading_pair", None)

    return base_dict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cls_is_config(obj: Any) -> bool:
    return inspect.isclass(obj) and hasattr(obj, "controller_name") and hasattr(obj, "model_fields")


def defaults_from_model(model_cls) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for fname, field in model_cls.model_fields.items():  # type: ignore[attr-defined]
        out[fname] = field.default if field.default is not inspect._empty else None
    return out

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def discover_controllers() -> List[Dict[str, Any]]:
    controllers_pkg = "bots.controllers"
    discovered: List[Dict[str, Any]] = []
    for mod_info in pkgutil.walk_packages([str(ROOT / "bots" / "controllers")], prefix=f"{controllers_pkg}."):
        try:
            mod = importlib.import_module(mod_info.name)
        except Exception as exc:
            print(f"❌ import {mod_info.name}: {exc}")
            continue
        for obj in vars(mod).values():
            if cls_is_config(obj):
                discovered.append({"cls": obj, "module": mod_info.name})
    return discovered


def build_yaml(cfg_cls) -> str:
    base = defaults_from_model(cfg_cls)
    # Remove Pydantic internals
    base.pop("__pydantic_validator__", None)

    base = sanitize_base(base, getattr(cfg_cls, "controller_name", cfg_cls.__name__))

    stub = {
        "meta": {
            "start": "2024-03-11",
            "end": "2024-03-13",
            "resolution": "3m",
            "fee": 0.001,
        },
        "base": base,
        "sweep": {},
        "grid": {},
    }
    return yaml.safe_dump(stub, sort_keys=False, default_flow_style=False)


def diff(existing: str, new: str, path_old: Path, path_new: Path):
    d = difflib.unified_diff(
        existing.splitlines(),
        new.splitlines(),
        fromfile=str(path_old),
        tofile=str(path_new),
        lineterm="",
    )
    for line in d:
        print(line)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show-diff", action="store_true", help="Print a unified diff when curated sweep differs.")
    args = ap.parse_args()
    # ------------------------------------------------------------------

    created = updated = skipped = 0

    emitted_names: Dict[str, int] = {}
    try:
        USERNAME = os.getenv("HB_USER", "admin")
        PASSWORD = os.getenv("HB_PASS", "admin")
        base_url = "http://localhost:8000"

        # 1) Discover controller files
        r = requests.get(f"{base_url}/list-controllers", auth=(USERNAME, PASSWORD), timeout=10)
        r.raise_for_status()
        listing: Dict[str, List[str]] = r.json()

        total = sum(len(v) for v in listing.values())
        print(f"🛰  Fetched controller list (total {total}) via /list-controllers")

        for controller_type, files in listing.items():
            for fname in files:
                name = fname.replace(".py", "")
                if name in emitted_names:
                    emitted_names[name] += 1
                    name_unique = f"{name}_v{emitted_names[name]}"
                else:
                    emitted_names[name] = 1
                    name_unique = name

                # 2) Fetch default config per controller
                url = f"{base_url}/controller-config-pydantic/{controller_type}/{fname}"
                try:
                    resp = requests.get(url, auth=(USERNAME, PASSWORD), timeout=10)
                    resp.raise_for_status()
                    base = resp.json()
                    if name_unique != name:
                        base["controller_name"] = name_unique
                except Exception as exc_inner:
                    print(f"❌ fetch {fname}: {exc_inner}")
                    continue

                base = sanitize_base(base, name_unique)
                yaml_text = yaml.safe_dump({
                    "meta": {
                        "start": "2024-03-11",
                        "end": "2024-03-13",
                        "resolution": "3m",
                        "fee": 0.001,
                    },
                    "base": base,
                    "sweep": {},
                    "grid": {},
                }, sort_keys=False, default_flow_style=False)

                curated_path = SWEEP_DIR / f"{name_unique}_sweep.yml"
                gen_path = GEN_DIR / f"{name_unique}_sweep.yml"

                if curated_path.exists():
                    existing = curated_path.read_text()
                    if existing.strip() == yaml_text.strip():
                        skipped += 1
                        continue
                    gen_path.write_text(yaml_text)
                    print(f"🔄 Updated stub → {gen_path.relative_to(ROOT)} (diff vs curated)")
                    if args.show_diff:
                        print("---")
                        diff(existing, yaml_text, curated_path, gen_path)
                    updated += 1
                else:
                    gen_path.write_text(yaml_text)
                    print(f"✅ Generated stub → {gen_path.relative_to(ROOT)}")
                    created += 1

    except Exception as exc:
        print(f"⚠️  Could not fetch from API ({exc}) – aborting scaffold (no local import fallback).")
        return

    print("\nSummary:", f"{created} new, {updated} diffs, {skipped} unchanged.")


if __name__ == "__main__":
    main() 