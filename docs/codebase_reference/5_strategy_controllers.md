# Codebase Reference: Strategy Controllers & Scripts

This document describes representative strategy controllers (the core trading logic) and the V2 strategy scripts that run them.

---

## V2 Strategy Scripts

This section describes the high-level scripts that manage the lifecycle of one or more controllers in a live environment.

### 1. `bots/scripts/v2_with_controllers.py`
*   **Purpose**: A sophisticated V2 strategy script that runs and manages multiple controllers simultaneously. It is designed for live trading.
*   **Key Features**:
    *   **Lifecycle Management**: Starts and stops multiple controllers based on a single configuration file.
    *   **Risk Management**: Includes global and per-controller drawdown protection to automatically stop strategies if they lose too much.
    *   **Auto-Rebalancing**: Contains logic to periodically check and rebalance assets across connectors to meet the needs of each strategy.
    *   **Cash-Out Feature**: Provides a "kill switch" to gracefully stop all trading, let existing trades finish, and then exit.
    *   **Performance Reporting**: Publishes real-time performance metrics to an MQTT topic for monitoring.

---

## Strategy Controllers (`bots/controllers/*`)

These files contain the atomic trading logic for individual strategies. They are designed to be managed by a higher-level V2 script like the one described above.

### 1. `bots/controllers/market_making/pmm_simple.py`
* **Purpose**: A minimal market-making controller that places a single buy and sell level at fixed spreads.
* **Highlights**:
  * Inherits from `MarketMakingControllerBase`.
  * Config model contains `buy_spreads`, `sell_spreads`, `buy_amounts_pct`, `sell_amounts_pct`.
  * `update_processed_data()` computes current mid-price and desired order prices.
  * A good starting template for building more sophisticated PMM strategies.

### 2. `bots/controllers/market_making/pmm_dynamic.py`
* **Purpose**: A dynamic PMM that widens or narrows its spreads based on market volatility, using indicators like MACD and NATR.
* **Highlights**:
  * Reads candle data (`candles_config`) and computes technical indicators.
  * Adjusts `buy_spreads` and `sell_spreads` in each refresh interval based on market conditions.
  * Uses `macd_fast`, `macd_slow`, and `natr_length` from its configuration.

### 3. `bots/controllers/market_making/pmm_dynamic_2.py`
* **Purpose**: A second-generation dynamic PMM that improves on the original by adding separate long/short activation bounds and leverage control.
* **Highlights**:
  * Adds parameters like `activation_bounds` and `position_rebalance_threshold_pct`.
  * Demonstrates how to implement a two-sided position-rebalancing mechanic.
  * Registered via an upstream patch so the backtesting engine can auto-discover it.

### 4. `bots/controllers/market_making/pmm_skew.py`
* **Purpose**: A micro-variant of `pmm_simple` that introduces a `skew_factor` to bias spreads, which is useful for directional hedging.
* **Highlights**:
  * The configuration adds a single float field: `skew_factor`.
  * Overrides `get_processed_spreads()` to widen sell spreads and tighten buy spreads when the `skew_factor` is positive.
  * Shows how easily an existing controller can be extended with a single new parameter.

### 5. `bots/controllers/market_making/dman_maker_v2.py`
*   **Purpose**: A market-making strategy that uses Dollar-Cost Averaging (DCA). It places a grid of orders to scale into a position.
*   **Mechanism**: Instead of creating single orders, it creates `DCAExecutor` instances. Each executor then manages a series of limit orders at progressively wider spreads, allowing the strategy to build a position as the market moves against it.

### 6. `bots/controllers/directional_trading/dman_v3.py`
* **Purpose**: A DCA-style directional algorithm that enters positions based on Bollinger Band signals and averages down using a predefined grid of orders.
* **Highlights**:
  * Features configurable DCA ladders (`dca_spreads`, `dca_amounts_pct`).
  * Supports `max_executors_per_side` to cap the number of active positions.
  * Uses a triple-barrier exit strategy (take-profit, stop-loss, and time-limit).
  * Relies on the patched `validate_sufficient_balance` fix for improved balance validation.

### 7. `bots/controllers/directional_trading/supertrend_v1.py`
*   **Purpose**: A directional trading strategy controller based on the popular SuperTrend technical indicator.
*   **Key Features**:
    *   It uses the `pandas-ta` library to calculate the SuperTrend indicator from candle data.
    *   It generates a "long" signal when the price is above the SuperTrend line and a "short" signal when it is below.
    *   The `percentage_threshold` parameter allows for fine-tuning the entry condition based on the distance from the trendline.
*   **Usage**: Serves as a clear example of how to implement a complete, indicator-based trading strategy within the controller framework.

### 8. `bots/controllers/directional_trading/bollinger_v1.py`
*   **Purpose**: A classic mean-reversion strategy that uses Bollinger Bands to generate trading signals.
*   **Key Features**:
    *   It uses the `pandas-ta` library to calculate Bollinger Bands and the Bollinger Band Percentage (`%B`) indicator.
    *   It generates a "long" signal when the `%B` is below a lower threshold (e.g., 0) and a "short" signal when it is above an upper threshold (e.g., 1).
