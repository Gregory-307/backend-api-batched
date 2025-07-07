## 11. frontend/visualization/performance_time_evolution.py

**Description**: Creates four-row time-evolution dashboard combining cumulative PnL, volume, activity and win/loss ratio for a pandas DataFrame of executors.

**Exports**: `create_combined_subplots`, `get_pnl_traces`, `get_volume_bar_traces`, `get_total_executions_with_position_bar_traces`, `get_win_loss_ratio_fig`

**Tags**: pnl_line, bar

```python
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from frontend.visualization.theme import get_color_scheme


def create_combined_subplots(executors: pd.DataFrame):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=["Cumulative PnL",
                                        "Cumulative Volume",
                                        "Cumulative Positions",
                                        "Win/Loss Ratio"])

    pnl_trace = get_pnl_traces(executors)
    fig.add_trace(pnl_trace, row=1, col=1)

    volume_trace = get_volume_bar_traces(executors)
    fig.add_trace(volume_trace, row=2, col=1)

    activity_trace = get_total_executions_with_position_bar_traces(executors)
    fig.add_trace(activity_trace, row=3, col=1)

    win_loss_fig = get_win_loss_ratio_fig(executors)
    for trace in win_loss_fig.data:
        fig.add_trace(trace, row=4, col=1)

    fig.update_layout(...)
    return fig

# get_pnl_traces, get_volume_bar_traces, get_total_executions_with_position_bar_traces,
# get_win_loss_ratio_fig definitions follow (see full file for details).
```

---

## 12. frontend/visualization/signals.py

**Description**: Helpers to create buy/sell signal marker traces for multiple indicator strategies (Bollinger, MACD-BB combo, SuperTrend).

**Exports**: `get_signal_traces`, `get_bollinger_v1_signal_traces`, `get_macdbb_v1_signal_traces`, `get_supertrend_v1_signal_traces`

**Tags**: signal_marker

```python
import pandas_ta as ta  # noqa: F401
import plotly.graph_objects as go

from frontend.visualization import theme


def get_signal_traces(buy_signals, sell_signals):
    tech_colors = theme.get_color_scheme()
    traces = [
        go.Scatter(x=buy_signals.index, y=buy_signals['close'], mode='markers',
                   marker=dict(color=tech_colors['buy_signal'], size=10, symbol='triangle-up'),
                   name='Buy Signal'),
        go.Scatter(x=sell_signals.index, y=sell_signals['close'], mode='markers',
                   marker=dict(color=tech_colors['sell_signal'], size=10, symbol='triangle-down'),
                   name='Sell Signal')
    ]
    return traces

# Strategy-specific wrappers build on the generic helper.
```

---

## 13. frontend/visualization/theme.py

**Description**: Central colour palette and Plotly layout settings for dark-themed charts.

**Exports**: `get_default_layout`, `get_color_scheme`

**Tags**: style

```python
def get_default_layout(title=None, height=800, width=1800):
    layout = {
        "template": "plotly_dark",
        "plot_bgcolor": 'rgba(0, 0, 0, 0)',
        "paper_bgcolor": 'rgba(0, 0, 0, 0.1)',
        "font": {"color": 'white', "size": 12},
        ...
    }
    if title:
        layout["title"] = title
    return layout


def get_color_scheme():
    return {
        'upper_band': '#4682B4',  # steel blue
        'buy_signal': '#1E90FF',
        'sell_signal': '#FF0000',
        'buy': '#32CD32',
        'sell': '#FF6347',
        'price': '#00008B',
        ...
    }
```

---

## 14. frontend/visualization/utils.py

**Description**: Tiny helper that loops through a list of traces and adds them to a figure at a specified subplot position.

**Exports**: `add_traces_to_fig`

**Tags**: helper

```python
def add_traces_to_fig(fig, traces, row=1, col=1):
    for trace in traces:
        fig.add_trace(trace, row=row, col=col)
```

---

## 15. frontend/visualization/bot_performance.py

**Description**: Full Streamlit page rendering performance tables, KPI metrics, pie charts and combined subplots, including sidebars for controller filters and Ag-Grid-style dataframes.

**Exports**: Multiple (see manifest).

**Tags**: kpi, table, pie, sidebar

```python
# --- snippet (first ~120 lines) ---
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from hummingbot.core.data_type.common import TradeType

from backend.services.backend_api_client import BackendAPIClient
from backend.utils.performance_data_source import PerformanceDataSource
from frontend.st_utils import download_csv_button, get_backend_api_client
from frontend.visualization.backtesting import create_backtesting_figure
from frontend.visualization.backtesting_metrics import render_accuracy_metrics, render_backtesting_metrics
from frontend.visualization.performance_time_evolution import create_combined_subplots

intervals_to_secs = { ... }


def display_performance_summary_table(executors, executors_with_orders: pd.DataFrame):
    if not executors_with_orders.empty:
        executors.sort_values("close_timestamp", inplace=True)
        executors["net_pnl_over_time"] = executors["net_pnl_quote"].cumsum()
        ...  # grouping & Streamlit dataframe code
```
*Note: the file spans ~300 lines with many helper functions for fetching data from the backend API, building KPI metric blocks, pie charts, combined subplots and interactive filters.* 