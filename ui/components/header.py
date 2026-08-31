"""
ui/components/header.py — Enterprise Header Navigation Bar for PR Sage.
"""
from __future__ import annotations

import html
import streamlit as st


def render_header(provider_label: str, system_status: str = "System Ready") -> None:
    """Renders the top enterprise navigation bar."""
    clean_provider = provider_label.split(" (")[0]
    safe_provider = html.escape(clean_provider)
    safe_status = html.escape(system_status)

    header_html = f"""
    <div class="enterprise-nav">
        <div class="brand-container">
            <div class="brand-logo-icon">🛡️</div>
            <div>
                <h1 class="brand-title">PR Sage — Enterprise AI Code Reviewer</h1>
                <div class="brand-sub">Autonomous 4-Stage Deterministic Pipeline · Strict Line Clamping · Multi-LLM Engine</div>
            </div>
        </div>
        <div class="nav-badges">
            <span class="engine-pill">⚡ Engine: {safe_provider}</span>
            <span class="status-pill">● {safe_status}</span>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
