import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import json
import logging
from hb_components import create_backtesting_figure
from hb_components.backtesting_metrics import render_backtesting_metrics

# AgGrid
from st_aggrid import AgGrid, GridOptionsBuilder

# Ensure Tailwind CSS overrides are active across pages
try:
    from .. import theme_overrides  # noqa: F401
except ImportError:
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    importlib.import_module("dashboard.theme_overrides")


# ================== TEMP PROFILE BLOCK (remove later) ==================
import time, contextlib, sys
from pathlib import Path

@contextlib.contextmanager
def timer(lbl):
    t0 = time.perf_counter()
    yield
    print(f"[PROFILE] {lbl}: {time.perf_counter() - t0:.2f}s", file=sys.stderr)

results_dir_path = Path(st.session_state.get("results_dir", Path.cwd()))
csv_file_path = Path(st.session_state.get("file_choice", ""))

with timer("CSV discovery"):
    _ = list(results_dir_path.rglob("*results.csv"))

with timer("CSV load"):
    if csv_file_path.is_file():
        _ = pd.read_csv(csv_file_path)

with timer("Packet glob"):
    _ = list(Path("results/detail_packets").glob("*.json"))
# ================= END TEMP PROFILE BLOCK =================

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Experiments Overview", layout="wide")
st.title("📊 Experiments Overview")

# ---------------------------------------------------------------------------
# Ensure session_state keys exist before any helper uses them
# ---------------------------------------------------------------------------
if "results_dir" not in st.session_state:
    default_dir = Path("results/summaries") if Path("results/summaries").is_dir() else Path.cwd()
    st.session_state.results_dir = str(default_dir.resolve())
if "file_choice" not in st.session_state:
    # placeholder until CSVs enumerated later
    st.session_state.file_choice = ""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading data...")
def load_df(path: Path) -> pd.DataFrame:
    """Load a results CSV (with or without header) and coerce numeric types.

    Strategy:
    1. Try reading with the default header (header=0). If that yields at least one numeric
       column after coercion, we keep it.
    2. Otherwise fall back to reading as header-less (header=None) and assign generic names.
    """
    if not path.exists():
        return pd.DataFrame()

    # Fallback column template for header-less CSVs
    column_names = [
        'algo', 'label', 'market', 'return_pct', 'net_pnl_quote', 'total_positions',
        'total_trades', 'total_pnl_quote', 'total_buy_trades', 'total_sell_trades',
        'accuracy_long', 'accuracy_short', 'total_volume', 'avg_close_time',
        'avg_profit_per_trade', 'sharpe_ratio', 'profit_factor', 'winning_trades',
        'losing_trades', 'total_open_trades', 'total_closed_trades', 'param_1', 'param_2'
    ]

    def _postprocess(df_in: pd.DataFrame) -> pd.DataFrame:
        """Common cleaning for both read modes."""
        df_out = df_in.copy()
        df_out = df_out.loc[:, ~df_out.columns.str.contains('^Unnamed', na=False)]
        df_out.dropna(axis=1, how='all', inplace=True)

        for col in df_out.columns:
            coerced = pd.to_numeric(df_out[col], errors="coerce")
            # Only replace column if conversion produced at least one numeric value
            if not coerced.isna().all():
                df_out[col] = coerced

        if 'label' not in df_out.columns or df_out['label'].isnull().any():
            df_out['label'] = [f"run_{i}" for i in df_out.index]
        return df_out

    def _row0_is_duplicate_header(df_test: pd.DataFrame) -> bool:
        """Return True if first data row appears to repeat the header names (string match)."""
        if df_test.empty:
            return False
        header_vals = [str(c).strip().lower() for c in df_test.columns]
        row0_vals = [str(v).strip().lower() for v in df_test.iloc[0].values]
        # Compare first few columns (3) to avoid false positives
        return header_vals[:3] == row0_vals[:3]

    # First attempt: read with a header row.
    try:
        df_header = pd.read_csv(path, header=0)
        if _row0_is_duplicate_header(df_header):
            raise ValueError("Detected duplicated header row – treating as header-less file")
        df_header = _postprocess(df_header)
        return df_header
    except Exception:
        pass  # Fallback to header-less mode

    # Fallback: no header present
    try:
        df_no_header = pd.read_csv(path, header=None)
        df_no_header.columns = column_names[: len(df_no_header.columns)]

        df_no_header = _postprocess(df_no_header)
        return df_no_header
    except Exception as exc:
        st.error(f"Error loading {path.name}: {exc}")
        return pd.DataFrame()


