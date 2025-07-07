#!/usr/bin/env python3
"""Light-weight smoke test for the codebase.

1. Recursively compiles every *.py file under the project root **in memory** to catch
   syntax errors without touching the filesystem (avoids __pycache__ permission issues).
2. Exits with non-zero status if any file fails to compile, printing a concise report.

Usage
-----
    python scripts/quick_smoke.py

The script is designed to run fast (<1-2 s) so it can be executed before
launching Streamlit on every reload (see `scripts/dev_watch.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Configuration – directories to ignore (version control, large data dumps, etc.)
# ---------------------------------------------------------------------------
EXCLUDE_DIRS = {
    ".git",
    "results",
    "logs",
    "data",
}


def should_skip(path: Path) -> bool:
    """Return True if *path* is located within an excluded directory."""
    parts = set(path.parts)
    return bool(parts & EXCLUDE_DIRS)


def compile_sources(root: Path = Path(".")) -> List[Tuple[Path, Exception]]:
    """Compile every Python file under *root* (depth-first).

    Returns a list of (path, exception) tuples for files that failed to compile.
    """
    errors: List[Tuple[Path, Exception]] = []

    for py_path in root.rglob("*.py"):
        if should_skip(py_path):
            continue
        try:
            source = py_path.read_text(encoding="utf-8")
            compile(source, str(py_path), "exec")  # in-memory compile
        except Exception as exc:  # noqa: BLE001 – we want to catch any exception
            errors.append((py_path, exc))
    return errors


def main() -> None:
    failures = compile_sources()

    if not failures:
        print("✅ Smoke-test passed – all Python files compiled successfully.")
        sys.exit(0)

    # Otherwise, report
    print("❌ Smoke-test failed – syntax errors detected in the following files:\n")
    for path, err in failures:
        print(f"• {path}: {err}")
    print(f"\nTotal failures: {len(failures)}")
    sys.exit(1)


if __name__ == "__main__":
    main() 