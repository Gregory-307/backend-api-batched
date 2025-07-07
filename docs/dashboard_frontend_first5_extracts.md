## 1. frontend/visualization/candles.py

**Description**: Light-weight helpers that return Plotly traces for full OHLC candlesticks or a simple close-price line (for back-tests).

**Exports**: `get_candlestick_trace`, `get_bt_candlestick_trace`

**Tags**: candlestick

```python
import pandas as pd
import plotly.graph_objects as go

from frontend.visualization import theme


def get_candlestick_trace(df):
    return go.Candlestick(x=df.index,
                          open=df['open'],
                          high=df['high'],
                          low=df['low'],
                          close=df['close'],
                          name="Candlesticks",
                          increasing_line_color='#2ECC71', decreasing_line_color='#E74C3C', )


def get_bt_candlestick_trace(df):
    df.index = pd.to_datetime(df.timestamp, unit='s')
    return go.Scatter(x=df.index,
                      y=df['close'],
                      mode='lines',
                      line=dict(color=theme.get_color_scheme()["price"]),
                      )
```

---

## 2. frontend/visualization/executors.py

**Description**: Overlay coloured entry/exit segments representing each trade/executor on an existing figure.

**Exports**: `add_executors_trace`

**Tags**: trades_overlay

```python
from decimal import Decimal

import pandas as pd
import plotly.graph_objects as go
from hummingbot.connector.connector_base import TradeType


def add_executors_trace(fig, executors, row, col):
    for executor in executors:
        entry_time = pd.to_datetime(executor.timestamp, unit='s')
        entry_price = executor.custom_info["current_position_average_price"]
        exit_time = pd.to_datetime(executor.close_timestamp, unit='s')
        exit_price = executor.custom_info.get("close_price", executor.custom_info["current_position_average_price"])
        name = "Buy Executor" if executor.config.side == TradeType.BUY else "Sell Executor"

        if executor.filled_amount_quote == 0:
            fig.add_trace(go.Scatter(x=[entry_time, exit_time], y=[entry_price, entry_price], mode='lines',
                                     line=dict(color='grey', width=2, dash="dash"), name=name), row=row, col=col)
        else:
            if executor.net_pnl_quote > Decimal(0):
                fig.add_trace(go.Scatter(x=[entry_time, exit_time], y=[entry_price, exit_price], mode='lines',
                                         line=dict(color='green', width=3), name=name), row=row, col=col)
            else:
                fig.add_trace(go.Scatter(x=[entry_time, exit_time], y=[entry_price, exit_price], mode='lines',
                                         line=dict(color='red', width=3), name=name), row=row, col=col)
    return fig
```

---

## 3. frontend/visualization/pnl.py

**Description**: Build cumulative PnL line trace from a list of `ExecutorInfo` objects.

**Exports**: `get_pnl_trace`

**Tags**: pnl_line

```python
from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


def get_pnl_trace(executors: List[ExecutorInfo]):
    pnl = [e.net_pnl_quote for e in executors]
    cum_pnl = np.cumsum(pnl)
    return go.Scatter(
        x=pd.to_datetime([e.close_timestamp for e in executors], unit="s"),
        y=cum_pnl,
        mode='lines',
        line=dict(color='gold', width=2, dash="dash"),
        name='Cumulative PNL'
    )
```

---

## 4. frontend/visualization/backtesting.py

**Description**: Assemble a two-row Plotly figure (candles + trades overlay + PnL) and apply dark layout.

**Exports**: `create_backtesting_figure`

**Tags**: candlestick, trades_overlay, pnl_line

```python
from plotly.subplots import make_subplots

from frontend.visualization.candles import get_bt_candlestick_trace
from frontend.visualization.executors import add_executors_trace
from frontend.visualization.pnl import get_pnl_trace
from frontend.visualization.theme import get_default_layout


def create_backtesting_figure(df, executors, config):
    # Create subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, subplot_titles=('Candlestick', 'PNL Quote'),
                        row_heights=[0.7, 0.3])

    # Add candlestick trace
    fig.add_trace(get_bt_candlestick_trace(df), row=1, col=1)

    # Add executors trace
    fig = add_executors_trace(fig, executors, row=1, col=1)

    # Add PNL trace
    fig.add_trace(get_pnl_trace(executors), row=2, col=1)

    # Apply the theme layout
    layout_settings = get_default_layout(f"Trading Pair: {config['trading_pair']}")
    layout_settings["showlegend"] = False
    fig.update_layout(**layout_settings)

    # Update axis properties
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(row=2, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="PNL", row=2, col=1)
    return fig
```

