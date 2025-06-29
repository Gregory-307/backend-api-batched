import logging
import traceback
from typing import Dict, Union
import math

from fastapi import APIRouter
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from pydantic import BaseModel

from config import CONTROLLERS_MODULE, CONTROLLERS_PATH

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
        logging.info(f"RUNNING BACKTEST WITH CONFIG: {controller_config}")
        backtesting_results = await backtesting_engine.run_backtesting(
            controller_config=controller_config, trade_cost=backtesting_config.trade_cost,
            start=int(backtesting_config.start_time), end=int(backtesting_config.end_time),
            backtesting_resolution=backtesting_config.backtesting_resolution)
        processed_data = backtesting_results["processed_data"]["features"].fillna(0)
        executors_info = [e.to_dict() for e in backtesting_results["executors"]]
        backtesting_results["processed_data"] = processed_data.to_dict()
        results = backtesting_results["results"]
        results["sharpe_ratio"] = results.get("sharpe_ratio", 0) or 0
        # replace any NaN or infinite values that break JSON serialization
        for k, v in list(results.items()):
            if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                results[k] = 0
        return {
            "executors": executors_info,
            "processed_data": backtesting_results["processed_data"],
            "results": backtesting_results["results"],
        }
    except Exception as e:
        # Log the full exception traceback to the server logs
        logging.error("Backtesting endpoint failed with an exception:", exc_info=True)
        # Return a JSON response including the traceback for easier debugging from the client
        return {
            "error": f"An exception occurred during backtesting: {str(e)}",
            "traceback": traceback.format_exc().split('\\n')
        }
