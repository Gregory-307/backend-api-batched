import os
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_RESULTS_DIR = Path.cwd()
DEFAULT_CSV = "batch_results.csv"
PAGE_TITLE = "Hummingbot – Experiment Dashboard"

st.set_page_config(page_title=PAGE_TITLE, layout="wide", initial_sidebar_state="expanded")

st.title("📈 Experiment Results – Overview (Page 1)")

# ---------------------------------------------------------------------------
# Sidebar – file picker & basic controls
# ---------------------------------------------------------------------------

def find_csvs(directory: Path):
    return [p for p in directory.glob("*.csv") if p.name.endswith("results.csv")]

sidebar = st.sidebar
sidebar.header("Data Source")

results_dir = sidebar.text_input("Results directory", value=str(DEFAULT_RESULTS_DIR))
results_dir = Path(results_dir).expanduser().resolve()

csv_files = find_csvs(results_dir)
if not csv_files:
    st.warning(f"No *results.csv files found in {results_dir}. Run make batch first.")
    st.stop()

file_choice = sidebar.selectbox("Select results file", options=csv_files, format_func=lambda p: p.name)

refresh = sidebar.button("🔄 Reload CSV")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_df(path: Path):
    df = pd.read_csv(path)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    # Attempt numeric coercion for all columns
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df

df = load_df(file_choice) if not refresh else load_df.clear()(file_choice)

st.success(f"Loaded {len(df)} rows from {file_choice.name}")

# ---------------------------------------------------------------------------
# Data inspection
# ---------------------------------------------------------------------------

st.subheader("Raw Data")
with st.expander("Show / Hide Table", expanded=False):
    st.dataframe(df, use_container_width=True, height=300)

# Remove error rows for metrics scan
error_free_df = df[df.get("error").isna()] if "error" in df.columns else df
numeric_cols = error_free_df.select_dtypes(include="number").columns.tolist()

if not numeric_cols:
    st.warning("No numeric columns detected. Check that metrics are numeric in the CSV.")

kpi_cols_default = [c for c in ["net_pnl_quote", "sharpe_ratio", "profit_factor", "accuracy_long"] if c in numeric_cols]
selected_kpis = sidebar.multiselect("KPI columns", options=numeric_cols, default=kpi_cols_default, help="Choose up to 4 metrics to highlight")[:4] if numeric_cols else []

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

if selected_kpis:
    st.subheader("Top Runs per KPI")
    kpi_cols = st.columns(len(selected_kpis))
    for i, colname in enumerate(selected_kpis):
        best_idx = df[colname].idxmax()
        best_row = df.loc[best_idx]
        kpi_cols[i].metric(label=colname, value=f"{best_row[colname]:,.4f}", help=f"Label: {best_row.get('label', 'n/a')}")

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

st.subheader("Visualisations")

# Algo selector
algo_col = sidebar.selectbox("Group / filter by algo column", [c for c in df.columns if c in ("algo", "controller_name")]) if any(c in df.columns for c in ("algo", "controller_name")) else None
if algo_col:
    algos = sorted(df[algo_col].dropna().unique())
    chosen_algos = sidebar.multiselect("Algorithms", algos, default=algos)
    df_display = df[df[algo_col].isin(chosen_algos)]
else:
    df_display = df.copy()

# Line chart of net_pnl_quote by label
if "net_pnl_quote" in df_display.columns:
    fig = px.bar(df_display, x="label", y="net_pnl_quote", color=algo_col or None, title="Net PNL Quote by Test")
    fig.update_layout(xaxis_title="Test Label", yaxis_title="PNL (quote)", showlegend=bool(algo_col))
    st.plotly_chart(fig, use_container_width=True)

# Scatter of Sharpe vs PNL if available
if {"net_pnl_quote", "sharpe_ratio"}.issubset(df_display.columns):
    fig2 = px.scatter(df_display, x="sharpe_ratio", y="net_pnl_quote", color=algo_col or None,
                      hover_data=["label"], title="Sharpe vs Net PNL (quote)")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

st.caption("Page 2 (Top-5 deep dive) coming soon…") 