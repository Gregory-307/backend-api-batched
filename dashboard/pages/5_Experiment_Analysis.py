import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px

from hb_components import (
    create_backtesting_figure,
    render_backtesting_metrics,
    render_accuracy_metrics,
    render_close_types,
)
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
# CSS overrides
try:
    from .. import theme_overrides  # noqa: F401
except ImportError:
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    importlib.import_module("dashboard.theme_overrides")

# Index helper to avoid scanning every JSON
try:
    from ..packet_index import load_index, load_packet  # type: ignore
except ImportError:
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_index, load_packet = importlib.import_module("dashboard.packet_index").load_index, importlib.import_module("dashboard.packet_index").load_packet

st.set_page_config(page_title="Experiment Analysis", layout="wide")
st.title("🔬 Experiment Analysis")

# Determine detail directory based on currently selected CSV
csv_path = Path(st.session_state.get("file_choice", ""))
csv_stem = csv_path.stem if csv_path else "unknown"
detail_dir = Path("results/detail_packets") / csv_stem

# Load index & filter
idx_df = load_index(detail_dir)
if idx_df.empty:
    st.warning("No index file found. Run batch tester first to generate detail packets.")
    st.stop()

labels = idx_df[idx_df["valid"].isin([1, "1", True])]["label"].tolist()

# Intersect with current CSV selected in session
if "available_labels" in st.session_state and st.session_state.available_labels:
    csv_set = set(st.session_state.available_labels)
    labels = [lbl for lbl in labels if lbl in csv_set]

if not labels:
    st.warning("No valid detail packets matching current CSV selection.")
    st.stop()

selected = st.sidebar.selectbox("Choose run label", labels)

# Load packet lazily
try:
    data = load_packet(selected, detail_dir)
    if "results" not in data or not data.get("results"):
        error_msg = data.get("error", "Packet is missing 'results' data or results are empty.")
        raw_response = data.get("raw")
        st.error(f"Could not process run {selected}: {error_msg}")
        if raw_response:
            with st.expander("Show raw server response"):
                st.code(raw_response, language='text')
        st.stop()

except Exception as exc:
    st.error(f"Could not load detail packet: {exc}")
    st.stop()

# KPI cards
render_backtesting_metrics(data["results"], title=f"Metrics – {selected}")
render_accuracy_metrics(data["results"])
render_close_types(data["results"])

# Show run parameters if available
if "config" in data and data["config"]:
    # Display compact one-liner of key parameters (spreads, leverage, etc.)
    key_fields = [
        "controller_name",
        "buy_spreads",
        "sell_spreads",
        "leverage",
        "total_amount_quote",
        "stop_loss",
        "take_profit",
        "time_limit",
    ]
    compact = {k: v for k, v in data["config"].items() if k in key_fields and v not in (None, "", [])}
    with st.expander("Run configuration from packet"):
        st.write(", ".join(f"{k}={v}" for k, v in compact.items()))
        st.json(data["config"], expanded=False)

# Figure
df_feat = pd.DataFrame(data["processed_data"])
event_df = None
if "event_log_csv" in data:
    try:
        ev_path = Path(data["event_log_csv"])
        if ev_path.exists():
            event_df = pd.read_csv(ev_path)
    except Exception:
        pass

if event_df is not None:
    order_creates = event_df[event_df["event_type"] == "CREATE"]
else:
    order_creates = None

fig = create_backtesting_figure(
    df_feat,
    data["executors"],
    {"trading_pair": data["results"].get("market", "N/A")},
    include_signals=True,
    extra_orders=order_creates,
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Configuration parameters (if CSV row available)
# ---------------------------------------------------------------------------

csv_path = Path(st.session_state.get("file_choice", ""))
if csv_path.exists():
    try:
        df_csv = pd.read_csv(csv_path)
        row_cfg = df_csv[df_csv.get("label") == selected]
        if not row_cfg.empty:
            row_dict = row_cfg.iloc[0].to_dict()
            if not (len(row_dict) == 1 and "error" in row_dict):
                st.subheader("Run parameters from CSV")
                st.json(row_dict, expanded=False)
    except Exception:
        pass

# Raw executors table
st.header("Executors")
exec_df = pd.json_normalize(data["executors"])
st.dataframe(exec_df, use_container_width=True, height=400)

# NEW SECTION – Trade Log Table & Win/Loss Metrics
# -------------------------------------------------
trade_rows = []
cumulative_pos = 0.0
for ex in sorted(data.get("executors", []), key=lambda e: e.get("close_timestamp", e.get("timestamp", 0))):
    filled_quote = ex.get("filled_amount_quote", 0) or ex.get("order_size_quote", 0)
    if filled_quote == 0:
        continue  # skip zero-volume orders
    side_val = ex.get("side", ex.get("config", {}).get("side", 1))
    is_buy = int(side_val) == 1 if isinstance(side_val, (int, float)) else str(side_val).lower() == "buy"
    signed_size = filled_quote if is_buy else -filled_quote
    cumulative_pos += signed_size

    timestamp = pd.to_datetime(
        ex.get("close_timestamp", ex.get("timestamp", 0)), unit="s"
    ).isoformat()

    trade_rows.append(
        {
            "Time": timestamp,
            "Side": "BUY" if is_buy else "SELL",
            "Size (quote)": filled_quote,
            "Price": ex.get("config", {}).get("entry_price", ex.get("entry_price")),
            "P/L": ex.get("net_pnl_quote", 0),
            "Cum Pos": cumulative_pos,
        }
    )

# Convert to DataFrame
trade_df = pd.DataFrame(trade_rows)

if not trade_df.empty:
    st.header("Detailed Trade Log")

    # Win/Loss KPI metrics
    pnls_numeric = pd.to_numeric(trade_df["P/L"], errors="coerce").fillna(0)
    wins = (pnls_numeric > 0).sum()
    losses = (pnls_numeric < 0).sum()
    win_rate = wins / (wins + losses) if (wins + losses) else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Trades", f"{len(trade_df):,}")
    m2.metric("Winning Trades", f"{wins:,}")
    m3.metric("Win Rate", f"{win_rate*100:.1f}%")

    # --- AgGrid Styling --------------------------------------------------
    gb = GridOptionsBuilder.from_dataframe(trade_df)
    gb.configure_default_column(sortable=True, resizable=True, filter=True)

    # Side badge renderer
    side_renderer = JsCode(
        """
        function(params) {
            if (params.value === 'BUY') {
                return `<span class="badge-buy">BUY</span>`;
            } else {
                return `<span class="badge-sell">SELL</span>`;
            }
        }
        """
    )
    gb.configure_column("Side", cellRenderer=side_renderer, filter=False)

    # Price & P/L formatters
    gb.configure_column(
        "Price",
        valueFormatter="(params.value === undefined) ? '' : `$${params.value.toFixed(2)}`"
    )
    pnl_color_js = JsCode(
        """
        function(params) {
            if (params.value > 0) return { 'color': '#10B981', 'fontWeight': 'bold' };
            if (params.value < 0) return { 'color': '#EF4444', 'fontWeight': 'bold' };
        }
        """
    )
    gb.configure_column(
        "P/L",
        type=["numericColumn", "valueColumn"],
        cellStyle=pnl_color_js,
        valueFormatter="(params.value === undefined) ? '' : `$${params.value.toFixed(2)}`"
    )

    grid_options = gb.build()
    AgGrid(
        trade_df,
        gridOptions=grid_options,
        theme="streamlit",
        height=400,
        allow_unsafe_jscode=True,
    )
else:
    st.info("No trade data available for this run.") 