def find_csvs(directory: Path):
    """Return a list of paths to *results.csv files under directory (recursive)."""
    csvs = list(directory.rglob("*results.csv"))
    # Also include custom-named CSVs (e.g., pmm_dynamic_2.csv) under summaries
    extra = [p for p in directory.rglob("*.csv") if p not in csvs]
    return sorted(csvs + extra)

# ---------------------------------------------------------------------------
# Sidebar – data source selection
# ---------------------------------------------------------------------------
sidebar = st.sidebar
sidebar.header("Data Source")

if 'results_dir' not in st.session_state:
    st.session_state.results_dir = str(Path.cwd())

results_dir_input = sidebar.text_input("Results directory", value=st.session_state.results_dir)
if results_dir_input != st.session_state.results_dir:
    st.session_state.results_dir = results_dir_input
    st.experimental_rerun()

results_dir = Path(st.session_state.results_dir).expanduser().resolve()

csv_files = find_csvs(results_dir)
if not csv_files:
    st.warning(f"No `*results.csv` files found in `{results_dir}`. Run a batch test or choose a valid directory.")
    st.stop()

# Display quick info about discovered files
sidebar.caption(f"Found {len(csv_files)} results file{'s' if len(csv_files) != 1 else ''} in directory.")

if 'file_choice' not in st.session_state or Path(st.session_state.file_choice) not in csv_files:
    st.session_state.file_choice = str(csv_files[0])

file_choice_str = sidebar.selectbox(
    "Select results file",
    options=[str(p) for p in csv_files],
    index=[str(p) for p in csv_files].index(st.session_state.file_choice),
    format_func=lambda p: Path(p).name,
)
file_choice = Path(file_choice_str)

if file_choice_str != st.session_state.file_choice:
    st.session_state.file_choice = file_choice_str
    load_df.clear()

if sidebar.button("🔄 Reload CSV"):
    load_df.clear()

# ---------------------------------------------------------------------------
# Detail packet selector (optional candlestick preview)
# ---------------------------------------------------------------------------

try:
    from ..packet_index import load_index, load_packet  # type: ignore
except ImportError:
    # Fallback when running as script or path not set up
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_index, load_packet = importlib.import_module("dashboard.packet_index").load_index, importlib.import_module("dashboard.packet_index").load_packet

csv_stem = file_choice.stem  # e.g., dev_results
# Allow per-run subdirectories under detail_packets
detail_dir = Path("results/detail_packets") / csv_stem
idx_df = load_index(detail_dir)

selected_detail = None

if idx_df.empty:
    sidebar.info("No index file found – run the batch tester again to generate detail packets.")
else:
    # Filter index to those with valid flag (1). If the list of labels
    # belonging to the currently selected CSV is not yet available in
    # `session_state` (set later in the page), derive it on-the-fly by
    # reading just the *label* column. This avoids a chicken-and-egg
    # situation where the preview selector is rendered before we parse
    # the CSV.

    csv_labels = set(st.session_state.get("available_labels", []))

    if not csv_labels:
        try:
            csv_labels = set(pd.read_csv(file_choice, usecols=["label"]).label.dropna())
        except Exception:
            csv_labels = set()

    valid_rows = idx_df[idx_df["valid"].isin([1, "1", True])]
    if csv_labels:
        valid_rows = valid_rows[valid_rows["label"].isin(csv_labels)]

    preview_opts = valid_rows["label"].tolist()
    if preview_opts:
        selected_detail = sidebar.selectbox("Run graph preview", preview_opts)
    else:
        sidebar.info("No valid detail packets matching current CSV.")

# ---------------------------------------------------------------------------
# Main content – load and display data
# ---------------------------------------------------------------------------
df = load_df(file_choice)