---

## 5. frontend/visualization/backtesting_metrics.py

**Description**: Streamlit KPI cards for core back-test metrics and accuracy / close-type breakdowns.

**Exports**: `render_backtesting_metrics`, `render_accuracy_metrics`, `render_accuracy_metrics2`, `render_close_types`

**Tags**: kpi

```python
import streamlit as st


def render_backtesting_metrics(summary_results, title="Backtesting Metrics"):
    net_pnl = summary_results.get('net_pnl', 0)
    net_pnl_quote = summary_results.get('net_pnl_quote', 0)
    total_volume = summary_results.get('total_volume', 0)
    total_executors_with_position = summary_results.get('total_executors_with_position', 0)

    max_drawdown_usd = summary_results.get('max_drawdown_usd', 0)
    max_drawdown_pct = summary_results.get('max_drawdown_pct', 0)
    sharpe_ratio = summary_results.get('sharpe_ratio', 0)
    profit_factor = summary_results.get('profit_factor', 0)

    # Displaying KPIs in Streamlit
    st.write(f"### {title}")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric(label="Net PNL (Quote)", value=f"{net_pnl_quote:.2f}", delta=f"{net_pnl:.2%}")
    col2.metric(label="Max Drawdown (USD)", value=f"{max_drawdown_usd:.2f}", delta=f"{max_drawdown_pct:.2%}")
    col3.metric(label="Total Volume (Quote)", value=f"{total_volume:.2f}")
    col4.metric(label="Sharpe Ratio", value=f"{sharpe_ratio:.2f}")
    col5.metric(label="Profit Factor", value=f"{profit_factor:.2f}")
    col6.metric(label="Total Executors with Position", value=total_executors_with_position)


def render_accuracy_metrics(summary_results):
    accuracy = summary_results.get('accuracy', 0)
    total_long = summary_results.get('total_long', 0)
    total_short = summary_results.get('total_short', 0)
    accuracy_long = summary_results.get('accuracy_long', 0)
    accuracy_short = summary_results.get('accuracy_short', 0)

    st.write("#### Accuracy Metrics")
    st.metric(label="Global Accuracy", value=f"{accuracy:.2%}")
    st.metric(label="Total Long", value=total_long)
    st.metric(label="Total Short", value=total_short)
    st.metric(label="Accuracy Long", value=f"{accuracy_long:.2%}")
    st.metric(label="Accuracy Short", value=f"{accuracy_short:.2%}")


def render_accuracy_metrics2(summary_results):
    accuracy = summary_results.get('accuracy', 0)
    total_long = summary_results.get('total_long', 0)
    total_short = summary_results.get('total_short', 0)
    accuracy_long = summary_results.get('accuracy_long', 0)
    accuracy_short = summary_results.get('accuracy_short', 0)

    st.write("#### Accuracy Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(label="Global Accuracy", value=f"{accuracy}:.2%")
    col2.metric(label="Total Long", value=total_long)
    col3.metric(label="Total Short", value=total_short)
    col4.metric(label="Accuracy Long", value=f"{accuracy_long:.2%}")
    col5.metric(label="Accuracy Short", value=f"{accuracy_short:.2%}")


def render_close_types(summary_results):
    st.write("#### Close Types")
    close_types = summary_results.get('close_types', {})
    st.metric(label="TAKE PROFIT", value=f"{close_types.get('TAKE_PROFIT', 0)}")
    st.metric(label="TRAILING STOP", value=f"{close_types.get('TRAILING_STOP', 0)}")
    st.metric(label="STOP LOSS", value=f"{close_types.get('STOP_LOSS', 0)}")
    st.metric(label="TIME LIMIT", value=f"{close_types.get('TIME_LIMIT', 0)}")
    st.metric(label="EARLY STOP", value=f"{close_types.get('EARLY_STOP', 0)}")
``` 


