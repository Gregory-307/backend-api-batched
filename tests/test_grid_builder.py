"""Unit tests for grid_builder.py parameter expansion logic."""
import pytest

from grid_builder import build_payloads, expand_grid


class TestExpandGrid:
    """Tests for the expand_grid function (Cartesian product expansion)."""

    def test_empty_grid_returns_single_empty_dict(self):
        """An empty grid should produce a single empty configuration."""
        result = expand_grid({})
        assert result == [{}]

    def test_single_parameter_expansion(self):
        """A single parameter should expand to one dict per value."""
        grid = {"macd_fast": [12, 21, 42]}
        result = expand_grid(grid)
        assert len(result) == 3
        assert result == [
            {"macd_fast": 12},
            {"macd_fast": 21},
            {"macd_fast": 42},
        ]

    def test_two_parameters_cartesian_product(self):
        """Two parameters should produce Cartesian product (m × n combinations)."""
        grid = {
            "macd_fast": [12, 21],
            "macd_slow": [26, 42],
        }
        result = expand_grid(grid)
        assert len(result) == 4  # 2 × 2 = 4
        # Verify all combinations exist
        assert {"macd_fast": 12, "macd_slow": 26} in result
        assert {"macd_fast": 12, "macd_slow": 42} in result
        assert {"macd_fast": 21, "macd_slow": 26} in result
        assert {"macd_fast": 21, "macd_slow": 42} in result

    def test_three_parameters_cartesian_product(self):
        """Three parameters should produce all combinations (m × n × p)."""
        grid = {
            "a": [1, 2],
            "b": [10, 20],
            "c": [100, 200],
        }
        result = expand_grid(grid)
        assert len(result) == 8  # 2 × 2 × 2 = 8

    def test_preserves_list_values(self):
        """List values within grid items should be preserved (not further expanded)."""
        grid = {
            "buy_spreads": [[0.01, 0.02], [0.01, 0.02, 0.03]],
        }
        result = expand_grid(grid)
        assert len(result) == 2
        assert result[0]["buy_spreads"] == [0.01, 0.02]
        assert result[1]["buy_spreads"] == [0.01, 0.02, 0.03]


