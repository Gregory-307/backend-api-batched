from typing import Any, Dict
import logging

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from .candles import get_candlestick_trace
from .executors import add_executors_trace
from .pnl import get_pnl_trace
from .theme import get_default_layout


def create_backtesting_figure(
    df: pd.DataFrame,
    executors: list[dict],
    config: Dict[str, Any] | None = None,
    *,
    include_signals: bool = True,  # kept for API compatibility (ignored – markers always shown)
    show_position: bool = True,
    show_duration: bool = False,
    show_order_levels: bool = True,
    marker_scale: float = 1_000,
    extra_orders: pd.DataFrame | None = None,
) -> go.Figure:
    """Return an upgraded back-testing figure matching Tailwind mock-up.

    The main (first) subplot always overlays three traces:
    1. Close price line (gray)
    2. Cumulative PnL (orange, dashed, mapped to secondary y-axis)
    3. Buy / Sell markers (triangle-up / triangle-down, size ~ trade size)

    If *show_position* → extra bar subplot with net quote exposure.
    If *show_duration*  → extra subplot with horizontal bar spanning entry→exit.
    """

    # Determine row structure ------------------------------------------------
    rows = 1
    titles = ["Backtesting Overview"]
    row_heights = [0.65]

    # Prefer Durations row directly below price (if requested)
    if show_duration:
        rows += 1
        titles.append("Durations")
        row_heights.append(0.15)

    # Position row last (if requested)
    if show_position:
        rows += 1
        titles.append("Net Position")
        row_heights.append(0.20)

    # Build specs – secondary_y enabled on first subplot
    specs = [[{"secondary_y": True}]] + [[{}] for _ in range(rows - 1)]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=row_heights,
        subplot_titles=tuple(titles),
        specs=specs,
    )

    # ---------------------------------------------------------------------
    # Row 1 – price, cumulative PnL, buy/sell markers, trade segments
    # ---------------------------------------------------------------------
    # Trade entry→exit coloured segments
    fig = add_executors_trace(fig, executors, row=1, col=1)

    # --- Optional dotted order-levels overlay ----------------------------
    if show_order_levels:
        _add_order_levels(fig, executors, df, row=1)

    # Price candlestick trace
    price_trace = get_candlestick_trace(df)
    fig.add_trace(price_trace, row=1, col=1, secondary_y=False)

    # Optional overlay of CREATE order markers (grey dots)
    if extra_orders is not None and not extra_orders.empty:
        try:
            xs = pd.to_datetime(extra_orders["timestamp"], unit="s")
            ys = pd.to_numeric(extra_orders["created_price"], errors="coerce")
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    marker=dict(symbol="circle", color="#9CA3AF", size=6, opacity=0.6),
                    name="Quote",
                ),
                row=1,
                col=1,
            )
            # Reference price markers (if column present)
            if "reference_price" in extra_orders.columns:
                ref_y = pd.to_numeric(extra_orders["reference_price"], errors="coerce")
                fig.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ref_y,
                        mode="markers",
                        marker=dict(symbol="x", color="#FCD34D", size=6, opacity=0.7),  # yellow x
                        name="RefPrice",
                    ),
                    row=1,
                    col=1,
                )
        except Exception as e:
            logging.error(f"Could not plot extra order markers: {e}")

    # PnL trace (secondary y-axis)
    pnl_trace = get_pnl_trace(executors)
    # Ensure colour & style as per spec
    pnl_trace.update(line=dict(color="#FDE047", dash="dash"))  # amber-300 dashed
    fig.add_trace(pnl_trace, row=1, col=1, secondary_y=True)
    fig.update_yaxes(showgrid=False, row=1, col=1, secondary_y=True)

    # Buy / Sell entry markers and close (exit) X markers sized by trade quote amount
    buy_tr, sell_tr, close_tr = _get_marker_traces(executors, marker_scale=marker_scale)
    fig.add_trace(buy_tr, row=1, col=1, secondary_y=False)
    fig.add_trace(sell_tr, row=1, col=1, secondary_y=False)
    fig.add_trace(close_tr, row=1, col=1, secondary_y=False)

    # Axis titles for first subplot
    fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Cum PNL", row=1, col=1, secondary_y=True)

    current_row = 2  # row index after price subplot

    # ------------------------------------------------------------------
    # Duration bar subplot ---------------------------------------------
    # ------------------------------------------------------------------
    if show_duration:
        _add_duration_bar(fig, executors, row=current_row)
        current_row += 1  # move to next row index

    # Position bar subplot ---------------------------------------------
    if show_position:
        _add_position_bar(fig, df, executors, row=current_row)

    # ------------------------------------------------------------------
    # Layout ----------------------------------------------------------------
    layout = get_default_layout(title=f"Trading Pair: {config.get('trading_pair', 'N/A')}" if config else None)
    layout["showlegend"] = False
    fig.update_layout(**layout)

    fig.update_xaxes(rangeslider_visible=False, row=1, col=1, showgrid=False)

    # Adaptive figure height
    base_h = 500
    if show_duration:
        base_h += 100
    if show_position:
        base_h += 120
    fig.update_layout(height=base_h)

    return fig


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_marker_traces(executors: list[dict], *, marker_scale: float = 1_000):
    """Return buy, sell, and close (exit) marker traces overlayed on price chart."""
    buy_x, buy_y, buy_size = [], [], []
    sell_x, sell_y, sell_size = [], [], []
    close_x, close_y, close_size = [], [], []

    for exe in executors:
        ts_entry = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        price_entry = exe.get("entry_price") or exe.get("custom_info", {}).get("current_position_average_price")
        if price_entry is None:
            continue

        filled = exe.get("filled_amount_quote", 0) or 0
        if filled == 0:
            continue  # unexecuted

        size = filled
        try:
            size_scaled = max(6, min(24, float(size) / marker_scale))
        except Exception:
            size_scaled = 8

        if exe.get("filled_amount_quote", 0) == 0:
            continue
        side = _classify_side(exe)

        if side == "buy":
            buy_x.append(ts_entry)
            buy_y.append(price_entry)
            buy_size.append(size_scaled)
        else:
            sell_x.append(ts_entry)
            sell_y.append(price_entry)
            sell_size.append(size_scaled)

        # Exit (close) marker
        if exe.get("close_timestamp"):
            ts_exit = pd.to_datetime(exe["close_timestamp"], unit="s")
            exit_price = exe.get("custom_info", {}).get("close_price", exe.get("exit_price", price_entry))
            close_x.append(ts_exit)
            close_y.append(exit_price)
            close_size.append(size_scaled)

    buy_trace = go.Scatter(
        x=buy_x,
        y=buy_y,
        mode="markers",
        marker=dict(symbol="triangle-up", color="#10B981", size=buy_size or 8),  # emerald-500
        name="Buy",
    )

    sell_trace = go.Scatter(
        x=sell_x,
        y=sell_y,
        mode="markers",
        marker=dict(symbol="triangle-down", color="#EF4444", size=sell_size or 8),  # red-500
        name="Sell",
    )

    close_trace = go.Scatter(
        x=close_x,
        y=close_y,
        mode="markers",
        marker=dict(symbol="x", color="#F59E0B", size=close_size or 8),  # amber-500 X
        name="Close",
    )

    return buy_trace, sell_trace, close_trace


