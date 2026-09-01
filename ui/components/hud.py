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
    high_count: int,
    medium_count: int,
    low_count: int,
    suggestion_count: int,
    noise_count: int,
    exec_time_ms: int,
    active_ai_label: str,
) -> None:
    """Renders the executive metric score HUD with exact matching counts."""
    safe_grade = html.escape(str(grade))
    safe_ai_label = html.escape(str(active_ai_label))
    quality_ten = round(health_score / 10.0, 1)

    hud_html = (
        '<div class="score-container">'
        '<div class="score-card" title="Overall Code Quality Score out of 10">'
        f'<div class="score-val" style="color: {grade_color};">{quality_ten} <span style="font-size: 1.05rem; font-weight: 500; color: #94A3B8;">/10</span></div>'
        f'<div class="score-lbl">🛡️ Quality Score ({safe_grade})</div>'
        '</div>'
        '<div class="score-card" title="Critical vulnerabilities requiring immediate fix">'
        f'<div class="score-val" style="color: #EF4444;">{crit_count}</div>'
        '<div class="score-lbl">🔴 Critical</div>'
        '</div>'
        '<div class="score-card" title="High severity bugs and security issues">'
        f'<div class="score-val" style="color: #F87171;">{high_count}</div>'
        '<div class="score-lbl">🟠 High</div>'
        '</div>'
        '<div class="score-card" title="Medium reliability and boundary risks">'
        f'<div class="score-val" style="color: #F59E0B;">{medium_count}</div>'
        '<div class="score-lbl">🟡 Medium</div>'
        '</div>'
        '<div class="score-card" title="Low severity notices and style suggestions">'
        f'<div class="score-val" style="color: #818CF8;">{low_count + suggestion_count}</div>'
        '<div class="score-lbl">💡 Suggestions</div>'
        '</div>'
        '<div class="score-card" title="Total round-trip pipeline execution latency">'
        f'<div class="score-val" style="color: #34D399;">{exec_time_ms}<span style="font-size: 0.95rem; font-weight: 500;">ms</span></div>'
        f'<div class="score-lbl">⚡ {safe_ai_label}</div>'
        '</div>'
        '</div>'
    )
    st.markdown(hud_html, unsafe_allow_html=True)
