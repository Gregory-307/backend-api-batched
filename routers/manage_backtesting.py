import logging
import traceback
from typing import Dict, Union
import math
import os

from fastapi import APIRouter, HTTPException
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from pydantic import BaseModel

from config import CONTROLLERS_MODULE, CONTROLLERS_PATH
import utils.candles_cache  # Activate Parquet cache for candle data

router = APIRouter(tags=["Market Backtesting"])
candles_factory = CandlesFactory()
backtesting_engine = BacktestingEngineBase()

# (Disabled) in-memory candle cache attachment removed due to incompatibility issues

# --- Monkey-patch to make summarize_results robust when no trades/positions ---
_orig_summarize = BacktestingEngineBase.summarize_results


@staticmethod
def _safe_summarize_results(executors_info, total_amount_quote: float = 1000):  # type: ignore
    """Wrap the original summarize_results to avoid IndexError when there are no positions."""
    if not executors_info:
        return {"note": "no trades", "trades": 0}
    try:
        return _orig_summarize(executors_info, total_amount_quote)  # type: ignore[arg-type]
    except (IndexError, KeyError):
        # Upstream code fails when the positions DF is empty.
        return {"note": "no positions", "trades": 0}


# Inject the patched version as the class staticmethod
BacktestingEngineBase.summarize_results = staticmethod(_safe_summarize_results)  # type: ignore[attr-defined]


class BacktestingConfig(BaseModel):
    start_time: int = 1672542000  # 2023-01-01 00:00:00
    end_time: int = 1672628400  # 2023-01-01 23:59:00
    backtesting_resolution: str = "1m"
    trade_cost: float = 0.0006
    config: Union[Dict, str]


