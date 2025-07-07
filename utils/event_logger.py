# utils/event_logger.py
"""Lightweight event logger that stores rows in-memory during one back-test
and writes them to CSV/JSON when requested.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json

import pandas as pd


class BTEventLogger:
    """Thread-local store for event rows (so concurrent back-tests don't mix logs)."""

    _events: list[Dict[str, Any]] | None = None

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    @classmethod
    def add(cls, **row: Any):
        if cls._events is None:
            cls._events = []
        cls._events.append(row)

    @classmethod
    def rows(cls) -> List[Dict[str, Any]]:
        return cls._events or []

    @classmethod
    def clear(cls):
        cls._events = []

    @classmethod
    def dump(cls, out_csv: Path):
        if not cls.rows():
            return None
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(cls.rows())
        df.to_csv(out_csv, index=False, float_format='%.8f')
        with out_csv.with_suffix(".json").open("w") as fp:
            json.dump(cls.rows(), fp, indent=2, default=str)
        return out_csv 