*   **Usage**: A straightforward example of a mean-reversion controller.

### 9. `bots/controllers/directional_trading/macd_bb_v1.py`
*   **Purpose**: A more advanced directional strategy that combines Bollinger Bands and the MACD indicator for a filtered entry signal.
*   **Key Features**:
    *   It generates a "long" signal only when the price is near the lower Bollinger Band AND the MACD indicates upward momentum.
    *   The "short" signal requires the price to be near the upper band AND the MACD to show downward momentum.
*   **Usage**: Demonstrates how to combine multiple indicators to create a more robust trading signal and reduce false entries.

### 10. `bots/controllers/directional_trading/ai_livestream.py`
*   **Purpose**: A unique controller that subscribes to an external data stream for its trading signals, likely from a separate Machine Learning model.
*   **Key Features**:
    *   Uses the `hbotrc` `ExternalTopicFactory` to listen to an MQTT topic for incoming JSON signals.
    *   The signal is expected to contain long/short probabilities.
    *   It enters a trade when the probability for a given direction crosses a configurable threshold.
*   **Usage**: A powerful example of how to integrate external, event-driven signal sources into the trading framework.

---
## Generic Controllers

This section covers general-purpose or example controllers that demonstrate specific concepts.

### 11. `bots/controllers/generic/arbitrage_controller.py`
*   **Purpose**: A sophisticated controller for executing cross-exchange arbitrage.
*   **Key Features**:
    *   Monitors prices on two different exchanges (or trading pairs).
    *   When a profitable arbitrage opportunity is detected, it creates an `ArbitrageExecutor` to execute the buy and sell orders simultaneously.
    *   Includes logic to handle rate conversions for quote assets and gas fees on AMM connectors.
    *   Manages trade imbalance to limit exposure risk.

### 12. `bots/controllers/generic/basic_order_example.py`
*   **Purpose**: A minimal example demonstrating how to create a single order executor.
*   **Key Features**:
    *   Places a single market order at a regular interval defined by `order_frequency`.
    *   It only creates a new order if no other orders from this controller are currently active.
*   **Usage**: An ideal starting point for developers new to the controller framework.

### 13. `bots/controllers/generic/basic_order_open_close_example.py`
*   **Purpose**: An example that demonstrates a complete trade lifecycle: opening a position and then closing it.
*   **Key Features**:
    *   First, it submits an "OPEN" order.
    *   After a delay (`close_order_delay`), it submits a "CLOSE" order for the created position.
    *   Includes boolean flags to test partial closes and different closing mechanisms.
*   **Usage**: A useful example for understanding position management.

### 14. `bots/controllers/generic/grid_strike.py`
*   **Purpose**: A grid trading strategy that uses the specialized `GridExecutor`.
*   **Mechanism**:
    *   The controller is responsible for creating a single `GridExecutor` that operates within a defined price range (`start_price` to `end_price`).
    *   The `GridExecutor` then takes over, managing the placement, cancellation, and tracking of all the individual orders that make up the grid.
*   **Usage**: Demonstrates how to delegate complex execution logic to a dedicated executor.

### 15. `bots/controllers/generic/pmm.py`
*   **Purpose**: A highly configurable and powerful Pure Market Making (PMM) controller.
*   **Key Features**:
    *   **Inventory Management**: Actively manages inventory by adjusting spreads and order sizes based on the target base percentage.
    *   **Skewing**: Can skew spreads to one side to more aggressively manage inventory.
    *   **Layered Orders**: Supports multiple levels of buy and sell orders.
    *   **Dynamic Configuration**: Many parameters, like spreads and amounts, can be updated on the fly.
*   **Usage**: A feature-rich, all-in-one market-making controller suitable for a wide range of scenarios.

### 16. `bots/controllers/generic/quantum_grid_allocator.py`
*   **Purpose**: An extremely advanced portfolio management strategy that deploys and manages grid strategies across multiple assets.
*   **Key Features**:
    *   **Portfolio Management**: Manages a portfolio based on target percentage allocations for different assets.
    *   **Dynamic Grid Allocation**: When an asset's allocation deviates from its target, the controller deploys long or short grid strategies to rebalance it. The size of the grid ("quantum") is determined by the magnitude of the deviation.
    *   **Dynamic Spreads**: Uses Bollinger Band width to dynamically set the grid range.
*   **Usage**: A sophisticated example of a "strategy of strategies" that combines portfolio management with active trading.

### 17. `bots/controllers/generic/xemm_multiple_levels.py`
*   **Purpose**: A cross-exchange market-making (XEMM) strategy that places orders on a maker exchange and hedges them on a taker exchange.
*   **Key Features**:
    *   Creates `XEMMExecutor` instances to manage the arbitrage between a maker and taker exchange.
    *   Supports multiple order levels on both the buy and sell side, each with its own `target_profitability`.
*   **Usage**: A clear example of how to implement a classic XEMM arbitrage strategy. 