if df.empty:
    st.error(f"Could not load or parse data from {file_choice.name}. Check the file format.")
    st.stop()

st.success(f"Loaded {len(df)} rows from `{file_choice.name}`")

# Store labels for other pages (e.g., Run Profile) to filter valid runs belonging
# to the currently selected CSV.
try:
    if "error" in df.columns:
        ok_df = df[df["error"].isna()]
    else:
        ok_df = df
    st.session_state.available_labels = sorted(ok_df["label"].dropna().unique().tolist())
except Exception:
    st.session_state.available_labels = []

# Warn user if key KPI columns are missing
expected_kpis = ["net_pnl_quote", "profit_factor", "total_volume"]
missing_kpis = [c for c in expected_kpis if c not in df.columns]
if missing_kpis:
    st.warning(f"Selected CSV is missing expected column(s): {', '.join(missing_kpis)}. "
               "Some batch KPIs will show as 0 or NaN.")

# Raw data inspector
st.subheader("Raw Data")
with st.expander("Show / Hide Table"):
    st.dataframe(df, use_container_width=True, height=300)

# ---------------------------------------------------------------------------
# Batch KPI header
# ---------------------------------------------------------------------------

# Helper to return an empty numeric Series when a column is absent
def _get_series_or_empty(column_name: str) -> pd.Series:
    return df[column_name] if column_name in df.columns else pd.Series(dtype=float)

# Compute batch-level KPIs, defaulting to zero/NaN when not available in the CSV
net_pnl_series = _get_series_or_empty("net_pnl_quote")
total_volume_series = _get_series_or_empty("total_volume")
profit_factor_series = _get_series_or_empty("profit_factor")
total_pnl_quote_series = _get_series_or_empty("total_pnl_quote")

# Win-rate: share of rows whose profit_factor > 1 (only if column exists)
if not profit_factor_series.empty:
    win_rate_val = (profit_factor_series > 1).mean()
else:
    win_rate_val = 0.0

# Profit factor computed from total_pnl_quote column when present
if not total_pnl_quote_series.empty and (total_pnl_quote_series != 0).any():
    gross_profit = total_pnl_quote_series.clip(lower=0).sum()
    gross_loss = abs(total_pnl_quote_series.clip(upper=0).sum())
    profit_factor_val = gross_profit / gross_loss if gross_loss != 0 else float("nan")
else:
    profit_factor_val = float("nan")

batch_results = {
    "net_pnl_quote": net_pnl_series.mean(),
    "total_volume": total_volume_series.mean(),
    "win_rate": win_rate_val,
    "profit_factor": profit_factor_val,
}

st.subheader("Batch Performance Summary")
b1, b2, b3, b4 = st.columns(4)

HELP_TEXTS = {
    "pnl": "The average **Net PNL** across all successful runs in the selected CSV file.\n\n- **Source Column**: `net_pnl_quote`\n- **Aggregation**: Mean\n- **Note**: This is not volume-weighted and does not normalize for different quote currencies.",
    "volume": "The average **Total Volume** traded across all successful runs.\n\n- **Source Column**: `total_volume`\n- **Aggregation**: Mean\n- **Note**: Volume is measured in the quote asset.",
    "win_rate": "The percentage of runs in the batch that were profitable.\n\n- **Formula**: `(Number of runs with Profit Factor > 1) / (Total number of runs)`\n- **Note**: This is a *run-level* metric, not a *trade-level* win rate.",
    "profit_factor": "The sum of all profits divided by the sum of all losses for the entire batch.\n\n- **Formula**: `sum(gross_profit) / sum(gross_loss)`\n- **Source Column**: `total_pnl_quote`\n- **Note**: A value greater than 1 indicates overall profitability."
}

def render_kpi_with_info(column, title: str, value_str: str, help_key: str):
    with column:
        label_cols = st.columns([0.8, 0.2])
        with label_cols[0]:
            st.markdown(f"**{title}**")
        with label_cols[1]:
            with st.popover("ⓘ", help="Click for details"):
                st.markdown(HELP_TEXTS[help_key])
        st.metric(label=" ", value=value_str, label_visibility="collapsed")

