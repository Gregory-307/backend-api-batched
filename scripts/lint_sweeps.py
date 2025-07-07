#!/usr/bin/env python3
"""lint_sweeps.py – quick static sanity-check for *\_sweep.yml files.

Usage
-----
python3 scripts/lint_sweeps.py sweeps  # path(s) passed as argv

Exits non-zero if any sweep file fails to parse or expand via the new
`build_payloads` implementation in *A_yml_to_json.py*.
This prevents broken YAML from reaching CI or other developers.
"""
from __future__ import annotations

import sys, os
from pathlib import Path
from typing import List
import traceback

try:
    import yaml  # type: ignore
except ImportError:
    sys.exit("Install PyYAML: pip install pyyaml")

# Ensure project root is on sys.path so A_yml_to_json can be imported when this script
# is executed from the "scripts" directory.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from A_yml_to_json import build_payloads  # re-use existing logic


def check_file(path: Path) -> List[str]:
    """Return list of error strings (empty list → file OK)."""
    errors: List[str] = []
    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:
        errors.append(f"YAML parse error → {exc}")
        return errors

    base = data.get("base", {})
    grid = data.get("grid", {})
    sweep = data.get("sweep", {})
    meta = data.get("meta", {})
    try:
        _ = build_payloads(base, grid, meta, sweep=sweep)
    except Exception as exc:
        errors.append(f"build_payloads failed → {exc}")
        tb = traceback.format_exc(limit=1)
        errors.append(tb.strip())
    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: lint_sweeps.py <dir-or-file> [...]", file=sys.stderr)
        sys.exit(1)

    targets: List[Path] = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            targets.extend(sorted(p.glob("*_sweep.yml")))
        else:
            targets.append(p)

    has_err = False
    for yml in targets:
        errs = check_file(yml)
        if errs:
            has_err = True
            print(f"❌ {yml}")
            for e in errs:
                print(f"   ↳ {e}")
        else:
            print(f"✅ {yml}")

    if has_err:
        sys.exit(1)


if __name__ == "__main__":
    main() 