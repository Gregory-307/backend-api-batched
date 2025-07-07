"""Index helper for detail packets to avoid loading every JSON on start-up."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import json

BASE_DIR = Path("results/detail_packets")

def _index_path(base: Path) -> Path:
    return base / "_index.csv"

COLUMNS = [
    "label",
    "file_path",
    "size",
    "mtime",
    "event_log_csv",
    "valid",
    "note",
]

def load_index(base: Path = BASE_DIR) -> pd.DataFrame:
    """Load an index CSV if present, otherwise build a minimal index from
    any JSON files in *base*.

    A missing index currently happens for fresh runs because the batch
    tester (C_multi_yml_to_backtests) writes individual packet files but
    does not yet generate the consolidated *\_index.csv*. Building a
    fallback on-the-fly prevents the dashboard from showing the misleading
    "No index file found" warning when packets are actually available.
    """

    path = _index_path(base)
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            # If the file is corrupt we fall back to rebuilding below.
            pass

    # --- Fallback: scan directory for *.json packets --------------------
    if not base.is_dir():
        return pd.DataFrame(columns=COLUMNS)

    records = []
    for p in base.glob("*.json"):
        if p.name.startswith("_index"):
            continue
        try:
            size = p.stat().st_size
            mtime = p.stat().st_mtime
        except OSError:
            size = 0
            mtime = 0
        records.append([
            p.stem,            # label
            str(p),            # file_path
            size,              # size (bytes)
            mtime,             # mtime (unix ts)
            "",               # event_log_csv (unknown)
            1,                 # valid (assume OK)
            "auto",           # note
        ])

    df = pd.DataFrame(records, columns=COLUMNS)

    # Persist so that next load is fast (best-effort).
    try:
        if records:
            base.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False)
    except Exception:
        # Non-fatal – keep in-memory df.
        pass

    return df


def mark(label: str, ok: bool, note: str = "", base: Path = BASE_DIR) -> None:
    df = load_index(base)
    if label in df.label.values:
        df.loc[df.label == label, ["valid", "note"]] = [int(ok), note]
    else:
        # fallback if row not present
        df = pd.concat([
            df,
            pd.DataFrame([[label, str(base / f"{label}.json"), 0, 0, "", int(ok), note]], columns=COLUMNS),
        ])
    _index_path(base).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(_index_path(base), index=False)


def load_packet(label: str, base: Path = BASE_DIR):
    p = base / f"{label}.json"
    if not p.is_file():
        mark(label, False, "missing packet", base)
        raise FileNotFoundError(p)
    try:
        return json.loads(p.read_text())
    except Exception as exc:
        mark(label, False, str(exc), base)
        raise 