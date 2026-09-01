"""
ui/views/editor_view.py — Custom Code & Unified Diff Editor View.
"""
from __future__ import annotations

import html
from typing import Tuple
import streamlit as st
from ui.analytics import detect_language
from ui.state import pop_target_override


def render_editor_view() -> Tuple[str, str]:
    """Renders the custom code/diff editor and returns (code, filename)."""
    override_code = pop_target_override()

    if "editor_code" not in st.session_state:
        st.session_state["editor_code"] = ""
    if "editor_filename" not in st.session_state:
        st.session_state["editor_filename"] = "main.cpp"

    if override_code is not None:
        st.session_state["editor_code"] = override_code

    c1, c2 = st.columns([1, 2])
    with c1:
        active_filename = st.text_input(
            "Target Filename (e.g. main.cpp, app.py, server.go, Service.java):",
            value=st.session_state["editor_filename"],
            key="custom_editor_filename_input",
        )

    target_code = st.text_area(
        "Code Editor",
        value=st.session_state["editor_code"],
        placeholder="// Paste your C++, Python, Java, Go, Rust, JavaScript or PHP code here...",
        height=240,
        label_visibility="collapsed",
        key="custom_editor_code_textarea",
    )
    st.session_state["editor_code"] = target_code

    # Real-time language detection & smart filename extension sync
    lang_key, det_name = detect_language(target_code or " ", active_filename)
    if target_code.strip():
        if lang_key in ("cpp", "c") and (active_filename.endswith((".py", ".pyw", "payment_service.py")) or active_filename == "app.py"):
            active_filename = "main.cpp"
        elif lang_key == "python" and (active_filename.endswith((".cpp", ".c", ".h", ".cxx", ".cc")) or active_filename == "main.cpp"):
            active_filename = "app.py"
        elif lang_key == "java" and (active_filename.endswith((".py", ".cpp")) or active_filename == "main.cpp"):
            active_filename = "Main.java"
        elif lang_key == "go" and (active_filename.endswith((".py", ".cpp")) or active_filename == "main.cpp"):
            active_filename = "main.go"
        elif lang_key == "rust" and (active_filename.endswith((".py", ".cpp")) or active_filename == "main.cpp"):
            active_filename = "main.rs"
        elif lang_key in ("javascript", "typescript") and (active_filename.endswith((".py", ".cpp")) or active_filename == "main.cpp"):
            active_filename = "index.js"

    st.session_state["editor_filename"] = active_filename

    with c2:
        safe_det = html.escape(det_name)
        st.markdown(
            f"""
            <div style='padding: 6px 12px; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; margin-top: 24px; font-size: 0.86rem;'>
                🏷️ <b>Detected Engine:</b> <span style='color: #818CF8;'>{safe_det}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return target_code, active_filename
