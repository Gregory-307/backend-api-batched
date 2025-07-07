from __future__ import annotations

"""utils.candles_cache – Simple Parquet disk cache for Hummingbot candle fetches

This module monkey-patches ``hummingbot.data_feed.candles_feed.candles_factory.CandlesFactory``
so that repeated calls to ``get_candles_df`` are first served from a local Parquet file
on disk.  It significantly reduces API rate-limit errors when running large back-testing
sweeps.

The patch is **idempotent** – importing this module multiple times is safe.
"""

from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
import asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("data/candles_cache")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _safe_filename(text: str) -> str:
    """Make *text* safe to use as part of a filename (very naive)."""
    for ch in "/\\ ":
        text = text.replace(ch, "-")
    return text


# ---------------------------------------------------------------------------
# Main patching logic
# ---------------------------------------------------------------------------

def _build_cache_key(connector: str, trading_pair: str, interval: str) -> Path:
    """Return the Parquet cache filepath for the given parameters."""
    stem = f"{_safe_filename(connector)}__{_safe_filename(trading_pair)}__{interval}.parquet"
    return _CACHE_DIR / stem


def _merge_and_save(df_existing: pd.DataFrame, df_new: pd.DataFrame, path: Path) -> None:
    """Merge *df_new* into *df_existing*, de-duplicate, sort, and write back to *path*."""
    df_combined = (
        pd.concat([df_existing, df_new]) if not df_existing.empty else df_new
    )
    # De-duplicate by index (timestamp) then sort
    df_combined = df_combined[~df_combined.index.duplicated(keep="last")].sort_index()
    # Persist (use fast compression if available)
    try:
        df_combined.to_parquet(path, compression="zstd")  # pyarrow backend preferred
    except Exception:
        try:
            # Fallback to default engine/compression
            df_combined.to_parquet(path)
        except Exception:
            # No Parquet engine available – skip persistence (cache miss still fine)
            return


# noinspection PyProtectedMember

