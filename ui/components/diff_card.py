"""
ui/components/diff_card.py — GitHub PR-Style Inline Review Comment Card Component.
"""
from __future__ import annotations

import html
from typing import Any
import streamlit as st
from ui.components.badges import render_cwe_badge, render_severity_badge


def render_diff_card(
    filename: str,
    finding: dict[str, Any],
    active_ai_label: str,
) -> None:
    """Renders a single GitHub PR inline review card attached to a specific line."""
    line_no = finding.get("line", "N/A")
    title_text = finding.get("title", "Detected Issue")
    severity = finding.get("severity", "info")
    cwe = finding.get("cwe")
    bad_code = finding.get("bad_code", finding.get("bad_snippet", ""))
    fix_code = finding.get("fix_code", finding.get("fix", ""))
    description = finding.get("description", finding.get("comment", ""))

    safe_fn = html.escape(str(filename))
    safe_title = html.escape(str(title_text))
    safe_bad = html.escape(str(bad_code))
    safe_fix = html.escape(str(fix_code))
    safe_desc = html.escape(str(description))
    safe_ai = html.escape(str(active_ai_label))

    cwe_badge_html = render_cwe_badge(cwe)
    sev_badge_html = render_severity_badge(severity)

    bad_line_html = f'<div class="diff-bad-line">❌ - {safe_bad}</div>' if safe_bad else ""
    fix_line_html = f'<div style="font-size: 0.82rem; color: #A78BFA; font-weight: 600; margin-top: 8px; margin-bottom: 4px;">Suggested Safe Replacement:</div><div class="diff-fix-line">✅ + {safe_fix}</div>' if safe_fix else ""

    card_html = f"""
    <div class="diff-card">
        <div class="diff-header">
            <div><b>{safe_fn}:{line_no}</b> — {safe_title}</div>
            <div style="display: flex; gap: 6px; align-items: center;">
                {cwe_badge_html}
                {sev_badge_html}
            </div>
        </div>
        <div class="diff-body">
            {bad_line_html}
            <div class="comment-thread">
                <div class="comment-author">🤖 PR Sage ({safe_ai})</div>
                <div class="comment-text">{safe_desc}</div>
                {fix_line_html}
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
