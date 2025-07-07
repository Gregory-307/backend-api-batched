## 6. frontend/visualization/executors_distribution.py

**Description**: Generate mirrored bar chart comparing buy vs sell order distributions by spread.

**Exports**: `create_executors_distribution_traces`

**Tags**: bar

```python
import numpy as np
import plotly.graph_objects as go

import frontend.visualization.theme as theme


def create_executors_distribution_traces(buy_spreads, sell_spreads, buy_amounts_pct, sell_amounts_pct,
                                         total_amount_quote):
    colors = theme.get_color_scheme()

    buy_spread_distributions = [spread * 100 for spread in buy_spreads]
    sell_spread_distributions = [spread * 100 for spread in sell_spreads]
    buy_order_amounts_quote = [amount * total_amount_quote for amount in buy_amounts_pct]
    sell_order_amounts_quote = [amount * total_amount_quote for amount in sell_amounts_pct]
    buy_order_levels = len(buy_spread_distributions)
    sell_order_levels = len(sell_spread_distributions)

    # Calculate total volumes
    total_buy_volume = sum(buy_order_amounts_quote)
    total_sell_volume = sum(sell_order_amounts_quote)

    # Create the figure with a dark theme and secondary y-axis
    fig = go.Figure()

    # Buy orders on the negative side of x-axis
    fig.add_trace(go.Bar(
        x=[-dist for dist in buy_spread_distributions],
        y=buy_order_amounts_quote,
        name='Buy Orders',
        marker_color=colors['buy'],
        width=[0.2] * buy_order_levels  # Adjust the width of the bars as needed
    ))

    # Sell orders on the positive side of x-axis
    fig.add_trace(go.Bar(
        x=sell_spread_distributions,
        y=sell_order_amounts_quote,
        name='Sell Orders',
        marker_color=colors['sell'],
        width=[0.2] * sell_order_levels  # Adjust the width of the bars as needed
    ))

    # Add annotations for buy orders
    for i, value in enumerate(buy_order_amounts_quote):
        fig.add_annotation(
            x=-buy_spread_distributions[i],
            y=value + 0.03 * max(buy_order_amounts_quote),  # Offset the text slightly above the bar
            text=str(round(value, 2)),
            showarrow=False,
            font=dict(color=colors['buy'], size=10)
        )

    # Add annotations for sell orders
    for i, value in enumerate(sell_order_amounts_quote):
        fig.add_annotation(
            x=sell_spread_distributions[i],
            y=value + 0.03 * max(sell_order_amounts_quote),  # Offset the text slightly above the bar
            text=str(round(value, 2)),
            showarrow=False,
            font=dict(color=colors['sell'], size=10)
        )

    max_y = max(max(buy_order_amounts_quote), max(sell_order_amounts_quote))
    # Add annotations for total volumes
    fig.add_annotation(
        x=-np.mean(buy_spread_distributions),
        y=max_y,
        text=f'Total Buy\n{round(total_buy_volume, 2)}',
        showarrow=False,
        font=dict(color=colors['buy'], size=12, family="Arial Black"),
        align='center'
    )

    fig.add_annotation(
        x=np.mean(sell_spread_distributions),
        y=max_y,
        text=f'Total Sell\n{round(total_sell_volume, 2)}',
        showarrow=False,
        font=dict(color=colors['sell'], size=12, family="Arial Black"),
        align='center'
    )

    # Apply the theme layout
    layout_settings = theme.get_default_layout("Market Maker Order Distribution")
    fig.update_layout(**layout_settings)
    fig.update_layout(
        xaxis_title="Spread (%)",
        yaxis_title="Order Amount (Quote)",
        bargap=0.1,  # Adjust the gap between the bars
        barmode='relative',  # Stack the bars on top of each other
        showlegend=True,
        height=600
    )
    return fig
```

---

## 7. frontend/visualization/indicators.py

**Description**: Utility to add BBands, Volume, MACD and SuperTrend traces on price charts.

**Exports**: `get_bbands_traces`, `get_volume_trace`, `get_macd_traces`, `get_supertrend_traces`

**Tags**: indicator

