"""
ui/views/editor_view.py — Custom Code & Unified Diff Editor View.
"""
from __future__ import annotations

import html
from typing import Tuple
import streamlit as st
from ui.analytics import PRESET_SNIPPETS, detect_language
from ui.state import pop_target_override


def render_editor_view() -> Tuple[str, str]:
    """Renders the custom code/diff editor and returns (code, filename)."""
    c1, c2 = st.columns([1, 2])
    with c1:
        active_filename = st.text_input(
            "Target Filename (e.g. payment_service.py, main.go, service.java, index.js):",
            value="payment_service.py",
        )

    override_code = pop_target_override()
    default_code = override_code or PRESET_SNIPPETS["🐍 Python: Vulnerable App (SQLi + Secret + Bare Except)"]

    with c2:
        _, det_name = detect_language(default_code, active_filename)
        safe_det = html.escape(det_name)
        st.markdown(
            f"""
            <div style='padding: 6px 12px; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; margin-top: 24px; font-size: 0.86rem;'>
                🏷️ <b>Detected Engine:</b> <span style='color: #818CF8;'>{safe_det}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    target_code = st.text_area(
        "Code Editor",
        value=default_code,
        height=220,
        label_visibility="collapsed",
    )

    return target_code, active_filename