def _add_position_bar(fig: go.Figure, df: pd.DataFrame, executors: list[dict], *, row: int):
    """Append net quote position bar subplot to *fig* at given *row*."""
    events = []
    for exe in executors:
        ts_entry = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        ts_exit = pd.to_datetime(exe.get("close_timestamp", None), unit="s") if exe.get("close_timestamp") else None
        size = float(exe.get("filled_amount_quote", 0))
        if size == 0:
            continue
        side = _classify_side(exe)
        signed = size if side == "buy" else -size
        events.append((ts_entry, signed))
        if ts_exit is not None:
            events.append((ts_exit, -signed))

    if not events:
        return

    ev_df = (
        pd.DataFrame(events, columns=["ts", "delta"])
        .groupby("ts", as_index=True)["delta"].sum()
        .sort_index()
    )
    # Ensure unique index (pandas cannot reindex with duplicates)
    ev_df = ev_df[~ev_df.index.duplicated(keep="last")]
    cum_series = ev_df.cumsum()

    if isinstance(df, pd.DataFrame) and "timestamp" in df.columns:
        grid = pd.to_datetime(df["timestamp"], unit="s").sort_values().unique()
    elif isinstance(df.index, pd.DatetimeIndex) and not df.index.empty:
        grid = df.index.sort_values().unique()
    else:
        # fallback: use timestamps from events themselves
        grid = pd.to_datetime(sorted(ev_df.index.unique()))

    pos_on_grid = cum_series.reindex(grid, method="ffill").fillna(0)

    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in pos_on_grid]

    fig.add_trace(
        go.Bar(x=grid, y=pos_on_grid.values, marker_color=colors, name="Net Position"),
        row=row,
        col=1,
    )

    max_abs = max(abs(pos_on_grid.min()), abs(pos_on_grid.max()))
    ylim = max_abs * 1.1 if max_abs else 1
    fig.update_yaxes(
        title_text="Net Quote",
        zeroline=True,
        zerolinecolor="#6B7280",
        range=[-ylim, ylim],
        row=row,
        col=1,
    )


