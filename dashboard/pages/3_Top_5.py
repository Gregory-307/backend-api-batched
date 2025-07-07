import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from pathlib import Path
import json

# Ensure CSS overrides
try:
    from .. import theme_overrides  # noqa: F401
except ImportError:
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    importlib.import_module("dashboard.theme_overrides")

from hb_components import create_backtesting_figure, render_backtesting_metrics

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Top 5", layout="wide")
st.title("🏅 Top 5")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading data...")
def load_df(path: Path) -> pd.DataFrame:
    """Robust CSV loader that auto-detects header presence (mirrors Overview page)."""

    if not path.exists():
        return pd.DataFrame()

    column_names = [
        'algo', 'label', 'market', 'return_pct', 'net_pnl_quote', 'total_positions',
        'total_trades', 'total_pnl_quote', 'total_buy_trades', 'total_sell_trades',
        'accuracy_long', 'accuracy_short', 'total_volume', 'avg_close_time',
        'avg_profit_per_trade', 'sharpe_ratio', 'profit_factor', 'winning_trades',
        'losing_trades', 'total_open_trades', 'total_closed_trades', 'param_1', 'param_2'
    ]

    def _postprocess(df_in: pd.DataFrame) -> pd.DataFrame:
        df_out = df_in.copy()
        df_out = df_out.loc[:, ~df_out.columns.str.contains('^Unnamed', na=False)]
        df_out.dropna(axis=1, how='all', inplace=True)

        for col in df_out.columns:
            try:
                df_out[col] = pd.to_numeric(df_out[col])
            except (ValueError, TypeError):
                # This column cannot be converted to numeric, so we leave it as is.
                pass

        if 'label' not in df_out.columns or df_out['label'].isnull().any():
            df_out['label'] = [f"run_{i}" for i in df_out.index]
        return df_out

    def _row0_is_duplicate_header(df_test: pd.DataFrame) -> bool:
        if df_test.empty:
            return False
        header_vals = [str(c).strip().lower() for c in df_test.columns]
        row0_vals = [str(v).strip().lower() for v in df_test.iloc[0].values]
        return header_vals[:3] == row0_vals[:3]

    try:
        df_header = pd.read_csv(path, header=0)
        if _row0_is_duplicate_header(df_header):
            raise ValueError
        df_header = _postprocess(df_header)
        return df_header
    except Exception:
        pass

    # Fallback no-header.
    try:
        df_no_header = pd.read_csv(path, header=None)
        df_no_header.columns = column_names[: len(df_no_header.columns)]
        df_no_header = _postprocess(df_no_header)
        return df_no_header
    except Exception as exc:
        st.error(f"Error loading {path.name}: {exc}")
        return pd.DataFrame()


# Fallback minmax scaling (avoids sklearn dependency)

def _minmax_scale(arr):
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return arr
    min_val = arr.min()
    max_val = arr.max()
    if max_val - min_val == 0:
        return np.zeros_like(arr)
    return (arr - min_val) / (max_val - min_val)


