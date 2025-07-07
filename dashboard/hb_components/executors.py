from typing import List

import pandas as pd
import plotly.graph_objects as go


# Reuse classification helper from signals module (avoids duplication)
try:
    from .signals import classify_side  # type: ignore
except Exception:
    def classify_side(exe):
        side_val = exe.get("config", {}).get("side", "buy")
        if isinstance(side_val, (int, float)):
            return "buy" if int(side_val) == 1 else "sell"
        return str(side_val).lower()


def add_executors_trace(fig: go.Figure, executors: List[dict], *, row: int = 1, col: int = 1) -> go.Figure:
    """Overlay coloured entry→exit segments for each executor on *fig*.

    `executors` is the list returned from /run-backtesting (each already a dict).
    """
    for exe in executors:
        if exe.get("filled_amount_quote", 0) == 0:
            continue  # skip not-executed orders

        entry_ts = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        exit_ts = pd.to_datetime(exe.get("close_timestamp", entry_ts), unit="s")
        entry_price = exe.get("custom_info", {}).get("current_position_average_price", exe.get("entry_price"))
        exit_price = exe.get("custom_info", {}).get("close_price", entry_price)
        side = classify_side(exe)
        color = "#10B981" if side == "buy" else "#EF4444"  # Tailwind emerald/red
        fig.add_trace(
            go.Scatter(
                x=[entry_ts, exit_ts],
                y=[entry_price, exit_price],
                mode="lines",
                line=dict(color=color, width=1),
                showlegend=False,
            ),
            row=row,
            col=col,
        )
    return fig 