import pandas as pd
import plotly.graph_objects as go


def get_bt_candlestick_trace(df: pd.DataFrame) -> go.Scatter:
    """Return a lightweight line trace (close price) for back-test candle data.

    Accepts DataFrame with at least columns ['timestamp', 'close'].
    """
    if "timestamp" in df.columns:
        df = df.copy()
        df.index = pd.to_datetime(df["timestamp"], unit="s")
    # Neutral gray price line for dark theme
    color = "#9CA3AF"  # gray-400
    return go.Scatter(x=df.index, y=df["close"], mode="lines", line=dict(color=color), name="Price")

def get_candlestick_trace(df: pd.DataFrame) -> go.Candlestick:
    """Return Plotly Candlestick trace from DataFrame with ['open','high','low','close'] columns.

    Index is expected to be datetime (or we coerce timestamp column).
    """
    if "timestamp" in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df["timestamp"], unit="s")

    return go.Candlestick(x=df.index,
                          open=df["open"],
                          high=df["high"],
                          low=df["low"],
                          close=df["close"],
                          name="Candlestick",
                          increasing_line_color="#2ECC71",
                          decreasing_line_color="#E74C3C") 