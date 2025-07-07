from decimal import Decimal
from typing import List, Dict, Optional

import pandas_ta as ta
import pandas as pd
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class PMMDynamic2ControllerConfig(MarketMakingControllerConfigBase):
    """
    A simplified and robust configuration for an alternate PMM Dynamic controller.
    This variant adds order_amount and MACD-driven adjustment factors, hence we
    expose it under a distinct name to avoid clashing with the upstream
    pmm_dynamic implementation.
    """
    controller_name: str = "pmm_dynamic_2"
    
    # --- Market Data ---
    candles_connector: str = Field(default=None, json_schema_extra={"prompt": "Enter connector for candles"})
    candles_trading_pair: str = Field(default=None, json_schema_extra={"prompt": "Enter trading pair for candles"})
    interval: str = Field(default="1m", json_schema_extra={"prompt": "Enter candle interval"})

    # --- Spreads and Order Amounts ---
    buy_spreads: List[float] = Field(default=[0.01, 0.02], json_schema_extra={"prompt": "Enter buy spreads (e.g., 0.01,0.02)"})
    sell_spreads: List[float] = Field(default=[0.01, 0.02], json_schema_extra={"prompt": "Enter sell spreads (e.g., 0.01,0.02)"})
    order_amount: Decimal = Field(default=Decimal("10"), json_schema_extra={"prompt": "Enter order amount"})

    # --- MACD Indicator ---
    macd_fast: int = Field(default=12, json_schema_extra={"prompt": "Enter MACD fast period"})
    macd_slow: int = Field(default=26, json_schema_extra={"prompt": "Enter MACD slow period"})
    macd_signal: int = Field(default=9, json_schema_extra={"prompt": "Enter MACD signal period"})
    
    # --- Dynamic Adjustments ---
    price_adjustment_factor: Decimal = Field(default=Decimal("0.0001"), json_schema_extra={"prompt": "Enter price adjustment factor based on MACD"})
    spread_multiplier_factor: Decimal = Field(default=Decimal("0.1"), json_schema_extra={"prompt": "Enter spread multiplier factor"})
    max_spread_multiplier: Decimal = Field(default=Decimal("2.0"), json_schema_extra={"prompt": "Enter maximum spread multiplier"})
    min_spread_multiplier: Decimal = Field(default=Decimal("0.5"), json_schema_extra={"prompt": "Enter minimum spread multiplier"})
    
    candles_config: List[CandlesConfig] = []

    @field_validator("buy_spreads", "sell_spreads", mode="before")
    @classmethod
    def parse_spreads(cls, v):
        """Parse spreads from string or return as list"""
        if isinstance(v, str):
            if v == "":
                return [0.01, 0.02]  # Default spreads
            return [float(x.strip()) for x in v.split(',')]
        elif isinstance(v, list):
            return [float(x) for x in v]
        return v

    @field_validator("candles_connector", "candles_trading_pair", mode="before")
    @classmethod
    def set_default_from_main_config(cls, v: str, info: ValidationInfo) -> str:
        # Helper to default candle config to the main strategy config
        if v is None:
            field_name = info.field_name.replace("candles_", "")
            return info.data.get(field_name)
        return v


