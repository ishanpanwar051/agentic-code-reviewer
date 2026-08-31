"""
ui/components/hud.py — Executive Security HUD & Metric Cards Component.
"""
from __future__ import annotations

import html
import streamlit as st


def render_score_hud(
    health_score: int,
    grade: str,
    grade_color: str,
    crit_count: int,
    warn_count: int,
    noise_count: int,
    exec_time_ms: int,
    active_ai_label: str,
) -> None:
    """Renders the executive metric score HUD."""
    safe_grade = html.escape(str(grade))
    safe_ai_label = html.escape(str(active_ai_label))

    hud_html = f"""
    <div class="score-container">
        <div class="score-card" title="Calculated health score based on critical vulnerabilities (-25) and warnings (-10)">
            <div class="score-val" style="color: {grade_color};">{health_score} <span style="font-size: 1.05rem; font-weight: 500;">/100</span></div>
            <div class="score-lbl">🛡️ Security Score ({safe_grade})</div>
        </div>
        <div class="score-card" title="High-severity vulnerabilities requiring immediate remediation before merge">
            <div class="score-val" style="color: #EF4444;">{crit_count}</div>
            <div class="score-lbl">🔴 Critical Vulnerabilities</div>
        </div>
        <div class="score-card" title="Reliability flaws, unhandled exceptions, and logic crash risks">
            <div class="score-val" style="color: #F59E0B;">{warn_count}</div>
            <div class="score-lbl">🟡 Reliability & Bugs</div>
        </div>
        <div class="score-card" title="False positives and out-of-diff comments eliminated by deterministic guardrails">
            <div class="score-val" style="color: #8B5CF6;">{noise_count}</div>
            <div class="score-lbl">🛡️ Guardrail Filtered</div>
        </div>
        <div class="score-card" title="Total round-trip pipeline execution latency">
            <div class="score-val" style="color: #34D399;">{exec_time_ms}<span style="font-size: 0.95rem; font-weight: 500;">ms</span></div>
            <div class="score-lbl">⚡ {safe_ai_label}</div>
        </div>
    </div>
    """
    st.markdown(hud_html, unsafe_allow_html=True)
