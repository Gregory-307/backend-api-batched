from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def get_pnl_trace(executors: List[dict]) -> go.Scatter:
    """Return cumulative PnL trace from executor list."""
    if not executors:
        return go.Scatter()
    pnl = np.array([e.get("net_pnl_quote", 0) for e in executors], dtype=float)
    cum_pnl = np.cumsum(pnl)
    times = pd.to_datetime([e.get("close_timestamp", e.get("timestamp")) for e in executors], unit="s")
    return go.Scatter(
        x=times,
        y=cum_pnl,
        mode="lines",
        line=dict(color="#FDE047", dash="dash", shape="hv"),
        name="Cum PNL",
    ) 