class PMMDynamic2Controller(MarketMakingControllerBase):
    """
    A simplified and robust PMM Dynamic controller focusing on stability.
    It uses MACD to adjust the reference price and spread multipliers.
    """
    def __init__(self, config: PMMDynamic2ControllerConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
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

        base_window = config.macd_slow
        self.max_records = base_window + 100
        
        if not self.config.candles_config:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]

    async def update_processed_data(self):
        """
        Fetches candle data, calculates a reference price based on the mid-price,
        and generates a signal based on the MACD histogram.
        """
        try:
            candles = self.market_data_provider.get_candles_df(
                connector_name=self.config.candles_connector,
                trading_pair=self.config.candles_trading_pair,
                interval=self.config.interval,
                max_records=self.max_records
            )
            
            # Robustness: Remove duplicates to prevent indexing errors
            candles = candles[~candles.index.duplicated(keep='last')]
            if candles.empty or len(candles) < self.config.macd_slow:
                msg = (
                    "pmm_dynamic_2.update_processed_data: Insufficient candle history. "
                    "Ensure candles_config includes start_time/end_time covering the backtest window."
                )
                try:
                    self.logger().error(msg)
                except Exception:
                    pass
                raise RuntimeError(msg)

            # --- Indicator Calculation ---
            candles.ta.macd(fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal, append=True)
            
            # --- Signal Generation ---
            macd_col = f"MACD_{self.config.macd_fast}{self.config.macd_slow}{self.config.macd_signal}"
            signal_col = f"MACDs_{self.config.macd_fast}{self.config.macd_slow}{self.config.macd_signal}"
            histogram_col = f"MACDh_{self.config.macd_fast}{self.config.macd_slow}{self.config.macd_signal}"
            
            # Get the latest values
            macd_line = candles[macd_col].iloc[-1] if macd_col in candles.columns else 0
            signal_line = candles[signal_col].iloc[-1] if signal_col in candles.columns else 0
            macd_histogram = candles[histogram_col].iloc[-1] if histogram_col in candles.columns else 0
            
            # --- Reference Price with MACD Adjustment ---
            base_price = Decimal(str(candles["close"].iloc[-1]))
            price_adjustment = Decimal(str(macd_histogram)) * self.config.price_adjustment_factor
            reference_price = base_price + (base_price * price_adjustment)
            
            # --- Spread Multiplier based on MACD ---
            spread_multiplier = self.calculate_spread_multiplier(macd_histogram)

            # --- Store Processed Data ---
            self.processed_data = {
                "signal": float(macd_histogram),  # For dashboard compatibility
                "reference_price": reference_price,
                "spread_multiplier": spread_multiplier,
                "macd_histogram": float(macd_histogram),
                "macd_line": float(macd_line),
                "signal_line": float(signal_line),
            }
            
        except Exception as e:
            # Error handling: fallback to order book price
            self.logger().warning(f"Error updating processed data: {e}. Using fallback price.")
            mid_price = self.get_fallback_price()
            self.processed_data = {
                "signal": 0,
                "reference_price": mid_price,
                "spread_multiplier": Decimal("1.0"),
                "macd_histogram": 0,
                "macd_line": 0,
                "signal_line": 0,
            }

    def get_fallback_price(self) -> Decimal:
        """Get fallback price from order book or last traded price"""
        try:
            order_book = self.market_data_provider.get_order_book(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair
            )
            mid_price = order_book.mid_price
            
            if mid_price is None or mid_price.is_nan():
                # Fallback to last trade price if mid-price is not available
                mid_price = self.market_data_provider.get_last_traded_price(
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair
                )
            return Decimal(str(mid_price))
        except Exception:
            return Decimal("100")  # Ultimate fallback

    def calculate_spread_multiplier(self, macd_histogram: float) -> Decimal:
        """Calculate spread multiplier based on MACD histogram"""
        abs_macd = abs(macd_histogram)
        multiplier = Decimal("1.0") + (Decimal(str(abs_macd)) * self.config.spread_multiplier_factor)
        
        # Clamp to min/max bounds
        multiplier = max(self.config.min_spread_multiplier, 
                        min(self.config.max_spread_multiplier, multiplier))
        
        return multiplier

    def get_processed_spreads(self, trade_type: TradeType) -> List[Decimal]:
        """Get spreads adjusted by the spread multiplier"""
        spreads = self.config.buy_spreads if trade_type == TradeType.BUY else self.config.sell_spreads
        multiplier = self.processed_data.get("spread_multiplier", Decimal("1.0"))
        
        return [Decimal(str(spread)) * multiplier for spread in spreads]

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal) -> PositionExecutorConfig:
        """
        Creates a position executor configuration for a specific order level.
        """
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=self.config.order_amount,  # Use fixed order amount
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )

    def to_format_status(self) -> List[str]:
        """Format status for display"""
        lines = []
        if hasattr(self, 'processed_data') and self.processed_data:
            lines.append(f"Reference Price: {self.processed_data.get('reference_price', 'N/A')}")
            lines.append(f"MACD Histogram: {self.processed_data.get('macd_histogram', 'N/A'):.6f}")
            lines.append(f"MACD Line: {self.processed_data.get('macd_line', 'N/A'):.6f}")
            lines.append(f"Signal Line: {self.processed_data.get('signal_line', 'N/A'):.6f}")
            lines.append(f"Spread Multiplier: {self.processed_data.get('spread_multiplier', 'N/A')}")
        return lines