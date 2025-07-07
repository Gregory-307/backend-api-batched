"""Lightweight subset of Hummingbot dashboard visual components vendored locally.

Only the helpers needed by our Streamlit pages are included.  If you need more,
copy the required module into this package and add its public symbols to
__all__."""

from .candles import get_bt_candlestick_trace  # noqa: F401
from .candles import get_candlestick_trace  # noqa: F401
from .executors import add_executors_trace  # noqa: F401
from .pnl import get_pnl_trace  # noqa: F401
from .backtesting import create_backtesting_figure  # noqa: F401
from .backtesting_metrics import (
    render_backtesting_metrics,  # noqa: F401
    render_accuracy_metrics,  # noqa: F401
    render_close_types,  # noqa: F401
)

__all__ = [
    "get_bt_candlestick_trace",
    "get_candlestick_trace",
    "add_executors_trace",
    "get_pnl_trace",
    "create_backtesting_figure",
    "render_backtesting_metrics",
    "render_accuracy_metrics",
    "render_close_types",
] 