@router.post("/run-backtesting")
async def run_backtesting(backtesting_config: BacktestingConfig):
    print("RUNNING BACKTESTING")
    print("BACKTESTING CONFIG: ", backtesting_config)
    try:
        if isinstance(backtesting_config.config, str):
            controller_config = backtesting_engine.get_controller_config_instance_from_yml(
                config_path=backtesting_config.config,
                controllers_conf_dir_path=CONTROLLERS_PATH,
                controllers_module=CONTROLLERS_MODULE
            )
        else:
            controller_config = backtesting_engine.get_controller_config_instance_from_dict(
                config_data=backtesting_config.config,
                controllers_module=CONTROLLERS_MODULE
            )
        # ------------------------------------------------------------------
        # Instance-level fallbacks – do NOT monkey-patch the class, just fill
        # missing values on this config object so downstream code sees a real
        # string instead of None.  This avoids accidentally shadowing legit
        # fields defined in subclasses.
        # ------------------------------------------------------------------
        if getattr(controller_config, "connector_name", None) in (None, ""):
            if hasattr(controller_config, "maker_connector"):
                controller_config.connector_name = getattr(controller_config, "maker_connector")
            else:
                ep1 = getattr(controller_config, "exchange_pair_1", None)
                if ep1 is not None:
                    controller_config.connector_name = getattr(ep1, "connector_name", None)

        if getattr(controller_config, "trading_pair", None) in (None, ""):
            if hasattr(controller_config, "maker_trading_pair"):
                controller_config.trading_pair = getattr(controller_config, "maker_trading_pair")
            else:
                ep1 = getattr(controller_config, "exchange_pair_1", None)
                if ep1 is not None:
                    controller_config.trading_pair = getattr(ep1, "trading_pair", None)

        logging.info(f"RUNNING BACKTEST WITH CONFIG: {controller_config}")
        backtesting_results = await backtesting_engine.run_backtesting(
            controller_config=controller_config, trade_cost=backtesting_config.trade_cost,
            start=int(backtesting_config.start_time), end=int(backtesting_config.end_time),
            backtesting_resolution=backtesting_config.backtesting_resolution)
        
        # ------------------------------------------------------------------
        # Normalise & validate `processed_data` ----------------------------
        raw_proc = backtesting_results.get("processed_data", {})
        try:
            import pandas as pd

            def _to_df(raw):
                """Robust conversion of *processed_data* payload to DataFrame without
                triggering Pandas' ambiguous truth-value check.
                """

                # Case 1 – already a DataFrame ------------------------------------------------
                if isinstance(raw, pd.DataFrame):
                    return raw

                # Case 2 – dict with a nested "features" key --------------------------------
                if isinstance(raw, dict) and "features" in raw:
                    feat = raw["features"]
                    if isinstance(feat, pd.DataFrame):
                        return feat
                    # `feat` could be dict-of-lists or list-of-dicts – DataFrame handles both.
                    return pd.DataFrame(feat if feat is not None else {})

                # Case 3 – flat dict that should be convertible ------------------------------
                if isinstance(raw, dict):
                    return pd.DataFrame(raw)

                raise TypeError(f"Unexpected processed_data type: {type(raw)}")

            processed_df = _to_df(raw_proc)

            # Guard: non-empty index & at least 1 column
            if processed_df.empty:
                raise ValueError("processed_data is empty after normalisation")

            processed_df = processed_df.fillna(0)
            processed_data = processed_df
            backtesting_results["processed_data"] = processed_df.to_dict()
        except Exception as exc:
            logging.exception("processed_data parsing failed – rejecting request")
            raise HTTPException(status_code=422, detail=f"Invalid processed_data: {exc}")

        executors_info = [e.to_dict() for e in backtesting_results.get("executors", [])]
        results = backtesting_results["results"]
        
        # Ensure downstream testers see a 'trades' key (✅ when >0, ⚠️ when 0)
        if "trades" not in results:
            # Total executors with a filled position is the best proxy for trade count
            results["trades"] = results.get("total_executors_with_position", 0)

        results["sharpe_ratio"] = results.get("sharpe_ratio", 0) or 0
        # replace any NaN or infinite values that break JSON serialization
        for k, v in list(results.items()):
            if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                results[k] = 0

        # Prepare base response_payload early so subsequent sections can append to it
        response_payload = {
            "executors": executors_info,
            "processed_data": backtesting_results["processed_data"],
            "results": backtesting_results["results"],
            "config": controller_config.dict() if hasattr(controller_config, "dict") else {},
        }

        # Derive a stable filename label early so both event CSV & packet use the same value
        if isinstance(backtesting_config.config, dict):
            _cfg_dict = backtesting_config.config
        else:
            _cfg_dict = {}

        _label_src = _cfg_dict.get("label") or _cfg_dict.get("id") or _cfg_dict.get("controller_name")
        if not _label_src:
            from time import time as _time
            _label_src = f"run_{int(_time())}"

        safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(_label_src))

        # ------------------------------------------------------------------
        # Extra logging – record every quote price at submission time so we can
        # later verify spread calculations.  We print BUY vs SELL along with
        # timestamp (ISO) and raw epoch to ease spreadsheet filtering.
        try:
            from datetime import datetime, timezone

            for exe in executors_info:
                ts = exe.get("timestamp") or exe.get("entry_timestamp")
                if ts is None:
                    continue
                # Convert to readable ISO string in UTC
                iso = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds")
                side_val = exe.get("side") or (exe.get("config", {}).get("side"))
                side = "BUY" if str(side_val) in ("1", "buy", "BUY") else "SELL"
                price = exe.get("entry_price") or exe.get("config", {}).get("entry_price")
                logging.info(
                    "QUOTE_SUBMITTED | %s | %s | price=%.8f",
                    iso,
                    side,
                    price if price is not None else float('nan'),
                )
        except Exception as log_exc:  # pragma: no cover
            logging.warning("Order logging failed: %s", log_exc)

        # ------------------------------------------------------------------
        # Build developer-friendly event log (CREATE, FILL?, CLOSE) ---------
        from utils.event_logger import BTEventLogger
        BTEventLogger.clear()

        # Map candle timestamp → OHLC row (DataFrame index expected to be timestamp)
        try:
            import pandas as pd

            # 'processed_data' variable above holds the DataFrame we filled (even though
            # a dict version was stored back in backtesting_results).  Re-use it to avoid
            # orientation confusion.
            feat_df = processed_data if isinstance(processed_data, pd.DataFrame) else pd.DataFrame(processed_data)

            # Ensure index is numeric unix ts (seconds)
            try:
                feat_df.index = feat_df.index.astype(float).astype(int)
            except Exception:
                pass
        except Exception:
            feat_df = None

        for exe in executors_info:
            ts = int(exe.get("timestamp") or exe.get("entry_timestamp", 0))
            side_val = exe.get("side") or exe.get("config", {}).get("side")
            side = "BUY" if str(side_val) in ("1", "buy", "BUY") else "SELL"

            candle = feat_df.loc[ts] if feat_df is not None and ts in feat_df.index else {}

            # Robust entry price extraction ---------------------------------
            entry_px = exe.get("entry_price")
            if entry_px is None:
                entry_px = exe.get("config", {}).get("entry_price")

            # CREATE event (when order was submitted)
            BTEventLogger.add(
                timestamp=ts,
                event_type="CREATE",
                strategy_name=exe.get("config", {}).get("controller_id", "main"),
                candle_open_time=candle.get("open_time"),
                candle_close_time=candle.get("close_time"),
                candle_open=candle.get("open"),
                candle_high=candle.get("high"),
                candle_low=candle.get("low"),
                candle_close=candle.get("close"),
                # Compute mid-price robustly without relying on truthiness of a Series
                candle_mid_price=(
                    ((candle.get("high") + candle.get("low")) / 2)
                    if candle is not None and candle.get("high") is not None and candle.get("low") is not None
                    else None
                ),
                reference_price=float(candle.get("reference_price")) if candle is not None and candle.get("reference_price") is not None else None,
                order_id=exe.get("config", {}).get("level_id"),
                trade_type=side,
                created_price=float(entry_px) if entry_px is not None else None,
                created_size=exe.get("config", {}).get("amount"),
            )

            # FILL event – if executor has filled_amount_quote > 0
            if exe.get("filled_amount_quote", 0):
                BTEventLogger.add(
                    timestamp=ts,  # approximation
                    event_type="FILL",
                    strategy_name=exe.get("config", {}).get("controller_id", "main"),
                    order_id=exe.get("config", {}).get("level_id"),
                    position_id=exe.get("id"),
                    trade_type=side,
                    fill_price=float(entry_px) if entry_px is not None else None,
                    amount_filled=exe.get("filled_amount_quote"),
                )

            # CLOSE event if closed
            close_ts = exe.get("close_timestamp")
            if close_ts:
                BTEventLogger.add(
                    timestamp=int(close_ts),
                    event_type="CLOSE",
                    strategy_name=exe.get("config", {}).get("controller_id", "main"),
                    order_id=exe.get("config", {}).get("level_id"),
                    position_id=exe.get("id"),
                    trade_type=side,
                    entry_price=exe.get("entry_price"),
                    close_price=exe.get("custom_info", {}).get("close_price", exe.get("exit_price")),
                    closing_reason=exe.get("close_type"),
                    pnl_quote=exe.get("net_pnl_quote"),
                    pnl_percent=exe.get("net_pnl_pct"),
                )

        try:
            from pathlib import Path

            ev_dir = Path("results/event_logs")
            ev_dir.mkdir(parents=True, exist_ok=True)
            csv_out = ev_dir / f"{safe_label}_events.csv"
            BTEventLogger.dump(csv_out)
            response_payload["event_log_csv"] = str(csv_out)
        except Exception as exc:
            logging.warning(f"Could not save event CSV: {exc}")

        # Persist detail packet for dashboard visualisations -----------------
        if os.getenv("HB_SAVE_PACKET", "0") == "1":
            try:
                from pathlib import Path
                import json

                DETAILS_DIR = Path(os.getenv("HB_DETAIL_DIR", "results/detail_packets"))
                DETAILS_DIR.mkdir(parents=True, exist_ok=True)
                out_path = DETAILS_DIR / f"{safe_label}.json"
                with out_path.open("w") as fp:
                    json.dump(response_payload, fp, indent=2)
            except Exception as exc:
                logging.warning(f"Could not save detail packet: {exc}")

        # If the model *totally lacks* these attributes (not even defined as
        # optional fields) inject read-only properties so generic helper code
        # in the back-testing engine can still access them.  This happens for
        # Arbitrage / XEMM / QGA configs.
        cfg_cls = type(controller_config)

        if "connector_name" not in getattr(cfg_cls, "model_fields", {}):
            if not hasattr(cfg_cls, "connector_name"):
                setattr(cfg_cls, "connector_name", property(lambda self: getattr(getattr(self, "exchange_pair_1", None), "connector_name", None)))

        if "trading_pair" not in getattr(cfg_cls, "model_fields", {}):
            if not hasattr(cfg_cls, "trading_pair"):
                setattr(cfg_cls, "trading_pair", property(lambda self: getattr(getattr(self, "exchange_pair_1", None), "trading_pair", None)))

        return response_payload
    except Exception as e:
        # Log the full exception traceback to the server logs
        logging.error("Backtesting endpoint failed with an exception:", exc_info=True)
        # Return a JSON response including the traceback for easier debugging from the client
        return {
            "error": f"An exception occurred during backtesting: {str(e)}",
            "traceback": traceback.format_exc().split('\\n')
        }
