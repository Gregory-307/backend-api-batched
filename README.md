# Hummingbot Backtesting & Deployment Platform

A production-ready backend API for systematic backtesting and deployment of algorithmic trading strategies built on the Hummingbot framework.

## Overview

This platform extends the [Hummingbot backend-api](https://github.com/hummingbot/backend-api) with:

- **Batch Testing Framework**: Run 100+ parameter combinations in parallel with automatic result aggregation
- **Custom Trading Strategies**: 5 market-making and 5 directional strategies with configurable parameters
- **Parameter Sweep Tools**: YAML-based grid expansion for systematic strategy optimization
- **Upstream Bug Fixes**: 4 patches addressing async bugs, edge cases, and JSON serialization issues
- **Streamlit Dashboard**: Visual analysis of backtest results

## Architecture

```
┌─────────────────────┐      ┌────────────────────────────────────────────┐
│  Testing Layer      │      │           FastAPI Backend                  │
│                     │      │                                            │
│  batch_tester.py    │─────▶│  /run-backtesting  ───▶ BacktestingEngine │
│  grid_builder.py    │      │  /list-controllers ───▶ FileSystemUtil    │
│  multi_market_*.py  │      │  /start-container  ───▶ DockerManager     │
└─────────────────────┘      │  /broker-messages  ───▶ MQTT (EMQX)       │
                             └────────────────────────────────────────────┘
                                              │
                             ┌────────────────┴───────────────────────────┐
                             │         Trading Controllers                │
                             │                                            │
                             │  Market Making:     Directional:           │
                             │  - pmm_dynamic      - dman_v3              │
                             │  - pmm_dynamic_2    - bollinger_v1         │
                             │  - pmm_simple       - macd_bb_v1           │
                             │  - pmm_skew         - supertrend_v1        │
                             │  - dman_maker_v2    - ai_livestream        │
                             │                                            │
                             │  Generic:                                  │
                             │  - portfolio_rebalancing_grid              │
                             │  - grid_strike                             │
                             │  - xemm_multiple_levels                    │
                             └────────────────────────────────────────────┘
```

## Key Features

### Batch Testing Framework

Run systematic parameter sweeps with the batch tester:

```bash
# Generate test payloads from YAML grid
make grid GRID=sweeps/pmm_dynamic_sweep.yml OUT=pmm_dynamic_tests.json

# Execute backtests in parallel
make batch FILE=pmm_dynamic_tests.json WORKERS=8

# Or combine both steps
make sweep GRID=sweeps/pmm_dynamic_sweep.yml WORKERS=8
```

Results are saved to CSV with metrics including Sharpe ratio, PnL, drawdown, and trade statistics.

### Trading Strategies

#### PMM Dynamic (`bots/controllers/market_making/pmm_dynamic.py`)

A volatility-aware market-making strategy that uses MACD for price bias and NATR for dynamic spreads:

```python
# Price adjustment based on MACD momentum
macd_signal = -(macd - macd.mean()) / macd.std()  # Normalized MACD
macdh_signal = macdh.apply(lambda x: 1 if x > 0 else -1)  # Histogram direction

# Reference price shifted by momentum signal
price_multiplier = ((0.5 * macd_signal + 0.5 * macdh_signal) * max_price_shift).iloc[-1]
reference_price = close * (1 + price_multiplier)

# Spreads scaled by volatility (NATR)
spread_multiplier = natr  # Normalized ATR as percentage
```

#### DMAN v3 (`bots/controllers/directional_trading/dman_v3.py`)

Bollinger Bands mean-reversion with DCA execution:

- **Entry**: Long when BBP < threshold, short when BBP > (1 - threshold)
- **Position Management**: DCA executor with configurable levels
- **Exit**: Triple barrier (take-profit, stop-loss, time-limit)

#### Portfolio Rebalancing Grid (`bots/controllers/generic/portfolio_rebalancing_grid.py`)

A deviation-aware grid strategy that maintains target portfolio allocations:

- Tracks theoretical vs actual allocation for each asset
- Creates directional grids based on deviation zones:
  - **Long-only zone**: Deviation < -threshold → buy grids only
  - **Short-only zone**: Deviation > +threshold → sell grids only
  - **Hedge zone**: Creates both buy and sell grids
- Optional Bollinger Band-based dynamic grid ranges

### Parameter Sweep Format

Define sweeps in YAML with automatic Cartesian product expansion:

```yaml
# sweeps/pmm_dynamic_sweep.yml
base:
  controller_type: market_making
  controller_name: pmm_dynamic
  connector_name: binance_perpetual
  trading_pair: BTC-USDT
  leverage: 5

grid:
  buy_spreads: [[0.01, 0.02], [0.01, 0.02, 0.03]]
  sell_spreads: [[0.01, 0.02], [0.01, 0.02, 0.03]]
  macd_fast: [12, 21]
  macd_slow: [26, 42]
  natr_length: [14, 21]

meta:
  start_time: "2024-01-01"
  end_time: "2024-03-01"
  resolution: "1m"
  trade_cost: 0.0006
```

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for containerized deployment)
- Conda (for local development)

