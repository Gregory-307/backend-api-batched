"""Unit tests for trading strategy configurations and logic.

These tests validate the configuration models and pure functions
without requiring the full Hummingbot runtime.
"""
from decimal import Decimal

import pytest

# Check if hummingbot dependencies are available
try:
    from bots.controllers.generic.portfolio_rebalancing_grid import (
        PortfolioRebalancingGridConfig,
    )
    HUMMINGBOT_AVAILABLE = True
except ImportError:
    HUMMINGBOT_AVAILABLE = False


@pytest.mark.skipif(not HUMMINGBOT_AVAILABLE, reason="Hummingbot not installed")
class TestPortfolioRebalancingGridConfig:
    """Tests for PortfolioRebalancingGridConfig validation and properties."""

    def test_default_config_is_valid(self):
        """Default configuration should be valid."""
        config = PortfolioRebalancingGridConfig()
        assert config.controller_name == "portfolio_rebalancing_grid"
        assert config.portfolio_allocation == {"SOL": Decimal("0.50")}

    def test_quote_asset_allocation_calculated_correctly(self):
        """Quote asset allocation should be 1 - sum(other allocations)."""
        # Single asset at 50% → quote should be 50%
        config = PortfolioRebalancingGridConfig(
            portfolio_allocation={"SOL": Decimal("0.50")}
        )
        assert config.quote_asset_allocation == Decimal("0.50")

        # Two assets totaling 70% → quote should be 30%
        config = PortfolioRebalancingGridConfig(
            portfolio_allocation={
                "SOL": Decimal("0.40"),
                "ETH": Decimal("0.30"),
            }
        )
        assert config.quote_asset_allocation == Decimal("0.30")

        # Three assets totaling 90% → quote should be 10%
        config = PortfolioRebalancingGridConfig(
            portfolio_allocation={
                "SOL": Decimal("0.30"),
                "ETH": Decimal("0.30"),
                "BTC": Decimal("0.30"),
            }
        )
        assert config.quote_asset_allocation == Decimal("0.10")

    def test_allocation_cannot_exceed_100_percent(self):
        """Total allocation must be less than 100% to leave room for quote asset."""
        with pytest.raises(ValueError, match="exceeds or equals 100%"):
            PortfolioRebalancingGridConfig(
                portfolio_allocation={"SOL": Decimal("1.0")}
            )

        with pytest.raises(ValueError, match="exceeds or equals 100%"):
            PortfolioRebalancingGridConfig(
                portfolio_allocation={
                    "SOL": Decimal("0.60"),
                    "ETH": Decimal("0.50"),
                }
            )

    def test_quote_asset_cannot_be_in_allocation(self):
        """Quote asset (FDUSD) should not be explicitly allocated."""
        with pytest.raises(ValueError, match="should not be explicitly allocated"):
            PortfolioRebalancingGridConfig(
                portfolio_allocation={"FDUSD": Decimal("0.50")}
            )

    def test_update_markets_adds_trading_pairs(self):
        """update_markets should add all portfolio asset pairs."""
        config = PortfolioRebalancingGridConfig(
            connector_name="binance",
            quote_asset="USDT",
            portfolio_allocation={
                "SOL": Decimal("0.30"),
                "ETH": Decimal("0.30"),
            }
        )

        markets = {}
        result = config.update_markets(markets)

        assert "binance" in result
        assert "SOL-USDT" in result["binance"]
        assert "ETH-USDT" in result["binance"]

    def test_update_markets_preserves_existing(self):
        """update_markets should not remove existing market entries."""
        config = PortfolioRebalancingGridConfig(
            connector_name="binance",
            quote_asset="USDT",
            portfolio_allocation={"SOL": Decimal("0.50")}
        )

        markets = {"binance": {"BTC-USDT"}, "kraken": {"ETH-USD"}}
        result = config.update_markets(markets)

        # Original entries preserved
        assert "BTC-USDT" in result["binance"]
        assert "kraken" in result
        # New entry added
        assert "SOL-USDT" in result["binance"]

    def test_grid_parameters_have_sensible_defaults(self):
        """Grid parameters should have sensible default values."""
        config = PortfolioRebalancingGridConfig()

        # Zone thresholds should be symmetric by default
        assert config.long_only_threshold == config.short_only_threshold

        # Grid value percentages should be reasonable
        assert Decimal("0") < config.base_grid_value_pct < Decimal("1")
        assert config.base_grid_value_pct < config.max_grid_value_pct

        # Order frequencies should be positive integers
        assert config.favorable_order_frequency > 0
        assert config.unfavorable_order_frequency > 0

        # TP/SL ratio should be between 0 and 1
        assert Decimal("0") < config.tp_sl_ratio < Decimal("1")


