#!/usr/bin/env python3
"""UI helper functions for Streamlit pages (Tailwind style)."""
from __future__ import annotations

import contextlib
import streamlit as st

# Ensure CSS injected once
import dashboard.theme_overrides  # noqa: F401  (side-effect)


def kpi_card(label: str, value: str, *, accent_class: str = "text-white") -> None:
    """Render a KPI card with Tailwind styles.

    Example::
        kpi_card("Total Net PNL", "+$1,234.56", accent_class="text-green-400")
    """
    html = f"""
    <div class='kpi-card'>
        <p class='text-sm font-medium text-gray-400'>{label}</p>
        <p class='text-3xl font-bold {accent_class} mt-1'>{value}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


@contextlib.contextmanager
def styled_container(class_name: str):
    """Context manager yielding a Streamlit container wrapped in a div with *class_name*."""
    st.markdown(f"<div class='{class_name}'>", unsafe_allow_html=True)
    with st.container():
        yield
    st.markdown("</div>", unsafe_allow_html=True) 