def _add_duration_bar(fig: go.Figure, executors: list[dict], *, row: int):
    """Append a horizontal bar per trade spanning entry → exit."""
    for exe in executors:
        entry_ts = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        exit_ts = pd.to_datetime(exe.get("close_timestamp", entry_ts), unit="s")
        if exe.get("filled_amount_quote", 0) == 0:
            continue
        side = _classify_side(exe)
        color = "rgba(16, 185, 129, 0.6)" if side == "buy" else "rgba(239, 68, 68, 0.6)"

        fig.add_trace(
            go.Scatter(
                x=[entry_ts, exit_ts],
                y=[0, 0],
                mode="lines",
                line=dict(color=color, width=2),
                showlegend=False,
            ),
            row=row,
            col=1,
        )

    fig.update_yaxes(visible=False, row=row, col=1)


# Local side classifier (buy / sell)
def _classify_side(exe: dict) -> str:
    side_val = exe.get("config", {}).get("side", "buy")
    if isinstance(side_val, (int, float)):
        return "buy" if int(side_val) == 1 else "sell"
    return str(side_val).lower()


# ---------------------------------------------------------------------------
# New helper: dotted order levels
# ---------------------------------------------------------------------------

def _add_order_levels(fig: go.Figure, executors: list[dict], df: pd.DataFrame, *, row: int = 1):
    """Overlay dotted grey horizontal lines representing order prices active between entry → exit.

    Instead of a full-width horizontal line, draw a line segment starting at the order
    entry timestamp and ending when the executor closes (or end of data if still open).
    """

    # Determine global end-timestamp for open trades (fallback: last candle)
    if isinstance(df.index, pd.DatetimeIndex):
        global_end = df.index.max()
    elif "timestamp" in df.columns:
        global_end = pd.to_datetime(df["timestamp"].max(), unit="s")
    else:
        global_end = None

    for exe in executors:
        entry_ts = pd.to_datetime(exe.get("timestamp") or exe.get("entry_timestamp"), unit="s")
        if pd.isna(entry_ts):
            continue

        exit_ts_raw = exe.get("close_timestamp") or exe.get("exit_timestamp")
        exit_ts = pd.to_datetime(exit_ts_raw, unit="s") if exit_ts_raw else global_end

        # Collect order price levels for this executor
        levels: list[float] = []
        if "prices" in exe and isinstance(exe["prices"], (list, tuple)):
            levels.extend(exe["prices"])
        elif "custom_info" in exe and isinstance(exe["custom_info"], dict) and "prices" in exe["custom_info"]:
            levels.extend(exe["custom_info"]["prices"])
        else:
            ep = exe.get("entry_price")
            if ep is not None:
                levels.append(ep)

        for price in levels:
            fig.add_shape(
                type="line",
                x0=entry_ts,
                x1=exit_ts,
                y0=price,
                y1=price,
                xref="x",
                yref="y",
                line=dict(color="#9CA3AF", dash="dot", width=1),  # gray-400
                row=row,
                col=1,
                layer="below",
            ) 