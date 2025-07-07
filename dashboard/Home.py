"""Minimal landing page for the Hummingbot Experiment App.
Displays a centred title and short blurb, and ensures the custom theme CSS is loaded once.
"""

from __future__ import annotations

import streamlit as st
import sys
from pathlib import Path

# Ensure project root is on sys.path so `import dashboard...` works even when this
# file is executed directly (not as a module) via `streamlit run dashboard/Home.py`.
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# Inject global CSS / fonts
import dashboard.theme_overrides  # type: ignore # noqa: F401  (side-effects only)

st.set_page_config(
    page_title="Hummingbot Experiment App",
    page_icon="🐝",
    layout="wide",
)

# -----------------------------------------------------------------------------
# Centered hero section
# -----------------------------------------------------------------------------

hero_style = "text-align:center; margin-top: 15vh;"

title_html = """
<h1 style='font-size:3rem; margin-bottom:0.3rem;'>🐝 Hummingbot Experiment App</h1>
<p style='font-size:1.25rem; color:#9CA3AF;'>Run, compare, and analyse back-testing experiments with ease.</p>
"""

st.markdown(f"<div style='{hero_style}'>{title_html}</div>", unsafe_allow_html=True)

# Spacer so nothing overlaps footer/sidebar
st.markdown("""<div style='height:40vh'></div>""", unsafe_allow_html=True) 