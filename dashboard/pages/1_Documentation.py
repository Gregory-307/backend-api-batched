from __future__ import annotations

import streamlit as st
from pathlib import Path
from typing import Dict

# Ensure global CSS overrides are active
try:
    from .. import theme_overrides  # noqa: F401
except ImportError:
    import importlib, pathlib, sys
    root = pathlib.Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import importlib
    importlib.import_module("dashboard.theme_overrides")

st.set_page_config(page_title="Documentation Hub", layout="wide")

st.markdown("""
<h1 style='text-align:center; margin-bottom: 1rem;'>📚 Project Knowledge Base</h1>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Build docs mapping dynamically (preferred list first, then auto-discover)
# ---------------------------------------------------------------------------
PREFERRED: Dict[str, str] = {
    "docs/guide.md": "Hummingbot Backtesting Guide",
    "docs/COMPLETED.md": "Rescue Retrospective",
    "README.md": "Backend-API README",
    "docs/GUIDE_NEW_STRATEGY.md": "Add New Strategy Walk-through",
    "docs/LEARNINGGUIDE.md": "Backtesting Rescue Story",
    "docs/analyst_funnel_plan.md": "Analyst Funnel Roadmap",
    "docs/implementation_plan_2025-06-26.md": "Implementation Plan Q2",
    "docs/COMPLETED2.md": "Custom Controller Case Study",
}

# Bucket names we want to group under
BUCKETS: Dict[str, str] = {
    "guide": "Primary Documentation",
    "README": "Primary Documentation",
    "COMPLETED": "Primary Documentation",
    "GUIDE_NEW_STRATEGY": "Implementation / How-To",
    "LEARNINGGUIDE": "Implementation / How-To",
    "analyst_funnel_plan": "Internal Specs & Plans",
    "implementation_plan": "Internal Specs & Plans",
    "1_api_backend": "Codebase Reference",
    "2_testing_framework": "Codebase Reference",
    "3_dashboard": "Codebase Reference"
}

sections: Dict[str, Dict[str, str]] = {
    "guide": PREFERRED,
    "README": {
        "README.md": "Backend-API README"
    },
    "COMPLETED": {
        "docs/COMPLETED.md": "Rescue Retrospective"
    },
    "GUIDE_NEW_STRATEGY": {
        "docs/GUIDE_NEW_STRATEGY.md": "Add New Strategy Walk-through"
    },
    "LEARNINGGUIDE": {
        "docs/LEARNINGGUIDE.md": "Backtesting Rescue Story"
    },
    "analyst_funnel_plan": {
        "docs/analyst_funnel_plan.md": "Analyst Funnel Roadmap"
    },
    "implementation_plan": {
        "docs/implementation_plan_2025-06-26.md": "Implementation Plan Q2"
    },
    "1_api_backend": {
        "docs/codebase_reference/1_api_backend.md": "API Backend"
    },
    "2_testing_framework": {
        "docs/codebase_reference/2_testing_framework.md": "Testing & Automation"
    },
    "3_dashboard": {
        "docs/codebase_reference/3_dashboard.md": "Dashboard & UI",
        "docs/codebase_reference/4_developer_scripts.md": "Developer Scripts",
        "docs/codebase_reference/5_strategy_controllers.md": "Strategy Controllers",
        "docs/codebase_reference/0_all_python_files.md": "Complete File List",
    },
    "Internal Specs & Plans": {
        "docs/COMPLETED2.md": "Custom Controller Case Study"
    },
}

# ---------------------------------------------------------------------------
# Helper for iteration / search
# ---------------------------------------------------------------------------
all_items = [(sec, pth, lbl) for sec, mapping in sections.items() for pth, lbl in mapping.items()]

# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------
st.sidebar.header("Search docs")
query = st.sidebar.text_input("Filter", placeholder="type to filter…")

def is_match(label: str) -> bool:
    return query.lower() in label.lower() if query else True

# Keep track of selected doc across reruns
if "selected_doc" not in st.session_state:
    st.session_state.selected_doc = None

# ---------------------------------------------------------------------------
# Render buttons per section
# ---------------------------------------------------------------------------
for section, mapping in sections.items():
    visible_items = {p: lbl for p, lbl in mapping.items() if is_match(lbl)}
    if not visible_items:
        continue
    st.markdown(f"<div class='section-title'>{section}</div>", unsafe_allow_html=True)
    cols = st.columns(2)
    col_idx = 0
    for path, label in visible_items.items():
        if cols[col_idx].button(label, key=f"docbtn_{section}_{path}", help=path, type="secondary", use_container_width=True):
            st.session_state.selected_doc = path
        col_idx = (col_idx + 1) % 2
    st.markdown("<br/>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Display selected markdown
# ---------------------------------------------------------------------------
if st.session_state.selected_doc:
    md_path = Path(st.session_state.selected_doc)
    if not md_path.is_file():
        st.error(f"File not found: {md_path}")
    else:
        st.markdown("---")
        st.subheader(sections[next(s for s,m in sections.items() if md_path.as_posix() in m)][md_path.as_posix()])
        try:
            st.markdown(md_path.read_text(), unsafe_allow_html=True)
        except FileNotFoundError:
            st.error(f"Documentation file not found: {md_path}") 