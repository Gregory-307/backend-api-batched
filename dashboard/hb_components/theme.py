from typing import Dict, Any


def get_color_scheme() -> Dict[str, str]:
    """Centralised colour palette (dark theme)."""
    return {
        "price": "#1E90FF",  # dodger blue
        "buy": "#32CD32",  # lime green
        "sell": "#FF6347",  # tomato red
        "buy_signal": "#1E90FF",
        "sell_signal": "#FF0000",
        "upper_band": "#4682B4",
        "middle_band": "#708090",
        "lower_band": "#A9A9A9",
        "volume": "#7FDBFF",
        "macd_line": "#FFD700",
        "macd_signal": "#FF8C00",
    }


def get_default_layout(title: str | None = None, *, height: int | None = None, width: int | None = None) -> Dict[str, Any]:
    """Return a Plotly `layout` dict with a dark background and our palette."""
    layout: Dict[str, Any] = {
        "template": "plotly_dark",
        "plot_bgcolor": "rgba(0, 0, 0, 0)",
        "paper_bgcolor": "rgba(0, 0, 0, 0.9)",
        "font": {"color": "white", "size": 12},
        "margin": dict(l=40, r=20, t=40, b=40),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    }
    if title:
        layout["title"] = title
    if height:
        layout["height"] = height
    if width:
        layout["width"] = width
    return layout 