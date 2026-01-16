# Hummingbot Backtesting Guide: Custom Strategies & Batch Testing

## Table of Contents
1. [Overview](#overview)
2. [Architecture Understanding](#architecture-understanding)
3. [Common Issues & Solutions](#common-issues--solutions)
4. [Setting Up Custom Strategies](#setting-up-custom-strategies)
5. [Batch Testing Framework](#batch-testing-framework)
6. [Debugging Strategies](#debugging-strategies)
7. [Quick Reference](#quick-reference)

## Overview

This guide documents the complete process of setting up, debugging, and running batch backtests on Hummingbot strategies, including custom controllers. It's based on real-world debugging experience and includes solutions to common pitfalls that aren't well-documented elsewhere.

### Key Learnings
- The backend-api runs inside Docker and needs proper configuration
- Many upstream controllers have bugs that need patching
- Docker Compose configuration is critical - using pre-built images vs. local builds
- Proper logging is essential for debugging

## Architecture Understanding

### System Components

```
┌─────────────────────┐     HTTP Requests    ┌──────────────────────┐
│  Test Orchestrator  │ ──────────────────>  │   Backend API        │
│ (simple_test.py)    │                      │ (Docker Container)   │
└─────────────────────┘                      └──────────────────────┘
                                                      │
                                                      ▼
                                            ┌──────────────────────┐
                                            │ Hummingbot Engine    │
                                            │ - Backtesting        │
                                            │ - Controllers        │
                                            │ - Market Data        │
                                            └──────────────────────┘
```

### Critical File Locations
- **API Endpoints**: `routers/`
  - `manage_backtesting.py` - Main backtesting endpoint
  - `manage_files.py` - Controller configuration endpoints
  - `manage_market_data.py` - Market data fetching
- **Controllers**: `bots/controllers/`
  - `market_making/` - PMM and market making strategies
  - `directional_trading/` - Directional strategies like DMAN
- **Configuration**: `docker-compose.yml` - Critical for proper setup

## Common Issues & Solutions

### Issue 1: Docker Not Using Local Code

**Symptom**: Changes to Python files aren't reflected in the running container.

**Root Cause**: `docker-compose.yml` using pre-built image instead of local build.

**Solution**:
```yaml
# WRONG - Uses pre-built image
services:
  backend-api:
    image: hummingbot/backend-api:latest

# CORRECT - Builds from local Dockerfile
services:
  backend-api:
    build: .
    volumes:
      - ./routers:/backend-api/routers
      - ./services:/backend-api/services
      # ... mount all source directories
```

**Commands**:
```bash
# After fixing docker-compose.yml
docker-compose down && docker-compose up -d --build
```

### Issue 2: IndexError on Zero Trades

**Symptom**: `IndexError: single positional indexer is out-of-bounds`

**Root Cause**: Backtesting engine's `summarize_results` doesn't handle empty trade lists.

**Location**: `hummingbot/strategy_v2/backtesting/backtesting_engine_base.py`

**Solution**:
```python
# Add guard clause in summarize_results
def summarize_results(self, executors_info, initial_portfolio_usd):
    executors_df = pd.DataFrame([e.to_dict() for e in executors_info])
    if executors_df.empty:
        return {
            "net_pnl": 0.0,
            "net_pnl_quote": 0.0,
            "total_executors": 0,
            "total_positions": 0,
            "accuracy": 0.0,
            "sharpe_ratio": 0.0,
            "note": "No trades executed"
        }
    # ... rest of the function
```

### Issue 3: DMAN Maker v2 Async Bug

**Symptom**: `TypeError: object NoneType can't be used in 'await' expression`

**Root Cause**: `validate_sufficient_balance()` is not async but is awaited.

**Solution**:
```python
# In hummingbot/strategy_v2/executors/executor_base.py
# Change:
def validate_sufficient_balance(self):
# To:
async def validate_sufficient_balance(self):
```

### Issue 4: Parameter Type Mismatches

**Common Mistakes**:
- Sending lists when strings are expected
- Missing required parameters
- Using wrong parameter names

**Example Fix for DMAN Maker v2**:
```python
# WRONG
"dca_amounts": [50],  # List
"buy_spreads": "0.00",  # Wrong parameter name

# CORRECT
"dca_amounts": "1,1,1,1",  # Comma-separated string
"dca_spreads": "0.01,0.02,0.04,0.08",  # Correct parameter name
```

## Setting Up Custom Strategies

### Step 1: Create Your Controller

```python
# bots/controllers/market_making/my_custom_strategy.py
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)

class MyCustomStrategyConfig(MarketMakingControllerConfigBase):
    controller_name: str = "my_custom_strategy"
    # Add your custom parameters here
    custom_param: float = 0.01

class MyCustomStrategy(MarketMakingControllerBase):
    def __init__(self, config: MyCustomStrategyConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
```

### Step 2: Register the Controller

```python
# In hummingbot/strategy_v2/controllers/__init__.py
from .market_making.my_custom_strategy import MyCustomStrategy

CONTROLLER_REGISTRY["my_custom_strategy"] = MyCustomStrategy
```

### Step 3: Add Logging for Debugging

```python
# In routers/manage_backtesting.py
import logging
import traceback

@router.post("/run-backtesting")
async def run_backtesting(backtesting_config: BacktestingConfig):
    try:
        # ... existing code ...
        logging.info(f"Running backtest with config: {controller_config}")
        # ... rest of function
    except Exception as e:
        logging.error("Backtesting failed:", exc_info=True)
        return {
            "error": str(e),
            "traceback": traceback.format_exc().split('\n')
        }
```

## Batch Testing Framework

### Test Script Structure

```python
#!/usr/bin/env python3
"""
Batch testing framework for Hummingbot strategies
"""
import json
import time
from datetime import datetime, timezone
import requests
from requests.auth import HTTPBasicAuth

BASE_URL = "http://localhost:8000"
USERNAME, PASSWORD = "admin", "admin"

def to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD to unix timestamp."""
    dt = datetime.fromisoformat(f"{date_str}T00:00:00+00:00")
    return int(dt.timestamp())

def run_backtest(body: dict, auth: HTTPBasicAuth, retries: int = 0) -> dict:
    """POST to /run-backtesting with retry logic."""
    # Implementation from simple_test.py
    pass

def run_batch_tests(test_configs: list, auth: HTTPBasicAuth):
    """Run multiple backtests and aggregate results."""
    results = []
    for config in test_configs:
        result = run_backtest(config, auth)
        results.append(result)
        time.sleep(1)  # Be nice to the API
    return results
```

### Parameter Sweep Example

```python
def generate_parameter_sweep():
    """Generate configurations for parameter optimization."""
    base_config = {
        "controller_name": "pmm_simple",
        "controller_type": "market_making",
        "connector_name": "kucoin",
        "trading_pair": "BTC-USDT",
        # ... other fixed parameters
    }
    
    configs = []
    for spread in [0.001, 0.002, 0.005, 0.01]:
        for stop_loss in [0.03, 0.05, 0.07]:
            config = base_config.copy()
            config.update({
                "buy_spreads": str(spread),
                "sell_spreads": str(spread),
                "stop_loss": stop_loss
            })
            configs.append(config)
    
    return configs
```

## Debugging Strategies

### 1. Enable Comprehensive Logging

```python
# Add to any router file
import logging
logging.basicConfig(level=logging.INFO)

# Log at key points
logging.info(f"Received config: {config}")
logging.info(f"Candle data shape: {candles_df.shape}")
logging.info(f"Executors created: {len(executors)}")
```

### 2. Check Docker Logs

```bash
# View real-time logs
docker-compose logs -f backend-api

# View last 100 lines
docker-compose logs --tail=100 backend-api
```

### 3. API Explorer Script

```python
# api_explorer.py - Use to inspect available endpoints
def get_controller_config(controller_type: str, controller_name: str):
    endpoint = f"/controller-config-pydantic/{controller_type}/{controller_name}"
    response = requests.get(f"{BASE_URL}{endpoint}", auth=auth)
    return response.json()
```

### 4. Validate Market Data

Always check if the strategy is receiving data:
```python
# In your controller
if self.candles_df.empty:
    logging.warning("No candle data available!")
    return []
```

## Quick Reference

### Essential Commands

```bash
# Rebuild and restart containers
docker-compose down && docker-compose up -d --build

# View logs
docker-compose logs backend-api

# Run tests
python3 simple_test.py

# Check container status
docker ps
```

### Common Parameter Fixes

| Controller | Parameter | Wrong | Correct |
|------------|-----------|-------|---------|
| dman_maker_v2 | dca_amounts | `[50]` (list) | `"1,1,1,1"` (string) |
| pmm_simple | buy_amounts_pct | `None` | `"100"` or `"50,50"` |
| dman_v3 | interval | `"1hr"` | `"1h"` |
| All | trading_pair | `"btc-usdt"` | `"BTC-USDT"` |

### Working Controller Configurations

```python
# PMM Simple (Tested & Working)
pmm_simple_config = {
    "controller_name": "pmm_simple",
    "controller_type": "market_making",
    "connector_name": "kucoin",
    "trading_pair": "BTC-USDT",
    "total_amount_quote": 1000.0,
    "buy_spreads": "0.005,0.01",
    "sell_spreads": "0.005,0.01",
    "buy_amounts_pct": "50,50",
    "sell_amounts_pct": "50,50",
    "executor_refresh_time": 300,
    "cooldown_time": 15,
    "leverage": 20,
    "stop_loss": 0.03,
    "take_profit": 0.02,
    "time_limit": 2700,
    "candles_config": [{"connector": "kucoin", "trading_pair": "BTC-USDT", "interval": "3m"}]
}

# DMAN v3 (After Patches)
dman_v3_config = {
    "controller_name": "dman_v3",
    "controller_type": "directional_trading",
    "connector_name": "kucoin",
    "trading_pair": "BTC-USDT",
    "total_amount_quote": 1000.0,
    "bb_long_threshold": 0.3,  # Lowered for more trades
    "bb_short_threshold": 0.3,  # Lowered for more trades
    "cooldown_time": 60,  # Reduced for short backtests
    "max_executors_per_side": 4,
    "dca_spreads": "0.001,0.01,0.03,0.06",
    # ... other parameters
}
```

## Next Steps

1. **Patch Known Issues**: Apply the async fix and guard clauses mentioned above
2. **Test Your Patches**: Run simple_test.py to verify fixes work
3. **Build Batch Runner**: Extend the framework for parameter optimization
4. **Monitor Performance**: Add metrics collection and visualization
5. **Document Your Strategies**: Keep notes on what parameters work best

Remember: Always test with small amounts first, and thoroughly backtest before deploying any strategy live! 