```python
import pandas as pd
import pandas_ta as ta  # noqa: F401
import plotly.graph_objects as go

from frontend.visualization import theme


def get_bbands_traces(df, bb_length, bb_std):
    tech_colors = theme.get_color_scheme()
    df.ta.bbands(length=bb_length, std=bb_std, append=True)
    bb_lower = f'BBL_{bb_length}_{bb_std}'
    bb_middle = f'BBM_{bb_length}_{bb_std}'
    bb_upper = f'BBU_{bb_length}_{bb_std}'
    traces = [
        go.Scatter(x=df.index, y=df[bb_upper], line=dict(color=tech_colors['upper_band']),
                   name='Upper Band'),
        go.Scatter(x=df.index, y=df[bb_middle], line=dict(color=tech_colors['middle_band']),
                   name='Middle Band'),
        go.Scatter(x=df.index, y=df[bb_lower], line=dict(color=tech_colors['lower_band']),
                   name='Lower Band'),
    ]
    return traces


def get_volume_trace(df):
    df.index = pd.to_datetime(df.timestamp, unit='s')
    return go.Bar(x=df.index, y=df['volume'], name="Volume", marker_color=theme.get_color_scheme()["volume"],
                  opacity=0.7)


def get_macd_traces(df, macd_fast, macd_slow, macd_signal):
    tech_colors = theme.get_color_scheme()
    df.ta.macd(fast=macd_fast, slow=macd_slow, signal=macd_signal, append=True)
    macd = f'MACD_{macd_fast}_{macd_slow}_{macd_signal}'
    macd_s = f'MACDs_{macd_fast}_{macd_slow}_{macd_signal}'
    macd_hist = f'MACDh_{macd_fast}_{macd_slow}_{macd_signal}'
    traces = [
        go.Scatter(x=df.index, y=df[macd], line=dict(color=tech_colors['macd_line']),
                   name='MACD Line'),
        go.Scatter(x=df.index, y=df[macd_s], line=dict(color=tech_colors['macd_signal']),
                   name='MACD Signal'),
        go.Bar(x=df.index, y=df[macd_hist], name='MACD Histogram',
               marker_color=df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"].apply(
                   lambda x: '#FF6347' if x < 0 else '#32CD32'))
    ]
    return traces


def get_supertrend_traces(df, length, multiplier):
    tech_colors = theme.get_color_scheme()
    df.ta.supertrend(length=length, multiplier=multiplier, append=True)
    supertrend_d = f'SUPERTd_{length}_{multiplier}'
    supertrend = f'SUPERT_{length}_{multiplier}'
    df = df[df[supertrend] > 0]

    # Create segments for line with different colors
    segments = []
    current_segment = {"x": [], "y": [], "color": None}

    for i in range(len(df)):
        if i == 0 or df[supertrend_d].iloc[i] == df[supertrend_d].iloc[i - 1]:
            current_segment["x"].append(df.index[i])
            current_segment["y"].append(df[supertrend].iloc[i])
            current_segment["color"] = tech_colors['buy'] if df[supertrend_d].iloc[i] == 1 else tech_colors['sell']
        else:
            segments.append(current_segment)
            current_segment = {"x": [df.index[i - 1], df.index[i]],
                               "y": [df[supertrend].iloc[i - 1], df[supertrend].iloc[i]],
                               "color": tech_colors['buy'] if df[supertrend_d].iloc[i] == 1 else tech_colors['sell']}

    segments.append(current_segment)

    # Create traces from segments
    traces = [
        go.Scatter(
            x=segment["x"],
            y=segment["y"],
            mode='lines',
            line=dict(color=segment["color"], width=2),
            name='SuperTrend'
        ) for segment in segments
    ]

    return traces
```

---

## 8. frontend/visualization/performance_dca.py

**Description**: Streamlit panels and charts analysing DCA strategy performance (pie, bar + metrics).

**Exports**: `display_dca_tab`, `get_dca_inputs`, `display_dca_performance`, `custom_sort`

**Tags**: pie, bar, kpi

