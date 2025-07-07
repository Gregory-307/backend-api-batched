# Repository Directory Map

Below is a high-level overview of the most relevant folders in this repository and what they contain.  This map provides context before the exhaustive list of individual Python files that follows.

| Directory | Purpose |
|-----------|---------|
| `bots/` | All trading-bot–related code.  Contains atomic strategy controllers (`bots/controllers/`), higher-level orchestration scripts (`bots/scripts/`), configuration stubs, archived bot runs, and other runtime assets. |
| `bots/controllers/` | Strategy controllers – the core trading logic.  Sub-folders group controllers by domain: `market_making/`, `directional_trading/`, and `generic/`. |
| `bots/scripts/` | V2 strategy scripts that manage one or more controllers live (e.g., `v2_with_controllers.py`). |
| `dashboard/` | Streamlit UI for exploring backtest results and documentation.  Contains reusable components (`hb_components/`) and multipage app files (`pages/`). |
| `routers/` | FastAPI routers that expose backend endpoints (`manage_backtesting`, `manage_files`, etc.). |
| `services/` | Backend services used by the routers (e.g., Docker orchestration, account management, bot monitoring). |
| `scripts/` | Developer utilities, smoke tests, and helper CLIs (e.g., `quick_smoke.py`, `lint_sweeps.py`).  Many live in `scripts/dev/`. |
| `utils/` | Cross-cutting helpers such as file-system utilities, candle-data caching, security/encryption, and event logging. |
| `archive/` | Legacy scripts and payloads kept for historical reference (`archive/legacy_scripts/`). |
| `results/` | Backtest outputs: summary CSVs, detail packets, cached figures, etc. |
| `sweeps/` | Parameter-sweep YAML and generated payloads used by the testing pipeline. |
| `data/` | Downloaded or cached datasets (e.g., `candles_cache/`). |
| `docs/` | Markdown documentation, including these Codebase Reference files. |
| Root-level `.py` files | Pipeline wrappers (`01_yml_to_json.py`, `02_json_to_backtests.py`, `03_multi_yml_to_backtests.py`), FastAPI entry point (`main.py`), configuration (`config.py`), and other standalone utilities. |

---

./01_yml_to_json.py
./02_json_to_backtests.py
./03_multi_yml_to_backtests.py
./archive/legacy_scripts/dev_mode_batch.py
./archive/legacy_scripts/exp_run_serial.py
./archive/legacy_scripts/simple_test.py
./batch_tester.py
./bots/__init__.py
./bots/controllers/__init__.py
./bots/controllers/directional_trading/__init__.py
./bots/controllers/directional_trading/ai_livestream.py
./bots/controllers/directional_trading/bollinger_v1.py
./bots/controllers/directional_trading/dman_v3.py
./bots/controllers/directional_trading/macd_bb_v1.py
./bots/controllers/directional_trading/supertrend_v1.py
./bots/controllers/generic/__init__.py
./bots/controllers/generic/arbitrage_controller.py
./bots/controllers/generic/basic_order_example.py
./bots/controllers/generic/basic_order_open_close_example.py
./bots/controllers/generic/grid_strike.py
./bots/controllers/generic/pmm.py
./bots/controllers/generic/quantum_grid_allocator.py
./bots/controllers/generic/xemm_multiple_levels.py
./bots/controllers/market_making/__init__.py
./bots/controllers/market_making/dman_maker_v2.py
./bots/controllers/market_making/pmm_dynamic.py
./bots/controllers/market_making/pmm_dynamic_2.py
./bots/controllers/market_making/pmm_simple.py
./bots/controllers/market_making/pmm_skew.py
./bots/scripts/__init__.py
./bots/scripts/v2_with_controllers.py
./config.py
./dashboard/__init__.py
./dashboard/hb_components/__init__.py
./dashboard/hb_components/backtesting.py
./dashboard/hb_components/backtesting_metrics.py
./dashboard/hb_components/candles.py
./dashboard/hb_components/executors.py
./dashboard/hb_components/pnl.py
./dashboard/hb_components/signals.py
./dashboard/hb_components/theme.py
./dashboard/packet_index.py
./dashboard/pages/1_Documentation.py
./dashboard/pages/2_Experiments_Overview.py
./dashboard/pages/3_Top_5.py
./dashboard/pages/4_Sweep_Analysis.py
./dashboard/pages/5_Experiment_Analysis.py
./dashboard/theme_overrides.py
./dashboard/ui_helpers.py
./grid_builder.py
./main.py
./models.py
./multi_market_sweep_tester.py
./routers/__init__.py
./routers/manage_accounts.py
./routers/manage_backtesting.py
./routers/manage_broker_messages.py
./routers/manage_databases.py
./routers/manage_docker.py
./routers/manage_files.py
./routers/manage_market_data.py
./routers/manage_performance.py
./scripts/dev/api_explorer.py
./scripts/dev_watch.py
./scripts/lint_sweeps.py
./scripts/quick_smoke.py
./scripts/scaffold_sweeps.py
./scripts/ui_smoke.py
./services/__init__.py
./services/accounts_service.py
./services/bot_archiver.py
./services/bots_orchestrator.py
./services/docker_service.py
./utils/__init__.py
./utils/candles_cache.py
./utils/check_candles.py
./utils/etl_databases.py
./utils/event_logger.py
./utils/file_system.py
./utils/models.py
./utils/security.py
