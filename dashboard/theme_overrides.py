"""Injects custom Tailwind-inspired dark CSS into Streamlit.

Import this module once (e.g. in `dashboard/pages/1_Documentation.py`) and the style
rules will apply across all pages in the multi-page app.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Google Font & basic palette
# ---------------------------------------------------------------------------
FONT_IMPORT = (
    "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">"
    "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>"
    "<link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">"
)

CSS = """
<style>
/* Apply Inter everywhere */
html, body, [class*="st-"], .stMarkdown, .stDataFrame table {
  font-family: 'Inter', sans-serif;
}

/* Dark background tweak (overrides config.toml) */
body {
  background-color: #111827;
  color: #E5E7EB;
}

/* KPI card container */
.kpi-card {
  background-color: #1F2937;
  border-radius: 0.75rem;
  padding: 1.5rem;
  border: 1px solid #374151;
}

/* Generic dark table container */
.table-container {
  background-color: #1F2937;
  border-radius: 0.75rem;
  border: 1px solid #374151;
  overflow: hidden;
}

/* Highlight row (Ag-Grid custom) */
.ag-row-selected {
  background-color: #4B5563 !important; /* Gray-600 */
}

/* BUY / SELL badge pills */
.badge-buy {
  background: rgba(16, 185, 129, 0.2); /* emerald-500 @ 20% */
  color: #10B981;
  padding: 2px 6px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 600;
}
.badge-sell {
  background: rgba(239, 68, 68, 0.2); /* red-500 */
  color: #EF4444;
  padding: 2px 6px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 600;
}

/* Docs landing big buttons */
.big-btn {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  margin: 0.25rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: #ffffff;
  background: #2563eb; /* blue-600 */
  border: 0;
  border-radius: 0.5rem;
  text-align: left;
}
.big-btn:hover {
  background: #1e40af;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0.75rem 0 0.5rem;
}

.table-container thead th {position:sticky; top:0; z-index:1;}
</style>
"""

# ---------------------------------------------------------------------------
# Inject once
# ---------------------------------------------------------------------------
if "_THEME_CSS_INJECTED" not in st.session_state:
    st.markdown(FONT_IMPORT + CSS, unsafe_allow_html=True)
    st.session_state["_THEME_CSS_INJECTED"] = True 