render_kpi_with_info(b1, "Avg Net PNL", f"{batch_results['net_pnl_quote']:,.2f}", "pnl")
render_kpi_with_info(b2, "Avg Volume", f"{batch_results['total_volume']:,.0f}", "volume")
render_kpi_with_info(b3, "Win Rate", f"{batch_results['win_rate']*100:.1f}%", "win_rate")
render_kpi_with_info(b4, "Profit Factor", f"{batch_results['profit_factor']:.2f}", "profit_factor")

# ---------------------------------------------------------------------------
# Leaderboard table
# ---------------------------------------------------------------------------

base_cols = ["label", "algo", "net_pnl_quote", "total_volume", "total_trades", "profit_factor", "sharpe_ratio"]
leader_cols = [c for c in base_cols if c in df.columns]
display_df = df[leader_cols].copy()
gb = GridOptionsBuilder.from_dataframe(display_df)
gb.configure_default_column(sortable=True, resizable=True)
gb.configure_selection(selection_mode="single", use_checkbox=False)
grid = AgGrid(display_df, gridOptions=gb.build(), theme="streamlit", height=300, update_mode="SELECTION_CHANGED")

if grid["selected_rows"]:
    sel_label = grid["selected_rows"][0]["label"]
    st.session_state["run_profile"] = sel_label
    st.info(f"Selected run '{sel_label}'. Open the 'Experiment Analysis' page for details.")

# ---------------------------------------------------------------------------
# Visualisations
# ---------------------------------------------------------------------------
st.subheader("Visualisations")

algo_col_candidates = [c for c in df.columns if c in ("algo", "controller_name", "strategy") or "algo" in c]
algo_col = sidebar.selectbox("Group / filter by column", algo_col_candidates) if algo_col_candidates else None

if algo_col and algo_col in df.columns:
    algos = sorted(df[algo_col].dropna().unique())
    chosen_algos = sidebar.multiselect("Filter values", algos, default=algos)
    df_display = df[df[algo_col].isin(chosen_algos)]
else:
    df_display = df.copy()

col1, col2 = st.columns(2)

def render_chart_with_info(chart_func, title: str, help_text: str):
    label_cols = st.columns([0.9, 0.1])
    with label_cols[0]:
        st.markdown(f"**{title}**")
    with label_cols[1]:
        with st.popover("ⓘ", help="Click for details"):
            st.markdown(help_text)
    with st.container():
        chart_func()

with col1:
    if "net_pnl_quote" in df_display.columns:
        def chart():
            fig = px.bar(df_display, x="label", y="net_pnl_quote", color=algo_col)
            fig.update_layout(xaxis_title="Test Label", yaxis_title="PNL (Quote)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Net PNL Quote by Test Run", 
                               "A bar chart showing the final **Net PNL** for each individual test run.\n\n"
                               "- **X-axis**: `label` (the unique ID for each run)\n"
                               "- **Y-axis**: `net_pnl_quote`\n"
                               "- **Source**: Directly from the results CSV, one bar per row.")

    if "profit_factor" in df_display.columns and algo_col:
        def chart():
            fig = px.box(df_display, x=algo_col, y="profit_factor", color=algo_col)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Profit Factor Distribution", 
                               "A box plot showing the distribution of the **Profit Factor** for each algorithm.\n\n"
                               "- The **box** shows the interquartile range (IQR), from the 25th to 75th percentile.\n"
                               "- The **line** in the middle is the median (50th percentile).\n"
                               "- The **whiskers** extend to show the rest of the distribution (typically 1.5x IQR).\n"
                               "- **Points** outside the whiskers are outliers.")

    if {"profit_factor", "accuracy_long"}.issubset(df_display.columns):
        def chart():
            fig = px.scatter(df_display, x="accuracy_long", y="profit_factor", color=algo_col, hover_data=["label"])
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Profit Factor vs Accuracy",
                               "A scatter plot to visualize the relationship between profitability and trade accuracy.\n\n"
                               "- **X-axis**: `accuracy_long` (% of profitable long trades)\n"
                               "- **Y-axis**: `profit_factor` (Gross Profit / Gross Loss)\n"
                               "- **Source**: Each point represents one run from the CSV.")

