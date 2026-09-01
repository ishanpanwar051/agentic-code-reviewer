"""
ui/components/pipeline.py — Live 4-Stage Deterministic Pipeline Radar Component.
"""
from __future__ import annotations

import streamlit as st


def render_pipeline_bar(
    loc_count: int,
    crit_count: int,
    warn_count: int,
    total_findings: int,
) -> None:
    """Renders the horizontal 4-stage pipeline execution bar."""
    dot1 = "step-dot-ok"
    dot2 = "step-dot-crit" if crit_count > 0 else "step-dot-ok"
    dot3 = "step-dot-warn" if warn_count > 0 else "step-dot-ok"
    dot4 = "step-dot-ok"

    pipeline_html = (
        '<div class="pipeline-bar">'
        '<div class="pipeline-step">'
        f'<span class="step-dot {dot1}"></span>'
        f'<span><b>1. Understand:</b> AST Walk ({loc_count} LOC)</span>'
        '</div>'
        '<div class="pipeline-arrow">➔</div>'
        '<div class="pipeline-step">'
        f'<span class="step-dot {dot2}"></span>'
        f'<span><b>2. Security:</b> {crit_count} Vulnerabilities (CWE/OWASP)</span>'
        '</div>'
        '<div class="pipeline-arrow">➔</div>'
        '<div class="pipeline-step">'
        f'<span class="step-dot {dot3}"></span>'
        f'<span><b>3. Error Handling:</b> {warn_count} Crash Risks</span>'
        '</div>'
        '<div class="pipeline-arrow">➔</div>'
        '<div class="pipeline-step">'
        f'<span class="step-dot {dot4}"></span>'
        f'<span><b>4. Review & Guardrails:</b> {total_findings} Actionable Issues</span>'
        '</div>'
        '</div>'
    )
    st.markdown(pipeline_html, unsafe_allow_html=True)