class TestBuildPayloads:
    """Tests for the build_payloads function (API payload generation)."""

    def test_base_config_merged_with_grid_variants(self):
        """Base config should be merged with each grid variant."""
        base = {
            "controller_type": "market_making",
            "controller_name": "pmm_dynamic",
            "trading_pair": "BTC-USDT",
        }
        grid = {"macd_fast": [12, 21]}
        meta = {}

        result = build_payloads(base, grid, meta)

        assert len(result) == 2
        # Both should have base config
        assert result[0]["config"]["controller_type"] == "market_making"
        assert result[1]["config"]["trading_pair"] == "BTC-USDT"
        # Each should have different macd_fast
        assert result[0]["config"]["macd_fast"] == 12
        assert result[1]["config"]["macd_fast"] == 21

    def test_generates_unique_labels(self):
        """Each payload should have a unique label."""
        base = {"controller_name": "pmm_simple"}
        grid = {"leverage": [1, 5, 10]}
        meta = {}

        result = build_payloads(base, grid, meta)

        labels = [p["label"] for p in result]
        assert len(labels) == len(set(labels))  # All unique
        assert labels == ["pmm_simple_1", "pmm_simple_2", "pmm_simple_3"]

    def test_meta_keys_extracted_to_payload_level(self):
        """Standard meta keys (start, end, resolution, fee) should be at payload level."""
        base = {"controller_name": "test"}
        grid = {}
        meta = {
            "start": "2024-01-01",
            "end": "2024-03-01",
            "resolution": "1m",
            "fee": 0.0006,
        }

        result = build_payloads(base, grid, meta)

        assert len(result) == 1
        payload = result[0]
        # Meta keys at payload level
        assert payload["start"] == "2024-01-01"
        assert payload["end"] == "2024-03-01"
        assert payload["resolution"] == "1m"
        assert payload["fee"] == 0.0006

    def test_non_meta_keys_merged_into_config(self):
        """Non-standard meta keys should be merged into the config."""
        base = {"controller_name": "test"}
        grid = {}
        meta = {
            "start": "2024-01-01",
            "custom_field": "custom_value",
        }

        result = build_payloads(base, grid, meta)

        payload = result[0]
        # Custom field should be in config, not at top level
        assert "custom_field" not in payload
        assert payload["config"]["custom_field"] == "custom_value"

    def test_auto_generates_amounts_pct_for_spreads(self):
        """Missing buy_amounts_pct/sell_amounts_pct should be auto-generated."""
        base = {"controller_name": "test"}
        grid = {"buy_spreads": [[0.01, 0.02, 0.03]]}
        meta = {}

        result = build_payloads(base, grid, meta)

        config = result[0]["config"]
        # 3 spreads → 3 equal amounts (1/3 each)
        assert "buy_amounts_pct" in config
        assert len(config["buy_amounts_pct"]) == 3
        assert all(abs(amt - 0.333333) < 0.001 for amt in config["buy_amounts_pct"])

    def test_scalar_spreads_converted_to_list(self):
        """Scalar spread values should be converted to single-element lists."""
        base = {"controller_name": "test"}
        grid = {"buy_spreads": [0.01]}  # Single value, not a list
        meta = {}

        result = build_payloads(base, grid, meta)

        config = result[0]["config"]
        # Should be wrapped in a list
        assert config["buy_spreads"] == [0.01]

    def test_candles_config_gets_time_bounds(self):
        """candles_config entries should inherit start/end from meta."""
        base = {
            "controller_name": "test",
            "candles_config": [
                {"connector": "binance", "trading_pair": "BTC-USDT", "interval": "1m"}
            ],
        }
        grid = {}
        meta = {"start": "2024-01-01", "end": "2024-03-01"}

        result = build_payloads(base, grid, meta)

        candles = result[0]["config"]["candles_config"][0]
        assert candles["start_time"] == "2024-01-01"
        assert candles["end_time"] == "2024-03-01"

    def test_empty_grid_produces_single_payload(self):
        """Empty grid should produce exactly one payload with base config."""
        base = {"controller_name": "pmm_simple", "leverage": 5}
        grid = {}
        meta = {}

        result = build_payloads(base, grid, meta)

        assert len(result) == 1
        assert result[0]["config"]["controller_name"] == "pmm_simple"
        assert result[0]["config"]["leverage"] == 5


class TestIntegration:
    """Integration tests for realistic sweep configurations."""

    def test_realistic_pmm_sweep(self):
        """Test a realistic PMM parameter sweep configuration."""
        base = {
            "controller_type": "market_making",
            "controller_name": "pmm_dynamic",
            "connector_name": "binance_perpetual",
            "trading_pair": "BTC-USDT",
            "leverage": 5,
            "total_amount_quote": 1000,
        }
        grid = {
            "buy_spreads": [[0.01, 0.02], [0.01, 0.02, 0.03]],
            "sell_spreads": [[0.01, 0.02], [0.01, 0.02, 0.03]],
            "macd_fast": [12, 21],
            "macd_slow": [26, 42],
        }
        meta = {
            "start": "2024-01-01",
            "end": "2024-03-01",
            "resolution": "1m",
            "fee": 0.0006,
        }

        result = build_payloads(base, grid, meta)

        # 2 × 2 × 2 × 2 = 16 combinations
        assert len(result) == 16

        # All payloads should have required fields
        for payload in result:
            assert payload["start"] == "2024-01-01"
            assert payload["fee"] == 0.0006
            assert payload["config"]["controller_name"] == "pmm_dynamic"
            assert "label" in payload
            assert "buy_amounts_pct" in payload["config"]
            assert "sell_amounts_pct" in payload["config"]

    def test_large_grid_expansion(self):
        """Verify correct expansion for larger grids."""
        base = {"controller_name": "test"}
        grid = {
            "a": [1, 2, 3],      # 3 values
            "b": [10, 20],       # 2 values
            "c": [100, 200, 300, 400],  # 4 values
        }
        meta = {}

        result = build_payloads(base, grid, meta)

        # 3 × 2 × 4 = 24 combinations
        assert len(result) == 24

        # Each combination should be unique
        configs = [tuple(sorted(p["config"].items())) for p in result]
        assert len(configs) == len(set(configs))