### Installation

**Option A: Conda (Development)**

```bash
make install
conda activate backend-api
uvicorn main:app --reload
```

**Option B: Docker Compose (Production)**

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up --build
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
# API Authentication
API_USERNAME=your_username
API_PASSWORD=your_secure_password

# MQTT Broker (for live bot communication)
BROKER_HOST=localhost
BROKER_PORT=1883

# Hummingbot config encryption
CONFIG_PASSWORD=your_config_password
```

### Running Backtests

```bash
# 1. Start the API
uvicorn main:app --reload

# 2. Run a single backtest via API
curl -X POST "http://localhost:8000/run-backtesting" \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": 1704067200,
    "end_time": 1706745600,
    "backtesting_resolution": "1m",
    "trade_cost": 0.0006,
    "config": {
      "controller_type": "market_making",
      "controller_name": "pmm_simple",
      "connector_name": "binance_perpetual",
      "trading_pair": "BTC-USDT"
    }
  }'

# 3. Or use the batch tester for parameter sweeps
make sweep GRID=sweeps/pmm_simple_sweep.yml WORKERS=4
```

### Analyzing Results

Launch the Streamlit dashboard:

```bash
streamlit run dashboard/app.py
```

## Project Structure

```
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration constants
├── routers/                # API endpoint handlers
│   ├── manage_backtesting.py   # Backtest execution
│   ├── manage_docker.py        # Container lifecycle
│   ├── manage_files.py         # Controller config management
│   └── ...
├── services/               # Business logic
│   ├── docker_service.py       # Docker API wrapper
│   ├── bots_orchestrator.py    # Bot lifecycle management
│   └── bot_archiver.py         # S3/local archiving
├── bots/
│   └── controllers/        # Trading strategy implementations
│       ├── market_making/      # PMM strategies
│       ├── directional_trading/# Directional strategies
│       └── generic/            # Multi-purpose strategies
├── batch_tester.py         # Parallel backtest orchestrator
├── grid_builder.py         # YAML → JSON parameter expansion
├── dashboard/app.py        # Streamlit results visualization
├── patches/                # Upstream Hummingbot fixes
└── docs/                   # Additional documentation
    ├── debugging-guide.md
    └── adding-strategies.md
```

## Upstream Patches

This project includes patches for known issues in the Hummingbot backtesting engine:

| Patch | Issue | Fix |
|-------|-------|-----|
| `01_async_dca.patch` | `TypeError: object NoneType can't be used in 'await'` | Added async/await to `validate_sufficient_balance` |
| `02_guard_no_positions.patch` | `IndexError` when backtest produces no trades | Guard clause for empty executor lists |
| `03_fix_sharpe.patch` | Division by zero in Sharpe ratio calculation | Safe division with fallback to 0 |
| `04_register_pmm2.patch` | PMM Dynamic 2 controller not registered | Added to controller registry |

## API Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your controller to `bots/controllers/<type>/<name>.py`
4. Create a sweep file in `sweeps/`
5. Run `make sweep` to validate
6. Submit a pull request

See [docs/adding-strategies.md](docs/adding-strategies.md) for detailed instructions.

## License

This project is built on [Hummingbot](https://github.com/hummingbot/hummingbot), which is licensed under Apache 2.0.
