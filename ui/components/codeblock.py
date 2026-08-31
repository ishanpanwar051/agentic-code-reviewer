"""
ui/components/codeblock.py — Syntax-Highlighted Before -> After Diff Preview Component.
"""
from __future__ import annotations

import streamlit as st


def render_diff_code_preview(
    original_code: str,
    refactored_code: str,
    language: str = "python",
) -> None:
    """Renders a structured Before vs After side-by-side or split code preview."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Original Code (With Vulnerabilities)**")
        st.code(original_code, language=language, line_numbers=True)
    with col2:
        st.markdown("**🟢 Refactored Code (All Safe Fixes Applied)**")
        st.code(refactored_code, language=language, line_numbers=True)
