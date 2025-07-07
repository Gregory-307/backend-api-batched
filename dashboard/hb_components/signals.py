import pandas as pd
import plotly.graph_objects as go
from typing import List, Tuple


def classify_side(exe: dict) -> str:
    """Return 'buy' or 'sell' from executor dict."""
    side_val = exe.get("config", {}).get("side", "buy")
    if isinstance(side_val, (int, float)):
        return "buy" if int(side_val) == 1 else "sell"
    return str(side_val).lower()


def get_signal_traces(executors: List[dict], *, marker_scale: float = 1_000) -> Tuple[go.Scatter, go.Scatter]:
    """Return two scatter traces for buy and sell signals on a flat row.

    *marker_scale* controls how `filled_amount_quote` is mapped to marker size.
    Rough mapping: size_px ≈ (filled_quote / marker_scale) but clamped to 6–24 px.
    """
    buy_ts, sell_ts, buy_size, sell_size = [], [], [], []
    for exe in executors:
        ts = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        size = exe.get("filled_amount_quote", 0) or exe.get("order_size_quote", 0)
        try:
            size_scaled = max(6, min(24, float(size) / marker_scale))
        except Exception:
            size_scaled = 8
        if classify_side(exe) == "buy":
            buy_ts.append(ts)
            buy_size.append(size_scaled)
        else:
            sell_ts.append(ts)
            sell_size.append(size_scaled)

    y_const_buy = [0] * len(buy_ts)
    y_const_sell = [0] * len(sell_ts)

    buy_trace = go.Scatter(x=buy_ts, y=y_const_buy, mode="markers",
                           marker=dict(symbol="triangle-up", color="lime", size=buy_size or 8),
                           name="Buy signals")
    sell_trace = go.Scatter(x=sell_ts, y=y_const_sell, mode="markers",
                            marker=dict(symbol="triangle-down", color="red", size=sell_size or 8),
                            name="Sell signals")
    return buy_trace, sell_trace 