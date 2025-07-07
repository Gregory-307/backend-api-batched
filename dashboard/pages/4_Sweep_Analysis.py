"""Sweep Analysis page – visualise KPI versus sweep parameters.

Assumes summary CSV produced by B_json_to_backtests.py contains `_sweep_params` columns
(one per varied parameter).
"""
import streamlit as st
from pathlib import Path
import pandas as pd
import plotly.express as px
import yaml
import ast  # near top

st.set_page_config(page_title="Sweep Analysis", layout="wide")
st.title("📊 Sweep Analysis")

# ---------------------------------------------------------------------------
# Sidebar – pick summary CSV & (optional) YAML file
# ---------------------------------------------------------------------------

RES_DIR = Path("results/summaries")
SWEEP_DIR = Path("sweeps")

csv_files = sorted(RES_DIR.glob("*.csv"))
if not csv_files:
    st.warning("No summary CSVs found under results/summaries/ . Run a sweep first.")
    st.stop()

csv_choice: Path = st.sidebar.selectbox("Summary CSV", csv_files)

# attempt to auto-match YAML
stem = csv_choice.stem.split(".")[0]  # strip possible date suffixes
yaml_guess = SWEEP_DIR / f"{stem}_sweep.yml"

yaml_files = sorted(SWEEP_DIR.glob("*_sweep.yml"))
if yaml_guess.exists():
    default_idx = yaml_files.index(yaml_guess)
else:
    default_idx = 0 if yaml_files else None

yaml_choice: Path | None = st.sidebar.selectbox("Sweep YAML (optional)", yaml_files, index=default_idx if default_idx is not None else 0)

# ---------------------------------------------------------------------------
# Load CSV
# ---------------------------------------------------------------------------

df = pd.read_csv(csv_choice)
if df.empty:
    st.error("Selected CSV is empty.")
    st.stop()

# Convert stringified single-element lists like "[0.005]" → 0.005 for easier filtering
def _maybe_unwrap(val):
    if isinstance(val, str) and val.startswith("[") and val.endswith("]"):
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, list) and len(parsed) == 1:
                return parsed[0]
        except Exception:
            pass
    return val

df = df.applymap(_maybe_unwrap)

# Identify sweep parameter columns
if yaml_choice and yaml_choice.exists():
    try:
        sweep_data = yaml.safe_load(yaml_choice.read_text())
        sweep_keys = set((sweep_data.get("grid") or {}).keys()) | set((sweep_data.get("sweep") or {}).keys())
    except Exception:
        sweep_keys = set()
else:
    # Fallback: any column that is NOT numeric KPI and not label/error is treated as sweep param
    kpi_like = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    sweep_keys = set(c for c in df.columns if c not in kpi_like and c not in ("label", "error"))

param_cols = sorted(k for k in sweep_keys if k in df.columns)
if not param_cols:
    st.error("Sweep parameter columns not found in the CSV.")
    st.stop()

# Metric choices (numeric columns)
metric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
metric_default = "net_pnl_quote" if "net_pnl_quote" in metric_cols else metric_cols[0]

metric_col = st.selectbox("Performance metric", metric_cols, index=metric_cols.index(metric_default))

x_param = st.selectbox("X-axis parameter", param_cols)
y_opts = ["<None>"] + [c for c in param_cols if c != x_param]
y_param_sel = st.selectbox("Y-axis parameter (for heatmap)", y_opts)

# ---------------------------------------------------------------------------
# Filter remaining parameters to keep all else equal
# ---------------------------------------------------------------------------
other_params = [p for p in param_cols if p not in {x_param, (y_param_sel if y_param_sel != "<None>" else None)}]

with st.sidebar.expander("Lock other parameters", expanded=False):
    filters = {}
    for p in other_params:
        vals = sorted(df[p].dropna().unique())
        if len(vals) <= 1:
            continue  # nothing to filter
        vals_display = ["<Any>"] + list(vals)
        sel = st.selectbox(p, vals_display, key=f"filter_{p}")
        if sel == "<Any>":
            continue
        filters[p] = sel

for k, v in filters.items():
    df = df[df[k] == v]

if df.empty:
    st.error("No rows remain after filtering; adjust filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

if y_param_sel == "<None>":
    hover_cols = ["label"] + [c for c in param_cols if c not in {x_param}] + [metric_col]
    fig = px.scatter(
        df,
        x=x_param,
        y=metric_col,
        hover_data=hover_cols,
        color_discrete_sequence=["#F59E0B"],
    )
    fig.update_layout(xaxis_title=x_param, yaxis_title=metric_col)
    st.plotly_chart(fig, use_container_width=True)
else:
    piv = df.pivot_table(index=y_param_sel, columns=x_param, values=metric_col, aggfunc="mean")
    fig = px.imshow(piv, x=piv.columns, y=piv.index, color_continuous_scale="RdYlGn", aspect="auto")
    fig.update_layout(xaxis_title=x_param, yaxis_title=y_param_sel, coloraxis_colorbar_title=metric_col)
    st.plotly_chart(fig, use_container_width=True)