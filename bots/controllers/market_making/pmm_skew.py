from decimal import Decimal
from typing import List

from pydantic import Field

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class PMMSkewConfig(MarketMakingControllerConfigBase):
    """PMM variant that skews spreads by a factor (positive = wider sell, tighter buy)."""

    controller_name: str = "pmm_skew"
    skew_factor: float = Field(0.0, description="0 = symmetric. Positive values skew towards selling.")
    # Keep candle feeds empty – we rely only on order-book reference prices.
    candles_config: List[CandlesConfig] = Field(default=[])


class PMMSkewController(MarketMakingControllerBase):
    def __init__(self, config: PMMSkewConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

        # Apply skew by adjusting the spreads in place.
        k = Decimal(str(1 + config.skew_factor))  # >1 widens sells, tightens buys
        if config.buy_spreads:
            config.buy_spreads = [float(Decimal(str(s)) / k) for s in config.buy_spreads]
        if config.sell_spreads:
            config.sell_spreads = [float(Decimal(str(s)) * k) for s in config.sell_spreads]

    # We re-use the executor logic from PMMSimple – only spreads differ.

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