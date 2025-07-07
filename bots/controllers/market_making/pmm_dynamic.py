from decimal import Decimal
from typing import List

import pandas_ta as ta  # noqa: F401
import pandas as pd
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class PMMDynamicControllerConfig(MarketMakingControllerConfigBase):
    controller_name: str = "pmm_dynamic"
    candles_config: List[CandlesConfig] = []
    buy_spreads: List[float] = Field(
        default="1,2,4",
        json_schema_extra={
            "prompt": "Enter a comma-separated list of buy spreads measured in units of volatility(e.g., '1, 2'): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    sell_spreads: List[float] = Field(
        default="1,2,4",
        json_schema_extra={
            "prompt": "Enter a comma-separated list of sell spreads measured in units of volatility(e.g., '1, 2'): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    candles_connector: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the connector for the candles data, leave empty to use the same exchange as the connector: ",
            "prompt_on_new": True})
    candles_trading_pair: str = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trading pair for the candles data, leave empty to use the same trading pair as the connector: ",
            "prompt_on_new": True})
    interval: str = Field(
        default="3m",
        json_schema_extra={
            "prompt": "Enter the candle interval (e.g., 1m, 5m, 1h, 1d): ",
            "prompt_on_new": True})
    macd_fast: int = Field(
        default=21,
        json_schema_extra={"prompt": "Enter the MACD fast period: ", "prompt_on_new": True})
    macd_slow: int = Field(
        default=42,
        json_schema_extra={"prompt": "Enter the MACD slow period: ", "prompt_on_new": True})
    macd_signal: int = Field(
        default=9,
        json_schema_extra={"prompt": "Enter the MACD signal period: ", "prompt_on_new": True})
    natr_length: int = Field(
        default=14,
        json_schema_extra={"prompt": "Enter the NATR length: ", "prompt_on_new": True})

    @field_validator("candles_connector", mode="before")
    @classmethod
    def set_candles_connector(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("connector_name")
        return v

    @field_validator("candles_trading_pair", mode="before")
    @classmethod
    def set_candles_trading_pair(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("trading_pair")
        return v


class PMMDynamicController(MarketMakingControllerBase):
    """
    This is a dynamic version of the PMM controller.It uses the MACD to shift the mid-price and the NATR
    to make the spreads dynamic. It also uses the Triple Barrier Strategy to manage the risk.
    """
    def __init__(self, config: PMMDynamicControllerConfig, *args, **kwargs):
        self.config = config
        # Ensure candle source defaults to the main connector/pair, warn user if missing.
        import warnings
        if not self.config.candles_connector:
            warnings.warn(
                "candles_connector missing in config; defaulting to connector_name",
                RuntimeWarning,
            )
            self.config.candles_connector = self.config.connector_name
        if not self.config.candles_trading_pair:
            warnings.warn(
                "candles_trading_pair missing in config; defaulting to trading_pair",
                RuntimeWarning,
            )
            self.config.candles_trading_pair = self.config.trading_pair

        # Restore full window size (no artificial 100-row cap).
        base_window = max(config.macd_slow, config.macd_fast, config.macd_signal, config.natr_length)
        self.max_records = base_window + 100
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)

    async def update_processed_data(self):
        """Compute reference price & spread multiplier with robust fallbacks."""
        try:
            candles = self.market_data_provider.get_candles_df(
                connector_name=self.config.candles_connector,
                trading_pair=self.config.candles_trading_pair,
                interval=self.config.interval,
                max_records=self.max_records,
            )

            if candles is None or candles.empty or len(candles) < self.config.macd_slow:
                raise ValueError("Insufficient candle data")

            # Clean duplicates
            candles = candles[~candles.index.duplicated(keep="last")]

            # Indicators
            natr = ta.natr(candles["high"], candles["low"], candles["close"], length=self.config.natr_length) / 100
            macd_output = ta.macd(
                candles["close"],
                fast=self.config.macd_fast,
                slow=self.config.macd_slow,
                signal=self.config.macd_signal,
            )
            macd_col = f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"
            macdh_col = f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"

            macd = macd_output[macd_col]
            macd_signal = -(macd - macd.mean()) / macd.std() if macd.std() != 0 else macd * 0
            macdh = macd_output[macdh_col]
            macdh_signal = macdh.apply(lambda x: 1 if x > 0 else -1)

            max_price_shift = natr / 2
            price_multiplier = ((0.5 * macd_signal + 0.5 * macdh_signal) * max_price_shift).iloc[-1]

            candles["spread_multiplier"] = natr
            candles["reference_price"] = candles["close"] * (1 + price_multiplier)

            self.processed_data = {
                "reference_price": Decimal(str(candles["reference_price"].iloc[-1])),
                "spread_multiplier": Decimal(str(candles["spread_multiplier"].iloc[-1])),
                "features": candles,
            }
        except Exception as e:
            # Surface a hard failure so users fix candle data rather than silently degrading
            msg = (
                f"pmm_dynamic.update_processed_data failed – candle data unavailable or malformed: {e}. "
                "Ensure candles_config includes start_time/end_time matching the backtest window, "
                "and that the CandlesFactory has access to historical data."
            )
            # Log and raise to abort backtest clearly
            try:
                self.logger().error(msg)
            except Exception:
                pass
            raise RuntimeError(msg) from e

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