@st.cache_data
def add_mock_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add additional mock metrics used by visualisations."""
    if 'total_trade_volume' not in df.columns:
        df['total_trade_volume'] = [np.random.uniform(10_000, 100_000) for _ in range(len(df))]
    if 'max_drawdown' not in df.columns:
        df['max_drawdown'] = [np.random.uniform(0.05, 0.3) for _ in range(len(df))]

    df['inverse_max_drawdown'] = 1 - df['max_drawdown']
    df['return_over_volume'] = df['net_pnl_quote'] / df['total_trade_volume']
    return df


@st.cache_data
def get_mock_playthrough_data(pnl: float, label: str) -> pd.DataFrame:
    """Generate synthetic price, trade and pnl series (placeholder)."""
    timestamps = pd.to_datetime(np.arange(1, 101), unit='h', origin=pd.Timestamp('2023-01-01'))
    price = 100 + np.random.randn(100).cumsum()

    trade_indices = np.random.choice(range(100), size=20, replace=False)
    sides = np.random.choice(['buy', 'sell'], size=20)

    trades = pd.DataFrame(index=timestamps)
    trades['price'] = price
    trades['side'] = np.nan
    trades.loc[timestamps[trade_indices], 'side'] = sides

    noise = np.random.normal(loc=pnl / (100 * 2), scale=abs(pnl / 20) if pnl != 0 else 1, size=100)
    trades['pnl'] = np.cumsum(noise)

    return trades.reset_index().rename(columns={'index': 'timestamp'})

# ---------------------------------------------------------------------------
# Data – like Overview: we expect session_state.file_choice (CSV)
# ---------------------------------------------------------------------------

if "file_choice" not in st.session_state or not st.session_state.file_choice:
    st.warning("Pick a results CSV on the Overview page first.")
    st.stop()

csv_path = Path(st.session_state.file_choice)
df_summary = load_df(csv_path)

if 'error' in df_summary.columns:
    df_summary = df_summary[df_summary['error'].isna()].copy()

if df_summary.empty:
    st.error("Results CSV contains only failed backtests. Run sweeps again.")
    st.stop()

# KPI for ranking
numeric_cols = df_summary.select_dtypes(include="number").columns.tolist()
rank_kpi = st.sidebar.selectbox("Rank by KPI", options=numeric_cols, index=numeric_cols.index("net_pnl_quote") if "net_pnl_quote" in numeric_cols else 0)

# Get top 5
df_top5 = df_summary.sort_values(rank_kpi, ascending=False).head(5)

st.success(f"Top 5 runs by {rank_kpi} (descending)")

for idx, row in df_top5.iterrows():
    label = row["label"]
    kpi_val = row[rank_kpi]

    st.subheader(f"🏷️ {idx+1}. {label} — {rank_kpi}: {kpi_val:,.4f}")

    # Load detail packet ---------------------------------------------------
    packet_path = Path("results/detail_packets") / csv_path.stem / f"{label}.json"
    if not packet_path.exists():
        st.warning("Detail packet missing – run batch again.")
        continue

    try:
        data = json.loads(packet_path.read_text())
    except json.JSONDecodeError as exc:
        st.warning(f"Malformed detail packet for {label}: {exc}")
        continue

    if "results" not in data or not data.get("results"):
        error_msg = data.get("error", "Packet is missing 'results' data or results are empty.")
        raw_response = data.get("raw")
        st.warning(f"Skipping {label}: {error_msg}")
        if raw_response:
            with st.expander("Show raw server response"):
                st.code(raw_response, language='text')
        continue

    df_feat = pd.DataFrame(data["processed_data"])

    cols_top = st.columns([3, 2])

    # --- Left: Backtesting figure ---------------------------------------
    with cols_top[0]:
        tp = data["results"].get("market", "N/A")
        fig = create_backtesting_figure(
            df_feat,
            data["executors"],
            {"trading_pair": tp},
            extra_orders=pd.read_csv(data["event_log_csv"])[lambda d: d.event_type=="CREATE"] if "event_log_csv" in data else None,
            include_signals=True,
        )
        st.plotly_chart(fig, use_container_width=True, key=f"fig_{label}")

    # --- Right: Metrics & Spider chart ----------------------------------
    with cols_top[1]:
        render_backtesting_metrics(data["results"], title="Metrics")

        # Spider chart for strengths / weaknesses
        st.markdown("### Strengths & Weaknesses")

        # -------------------------------------------------------------
        # Build a richer metric dictionary – derive a few extra KPIs so
        # the radar chart gives a more rounded picture.  All metrics are
        # orientated so **higher is better** to make the plot intuitive.
        # -------------------------------------------------------------
        res = data["results"].copy()

        # 1) Risk-adjusted return — inverse of max drawdown (higher ⇢ lower risk)
        max_dd_pct = res.get("max_drawdown_pct") or res.get("max_drawdown")
        if max_dd_pct not in (None, 0):
            res["inverse_max_drawdown"] = 1 - float(max_dd_pct)

        # 2) Capital efficiency — profit per traded volume
        volume_val = res.get("total_volume") or res.get("total_trade_volume")
        if volume_val not in (None, 0):
            res["return_over_volume"] = float(res.get("net_pnl_quote", 0)) / float(volume_val)

        # 3) Overall accuracy (if separate sides are not present)
        if "accuracy" in res and "accuracy_long" not in res:
            res["accuracy_long"] = res.get("accuracy")

        # -------------------------------------------------------------
        # Select metrics for the radar chart (add/remove here as needed)
        # -------------------------------------------------------------
        spider_metrics = [
            "net_pnl_quote",          # absolute profitability
            "profit_factor",          # ratio of gross profit to gross loss
            "accuracy_long",          # long-side hit rate
            "accuracy_short",         # short-side hit rate (if available)
            "sharpe_ratio",           # risk-adjusted return
            "inverse_max_drawdown",   # 1 − max_drawdown_pct (risk proxy)
            "return_over_volume",     # capital efficiency
        ]

        # Keep only the metrics present in the result set
        spider_metrics = [m for m in spider_metrics if m in res]

        # -----------------------------------------------------------------
        # 1⃣  Scale each metric RELATIVE TO THE WHOLE RESULTS DF  ---------
        #     This avoids one very large metric (e.g. net_pnl_quote)         
        #     dwarfing the others and producing a near-zero polygon.         
        # -----------------------------------------------------------------
        scaled_vals = []
        for m in spider_metrics:
            raw_val = float(res.get(m, 0))
            col = df_summary[m] if m in df_summary.columns else None
            if col is not None and col.nunique(dropna=True) > 1:
                col_min, col_max = col.min(skipna=True), col.max(skipna=True)
                # Protect division by zero
                if col_max - col_min == 0:
                    scaled = 0.5  # neutral centre
                else:
                    scaled = (raw_val - col_min) / (col_max - col_min)
                    scaled = max(0, min(1, scaled))
            else:
                scaled = 0.5
            scaled_vals.append(scaled)
         
        fig_spider = go.Figure(
            data=[
                go.Scatterpolar(
                    r=scaled_vals,
                    theta=spider_metrics,
                    fill="toself",
                    name="scaled 0-1",
                    hovertemplate="%{theta}: %{customdata:.4f}<extra></extra>",
                    customdata=[float(res.get(m, 0)) for m in spider_metrics],
                )
            ]
        )
        fig_spider.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1], dtick=0.25)),
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig_spider, use_container_width=True, key=f"spider_{label}")

    # --- Config / Parameters ------------------------------------------
    with st.expander("Show run parameters"):
        st.json({k: v for k, v in row.items() if k not in (numeric_cols + ["label"])})

    st.markdown("---")

# ---------------------------------------------------------------------------
# End of page content after Top-5 panels
# --------------------------------------------------------------------------- 