# Hummingbot Dashboard – Front-end Visualization Cheatsheet

A quick lookup table of reusable Plotly / Streamlit widgets found in `frontend/visualization`.  Import the component directly from the path to drop it into your own Streamlit page.

---

## 📈 Candlestick / Price
| Import path | What it gives you |
|-------------|------------------|
| `frontend.visualization.candles.get_candlestick_trace` | Full OHLC candlestick trace |
| `frontend.visualization.candles.get_bt_candlestick_trace` | Lightweight close-price line for back-tests |
| `frontend.visualization.backtesting.create_backtesting_figure` | 2-row figure: candles (+ trade overlay) + cumulative PnL |

## 🔄 Trades Overlay
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.executors.add_executors_trace` | Adds coloured entry→exit segments for each executor |
| `frontend.visualization.backtesting.create_backtesting_figure` | Bundles overlay with price & PnL |

## 💰 Cumulative PnL
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.pnl.get_pnl_trace` | Gold dashed line of cumulative quote PnL |
| `frontend.visualization.performance_time_evolution.*` | Time-evolution multi-subplot inc. PnL |

## 💹 Technical Indicators
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.indicators.get_bbands_traces` | Bollinger Bands lines |
| `frontend.visualization.indicators.get_macd_traces` | MACD line/signal/histogram |
| `frontend.visualization.indicators.get_supertrend_traces` | SuperTrend directional line |
| `frontend.visualization.indicators.get_volume_trace` | Volume bars |

## 📊 Bars / Distributions
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.executors_distribution.create_executors_distribution_traces` | Mirrored bar chart of buy vs sell order volumes |
| `frontend.visualization.dca_builder.create_dca_graph` | Multi-axis bar+line DCA visual |
| `frontend.visualization.performance_time_evolution.get_volume_bar_traces` | Cum volume over time |

## 🥧 Pie / Donut
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.performance_dca.display_dca_performance` | Pie of level distribution & close types |
| `frontend.visualization.bot_performance.performance_section` | Pie of close-type counts |

## 🖥️ KPI / Metric Cards
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.backtesting_metrics.render_backtesting_metrics` | Net PnL, drawdown, Sharpe, etc. |
| `frontend.visualization.bot_performance.display_side_analysis` | Long/short KPI block |

## 📑 Tables / Ag-Grid
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.bot_performance.display_tables_section` | Summary & raw executor tables (uses Streamlit column_config) |

## 🛠 Helpers & Theme
| Import path | Purpose |
|-------------|---------|
| `frontend.visualization.theme.get_default_layout` | Plug-and-play dark Plotly layout |
| `frontend.visualization.theme.get_color_scheme` | Central colour palette |
| `frontend.visualization.utils.add_traces_to_fig` | Loop-add many traces with one call |

---

### Sidebar / Selector Patterns
* `frontend.visualization.performance_etl.display_etl_section` – multiselect databases → checkpoint.
* `frontend.visualization.bot_performance.display_execution_analysis` – connector/pair dropdowns.

> Tip: combine the building blocks above to hit the target graphs list (candles + volume + trade dots, cumulative PnL, KPI cards, pie, scatter, etc.) with minimal extra code. 