```python
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.st_utils import get_backend_api_client
from frontend.visualization.dca_builder import create_dca_graph

backend_api = get_backend_api_client()


def display_dca_tab(config_type, config):
    if config_type != "dca":
        st.info("No DCA configuration available for this controller.")
    else:
        dca_inputs, dca_amount = get_dca_inputs(config)
        fig = create_dca_graph(dca_inputs, dca_amount)
        st.plotly_chart(fig, use_container_width=True)


def get_dca_inputs(config: dict):
    take_profit = config.get("take_profit", 0.0)
    dca_amounts_key = "dca_amounts_pct" if config["controller_type"] == "directional_trading" else "dca_amounts"
    if take_profit is None:
        take_profit = config["trailing_stop"]["activation_price"]
    dca_inputs = {
        "dca_spreads": config.get("dca_spreads", []),
        "dca_amounts": config.get(dca_amounts_key, []),
        "stop_loss": config.get("stop_loss", 0.0),
        "take_profit": take_profit,
        "time_limit": config.get("time_limit", 0.0),
        "buy_amounts_pct": config.get("buy_amounts_pct", []),
        "sell_amounts_pct": config.get("sell_amounts_pct", [])
    }
    dca_amount = config["total_amount_quote"]
    return dca_inputs, dca_amount


`` (truncated for brevity in preview; full code included in file) 
```  
*Note: file continues with pie/bar chart creation and helper `custom_sort`*  

---

## 9. frontend/visualization/dca_builder.py

**Description**: Construct multi-axis bar / line figure visualising DCA spreads, orders and unrealised PnL.

**Exports**: `calculate_unrealized_pnl`, `create_dca_graph`

**Tags**: bar

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import frontend.visualization.theme as theme


def calculate_unrealized_pnl(spreads, break_even_values, accumulated_amount):
    unrealized_pnl = []
    for i in range(len(spreads)):
        distance = abs(spreads[i] - break_even_values[i])
        pnl = accumulated_amount[i] * distance / 100  # PNL calculation
        unrealized_pnl.append(pnl)
    return unrealized_pnl


# create_dca_graph(...) full implementation includes order bars, cumulative amount, unrealised PnL bars,
# breakeven / TP / SL horizontal lines, and rich annotations.
```

---

## 10. frontend/visualization/performance_etl.py

**Description**: Sidebar tool for selecting databases and creating checkpoints before analysis.

**Exports**: `display_etl_section`, `fetch_checkpoint_data`

**Tags**: sidebar

```python
import json

import streamlit as st

from backend.services.backend_api_client import BackendAPIClient


def display_etl_section(backend_api: BackendAPIClient):
    db_paths = backend_api.list_databases()
    dbs_dict = backend_api.read_databases(db_paths)
    healthy_dbs = [db["db_path"].replace("sqlite:///", "") for db in dbs_dict if db["healthy"]]
    with st.expander("ETL Tool"):
        st.markdown("""
        In this tool, you can easily fetch and combine different databases. Just follow these simple steps:
        - Choose the ones you want to analyze (only non-corrupt databases are available)
        - Merge them into a checkpoint
        - Start analyzing
        """)
        if len(healthy_dbs) == 0:
            st.warning(
                "Oops, it looks like there are no databases here. If you uploaded a file and it's not showing up, "
                "you can check the status report.")
            st.dataframe([db["status"] for db in dbs_dict], use_container_width=True)
        else:
            st.markdown("#### Select Databases to Merge")
            selected_dbs = st.multiselect("Choose the databases you want to merge", healthy_dbs,
                                          label_visibility="collapsed")
            if len(selected_dbs) == 0:
                st.warning("No databases selected. Please select at least one database.")
            else:
                st.markdown("#### Create Checkpoint")
                if st.button("Save"):
                    response = backend_api.create_checkpoint(selected_dbs)
                    if response["message"] == "Checkpoint created successfully.":
                        st.success("Checkpoint created successfully!")
                    else:
                        st.error("Error creating checkpoint. Please try again.")
    checkpoints_list = backend_api.list_checkpoints(full_path=True)
    if len(checkpoints_list) == 0:
        st.warning("No checkpoints detected. Please create a new one to continue.")
        st.stop()
    else:
        selected_checkpoint = st.selectbox("Select a checkpoint to load", checkpoints_list)
        checkpoint_data = fetch_checkpoint_data(backend_api, selected_checkpoint)
        checkpoint_data["executors"] = json.loads(checkpoint_data["executors"])
        checkpoint_data["orders"] = json.loads(checkpoint_data["orders"])
        checkpoint_data["trade_fill"] = json.loads(checkpoint_data["trade_fill"])
        checkpoint_data["controllers"] = json.loads(checkpoint_data["controllers"])
        return checkpoint_data


@st.cache_data
def fetch_checkpoint_data(_backend_api: BackendAPIClient, selected_checkpoint: str):
    checkpoint_data = _backend_api.load_checkpoint(selected_checkpoint)
    return checkpoint_data
``` 