def _patch_candles_factory() -> None:
    """Monkey-patch ``CandlesFactory.get_candles_df`` once."""
    try:
        from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory  # pylint: disable=import-error
    except ImportError:  # pragma: no cover – Hummingbot not installed
        return

    # If already patched, bail early
    if getattr(CandlesFactory, "_hb_cached", False):
        return

    # Only patch if the expected function exists (API differences between HB versions)
    if not hasattr(CandlesFactory, "get_candles_df"):
        # Newer Hummingbot versions expose candle retrieval via a different API.
        # Skip patch to avoid breaking the app.
        return

    original_fn: Callable[..., Any] = CandlesFactory.get_candles_df  # type: ignore[attr-defined]

    @wraps(original_fn)
    def cached_get_candles_df(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        """Wrapper that adds a disk cache layer around the original method."""
        # -------------------------------------------------------------------
        # 1. Introspect args / kwargs – be tolerant to positional or keyword use
        # -------------------------------------------------------------------
        connector: Optional[str] = kwargs.get("connector_name") or (
            args[0] if len(args) > 0 else None  # type: ignore[assignment]
        )
        trading_pair: Optional[str] = kwargs.get("trading_pair") or (
            args[1] if len(args) > 1 else None  # type: ignore[assignment]
        )
        interval: Optional[str] = kwargs.get("interval") or (
            args[2] if len(args) > 2 else None  # type: ignore[assignment]
        )
        max_records: Optional[int] = kwargs.get("max_records")

        # Guard – if any of the essentials are missing, skip cache layer
        if connector is None or trading_pair is None or interval is None:
            return original_fn(self, *args, **kwargs)

        cache_path = _build_cache_key(connector, trading_pair, interval)

        # -------------------------------------------------------------------
        # 2. Try to serve request fully from cache
        # -------------------------------------------------------------------
        df_cached: Optional[pd.DataFrame] = None
        if cache_path.exists():
            try:
                df_cached = pd.read_parquet(cache_path)
                # Ensure index is unique & sorted
                df_cached = (
                    df_cached[~df_cached.index.duplicated(keep="last")].sort_index()
                )
            except Exception:
                # Corrupt cache – remove and ignore
                cache_path.unlink(missing_ok=True)
                df_cached = None
        if df_cached is not None and not df_cached.empty:
            # If caller only needs *max_records* and we have enough rows, shortcut
            if max_records is None or len(df_cached) >= max_records:
                return (
                    df_cached.iloc[-max_records:] if max_records else df_cached.copy()
                )

        # -------------------------------------------------------------------
        # 4. Fallback to network / original function (with safety net)
        # -------------------------------------------------------------------
        try:
            df_live = original_fn(self, *args, **kwargs)
            if asyncio.iscoroutine(df_live):
                try:
                    loop = asyncio.get_running_loop()
                    df_live = loop.run_until_complete(df_live)  # type: ignore[misc]
                except RuntimeError:
                    df_live = asyncio.run(df_live)  # type: ignore[func-returns-value]
        except Exception:
            # Network or provider error – fallback to cache if we have anything
            if df_cached is not None and not df_cached.empty:
                return df_cached.iloc[-max_records:] if max_records else df_cached.copy()
            raise

        # If provider returned None, but we have cache, serve it instead
        if df_live is None:
            if df_cached is not None and not df_cached.empty:
                return df_cached.iloc[-max_records:] if max_records else df_cached.copy()
            return df_live  # propagate None if absolutely nothing available

        try:
            if df_cached is None:
                _merge_and_save(pd.DataFrame(), df_live, cache_path)
            else:
                _merge_and_save(df_cached, df_live, cache_path)
        except Exception:  # pragma: no cover – cache failures must not break caller
            pass
        return df_live

    # Inject the patched method
    CandlesFactory.get_candles_df = cached_get_candles_df  # type: ignore[assignment]
    CandlesFactory._hb_cached = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Patch BacktestingDataProvider (primary target used during backtests)
# ---------------------------------------------------------------------------

def _patch_backtesting_data_provider() -> None:
    """Monkey-patch ``BacktestingDataProvider.get_candles_df`` (HB >= 2024.2)."""
    try:
        from hummingbot.strategy_v2.backtesting.backtesting_data_provider import (  # type: ignore
            BacktestingDataProvider,
        )
    except Exception:
        return

    # Skip if method already wrapped
    if getattr(BacktestingDataProvider, "_hb_cached", False):
        return

    if not hasattr(BacktestingDataProvider, "get_candles_df"):
        return

    original_fn = BacktestingDataProvider.get_candles_df  # type: ignore[attr-defined]

    @wraps(original_fn)
    def cached_get_candles_df(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        connector = kwargs.get("connector_name") or (args[0] if len(args) > 0 else None)
        trading_pair = kwargs.get("trading_pair") or (args[1] if len(args) > 1 else None)
        interval = kwargs.get("interval") or (args[2] if len(args) > 2 else None)
        max_records: Optional[int] = kwargs.get("max_records")

        if connector is None or trading_pair is None or interval is None:
            return original_fn(self, *args, **kwargs)

        cache_path = _build_cache_key(connector, trading_pair, interval)
        df_cached: Optional[pd.DataFrame] = None
        if cache_path.exists():
            try:
                df_cached = pd.read_parquet(cache_path)
                df_cached = df_cached[~df_cached.index.duplicated(keep="last")].sort_index()
            except Exception:
                cache_path.unlink(missing_ok=True)
                df_cached = None

        if df_cached is not None and not df_cached.empty and (
            max_records is None or len(df_cached) >= max_records
        ):
            return df_cached.iloc[-max_records:] if max_records else df_cached.copy()

        # Fallback to network / original function
        df_live = original_fn(self, *args, **kwargs)
        if df_live is None:
            return df_live
        try:
            if df_cached is None:
                _merge_and_save(pd.DataFrame(), df_live, cache_path)
            else:
                _merge_and_save(df_cached, df_live, cache_path)
        except Exception:
            pass
        return df_live

    BacktestingDataProvider.get_candles_df = cached_get_candles_df  # type: ignore[assignment]
    # Ensure the wrapper is treated as a regular function, not coroutine
    if hasattr(cached_get_candles_df, "__is_coroutine__"):
        try:
            delattr(cached_get_candles_df, "__is_coroutine__")
        except Exception:
            cached_get_candles_df.__is_coroutine__ = False  # type: ignore[attr-defined]
    BacktestingDataProvider._hb_cached = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Execute patches on import
# ---------------------------------------------------------------------------

_patch_backtesting_data_provider()
_patch_candles_factory()


# Expose helper so other modules can *explicitly* trigger patch if imported earlier

def enable_candles_cache():
    """Ensure the CandlesFactory patch is active (idempotent)."""
    _patch_candles_factory() 