with col2:
    if {"total_volume", "net_pnl_quote"}.issubset(df_display.columns):
        def chart():
            fig = px.scatter(df_display, x="total_volume", y="net_pnl_quote", color=algo_col, hover_data=["label"])
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Volume vs Net PNL",
                               "A scatter plot showing the relationship between total trading volume and the final Net PNL.\n\n"
                               "- **X-axis**: `total_volume` (Total value of trades in quote currency)\n"
                               "- **Y-axis**: `net_pnl_quote`\n"
                               "- **Source**: Each point represents one run from the CSV.")

    if "accuracy_long" in df_display.columns and algo_col:
        def chart():
            fig = px.box(df_display, x=algo_col, y="accuracy_long", color=algo_col)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Accuracy Distribution by Algorithm",
                               "A box plot showing the distribution of **Long Trade Accuracy** for each algorithm.\n\n"
                               "- The **box** shows the interquartile range (IQR), from the 25th to 75th percentile.\n"
                               "- The **line** in the middle is the median (50th percentile).\n"
                               "- The **whiskers** extend to show the rest of the distribution (typically 1.5x IQR).\n"
                               "- **Points** outside the whiskers are outliers.")

    if "sharpe_ratio" in df_display.columns and "net_pnl_quote" in df_display.columns:
        def chart():
            fig = px.histogram(df_display, x="sharpe_ratio", color=algo_col, marginal="rug")
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        render_chart_with_info(chart, "Sharpe Ratio Distribution",
                               "A histogram showing the distribution of the **Sharpe Ratio** across all runs.\n\n"
                               "- **X-axis**: `sharpe_ratio`\n"
                               "- **Y-axis**: Frequency (count of runs in each bin)\n"
                               "- **Note**: The 'rug' marks along the bottom show the exact location of each individual run's Sharpe Ratio.")

# ---------------------------------------------------------------------------
# Graph preview for selected run (detail packet)
# ---------------------------------------------------------------------------

if selected_detail:
    try:
        detail_data = load_packet(selected_detail, detail_dir)

        if "results" not in detail_data or not detail_data.get("results"):
            error_msg = detail_data.get("error", "Packet is missing 'results' data or results are empty.")
            raw_response = detail_data.get("raw")
            st.warning(f"Could not generate preview for {selected_detail}: {error_msg}")
            if raw_response:
                with st.expander("Show raw server response"):
                    st.code(raw_response, language="text")
        else:
            proc = detail_data["processed_data"]
            if "features" in proc and isinstance(proc["features"], dict):
                df_feat = pd.DataFrame(proc["features"])  # type: ignore[arg-type]
            else:
                # assume flat dict-of-lists (keys are columns)
                df_feat = pd.DataFrame(proc)  # type: ignore[arg-type]
            executors = detail_data.get("executors", [])
            results = detail_data["results"]

            if df_feat.empty:
                st.warning("No processed data in packet.")
            else:
                # Add grey quote markers if event log available in packet
                extra_orders_df = None
                ev_path = detail_data.get("event_log_csv")
                if ev_path and Path(ev_path).exists():
                    try:
                        ev_df = pd.read_csv(ev_path)
                        extra_orders_df = ev_df[ev_df["event_type"] == "CREATE"]
                    except Exception as e:
                        logging.warning(f"Could not process event log {ev_path}: {e}")

                fig_preview = create_backtesting_figure(
                    df_feat,
                    executors,
                    {"trading_pair": results.get("market", "N/A")},
                    extra_orders=extra_orders_df,
                )
                st.markdown("### 📉 Run Preview – " + selected_detail)
                st.plotly_chart(fig_preview, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not load detail packet: {exc}")

# Load CSV and drop rows with 'error' (failed backtests)
df = pd.read_csv(file_choice)
if 'error' in df.columns:
    failed = df[df['error'].notna()]
    if not failed.empty:
        st.warning(f"{len(failed)} backtests failed and were excluded from KPIs. See console for details.")
    df = df[df['error'].isna()].copy()

# If after filtering the KPI columns still missing, create zero columns to avoid KeyError
for col in ['net_pnl_quote', 'total_volume', 'profit_factor']:
    if col not in df.columns:
        df[col] = 0 