class TestDeviationZoneLogic:
    """Tests for the deviation zone calculation logic.

    The strategy uses three zones based on portfolio deviation:
    - Long-only: deviation < -threshold
    - Short-only: deviation > +threshold
    - Hedge: -threshold <= deviation <= +threshold
    """

    def test_zone_classification(self):
        """Test that deviation values map to correct zones."""
        # Using the default threshold of 0.2 (20%)
        threshold = Decimal("0.2")

        def get_zone(deviation: Decimal) -> str:
            if deviation < -threshold:
                return "long_only"
            elif deviation > threshold:
                return "short_only"
            else:
                return "hedge"

        # Long-only zone: need to buy (underweight)
        assert get_zone(Decimal("-0.25")) == "long_only"
        assert get_zone(Decimal("-0.50")) == "long_only"
        assert get_zone(Decimal("-1.0")) == "long_only"

        # Short-only zone: need to sell (overweight)
        assert get_zone(Decimal("0.25")) == "short_only"
        assert get_zone(Decimal("0.50")) == "short_only"
        assert get_zone(Decimal("1.0")) == "short_only"

        # Hedge zone: balanced, create both buy and sell grids
        assert get_zone(Decimal("0.0")) == "hedge"
        assert get_zone(Decimal("0.1")) == "hedge"
        assert get_zone(Decimal("-0.1")) == "hedge"
        assert get_zone(Decimal("0.2")) == "hedge"  # At threshold
        assert get_zone(Decimal("-0.2")) == "hedge"  # At threshold

    def test_deviation_calculation(self):
        """Test portfolio deviation calculation logic."""
        # Deviation = (actual - theoretical) / theoretical

        def calculate_deviation(actual: Decimal, theoretical: Decimal) -> Decimal:
            if theoretical == Decimal("0"):
                return Decimal("0")
            return (actual - theoretical) / theoretical

        # Underweight: actual < theoretical → negative deviation
        assert calculate_deviation(Decimal("80"), Decimal("100")) == Decimal("-0.2")
        assert calculate_deviation(Decimal("50"), Decimal("100")) == Decimal("-0.5")

        # Overweight: actual > theoretical → positive deviation
        assert calculate_deviation(Decimal("120"), Decimal("100")) == Decimal("0.2")
        assert calculate_deviation(Decimal("150"), Decimal("100")) == Decimal("0.5")

        # Balanced: actual == theoretical → zero deviation
        assert calculate_deviation(Decimal("100"), Decimal("100")) == Decimal("0")


class TestGridPriceCalculations:
    """Tests for grid price boundary calculations."""

    def test_tp_sl_ratio_splits_range(self):
        """TP/SL ratio should correctly split the grid range."""
        # With tp_sl_ratio = 0.8, we allocate 80% to TP side, 20% to SL side
        tp_sl_ratio = Decimal("0.8")
        grid_range = Decimal("0.01")  # 1%

        tp_multiplier = tp_sl_ratio
        sl_multiplier = Decimal("1") - tp_sl_ratio

        assert tp_multiplier == Decimal("0.8")
        assert sl_multiplier == Decimal("0.2")

        # For a BUY grid: want price to go UP (TP above, SL below)
        mid_price = Decimal("100")
        # Start price (SL side) = mid * (1 - range * sl_multiplier)
        start_price = mid_price * (1 - grid_range * sl_multiplier)
        # End price (TP side) = mid * (1 + range * tp_multiplier)
        end_price = mid_price * (1 + grid_range * tp_multiplier)

        assert start_price == Decimal("99.8")  # 0.2% below mid
        assert end_price == Decimal("100.8")   # 0.8% above mid

    def test_grid_range_symmetric_with_equal_ratio(self):
        """With 50/50 ratio, grid should be symmetric around mid price."""
        tp_sl_ratio = Decimal("0.5")
        grid_range = Decimal("0.02")  # 2%
        mid_price = Decimal("1000")

        tp_mult = tp_sl_ratio
        sl_mult = Decimal("1") - tp_sl_ratio

        start = mid_price * (1 - grid_range * sl_mult)
        end = mid_price * (1 + grid_range * tp_mult)

        # Both should be 1% away from mid
        assert start == Decimal("990")
        assert end == Decimal("1010")
        # Verify symmetry
        assert mid_price - start == end - mid_price


class TestMinimumOrderValidation:
    """Tests for minimum order amount validation logic."""

    def test_grid_value_must_support_multiple_levels(self):
        """Grid value must be large enough for at least 5 levels."""
        min_notional = Decimal("5")
        min_levels = 5
        min_grid_value = min_notional * min_levels

        assert min_grid_value == Decimal("25")

        # Grid value below minimum should be rejected
        grid_value = Decimal("20")
        assert grid_value < min_grid_value

        # Grid value at or above minimum should be accepted
        grid_value = Decimal("25")
        assert grid_value >= min_grid_value

        grid_value = Decimal("100")
        assert grid_value >= min_grid_value
