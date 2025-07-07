from __future__ import annotations
from decimal import Decimal
from typing import List, Dict

from pydantic import Field

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import StopExecutorAction, ExecutorAction


class PMMNettingConfig(MarketMakingControllerConfigBase):
    """Configuration for the spread-capture netting strategy."""
    controller_name: str = "pmm_netting"

    candles_config: List[CandlesConfig] = Field(default=[])

    # Extra behaviour flags
    auto_netting: bool = Field(
        default=True,
        description="If true, the controller will automatically net (close) matching long/short executors as soon as both sides are filled.",
        json_schema_extra={"prompt": "Automatically net offsetting positions? (true/false) ", "prompt_on_new": True, "is_updatable": True},
    )
    cancel_opposite_orders_on_fill: bool = Field(
        default=False,
        description="If true, after one side is filled the remaining opposite open orders will be cancelled until netting is complete.",
        json_schema_extra={"prompt": "Cancel opposite maker orders while waiting for netting? (true/false)", "prompt_on_new": True, "is_updatable": True},
    )


class PMMNettingController(MarketMakingControllerBase):
    """Pure-market-maker that immediately nets equal & opposite fills to realise spread profit."""

    # ------------------------------ lifecycle helpers ------------------------------

    def __init__(self, config: PMMNettingConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config: PMMNettingConfig = config
        # Internal queues holding executors waiting for opposite match
        self._unmatched_buys: Dict[str, "ExecutorInfo"] = {}
        self._unmatched_sells: Dict[str, "ExecutorInfo"] = {}

    # ------------------------------ executor factory ------------------------------

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        """Reuse the simple PMM order-size logic."""
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

    # ------------------------------ custom logic ------------------------------

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """Augment parent logic with netting-driven StopExecutorActions."""
        # Baseline actions (refresh / early stop) from parent if they exist
        base_actions: List[ExecutorAction] = []
        if hasattr(super(), "stop_actions_proposal"):
            # Older HB versions may not provide it – guard with hasattr
            base_actions = super().stop_actions_proposal()  # type: ignore

        if not self.config.auto_netting:
            return base_actions

        additional_actions: List[ExecutorAction] = []

        # Build lookup of fresh executors (active & entry filled)
        active_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda e: e.is_active and not e.is_trading and e.filled_amount_quote != 0,
        )

        for exe in active_executors:
            side_dict = self._unmatched_buys if exe.config.side == TradeType.BUY else self._unmatched_sells
            opp_dict = self._unmatched_sells if exe.config.side == TradeType.BUY else self._unmatched_buys

            # Try to find an opposite-side match of equal quote amount (tolerance 1e-9)
            matched_key = None
            for opp_id, opp_exe in opp_dict.items():
                if abs(opp_exe.filled_amount_quote - exe.filled_amount_quote) < 1e-9:
                    matched_key = opp_id
                    break

            if matched_key is not None:
                # Found a matching opposite leg – request both to stop immediately
                opp_exe = opp_dict.pop(matched_key)
                additional_actions.extend([
                    StopExecutorAction(controller_id=self.config.id, executor_id=exe.id, keep_position=False),
                    StopExecutorAction(controller_id=self.config.id, executor_id=opp_exe.id, keep_position=False),
                ])
                # No need to store exe in side_dict (both closed)
                continue

            # No match yet → keep it in queue
            side_dict[exe.id] = exe

            # Optional: cancel outstanding opposite maker orders while we wait
            if self.config.cancel_opposite_orders_on_fill:
                opposite_side = TradeType.SELL if exe.config.side == TradeType.BUY else TradeType.BUY
                still_open_levels = self.filter_executors(
                    executors=self.executors_info,
                    filter_func=lambda e: e.is_active and e.config.side == opposite_side and e.is_trading,
                )
                for opp in still_open_levels:
                    additional_actions.append(
                        StopExecutorAction(controller_id=self.config.id, executor_id=opp.id, keep_position=True)
                    )

        return base_actions + additional_actions 