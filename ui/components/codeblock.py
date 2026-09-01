"""
ui/components/codeblock.py — Syntax-Highlighted Code Viewer & Diff Preview Component.
"""
from __future__ import annotations

import html
from typing import Any
import streamlit as st


def render_annotated_code_viewer(
    code: str,
    findings: list[dict[str, Any]],
    filename: str,
    language: str = "cpp",
) -> None:
    """Renders line-numbered code viewer highlighting lines with detected findings."""
    lines = code.splitlines()
    findings_by_line: dict[int, list[dict[str, Any]]] = {}
    for f in findings:
        l_num = f.get("line", 1)
        findings_by_line.setdefault(l_num, []).append(f)

    html_lines = []
    for idx, raw_line in enumerate(lines, start=1):
        safe_code = html.escape(raw_line) if raw_line else "&nbsp;"
        line_findings = findings_by_line.get(idx, [])
        if line_findings:
            sev = line_findings[0].get("severity", "HIGH").upper()
            badge_color = "#EF4444" if sev in ("CRITICAL", "HIGH") else "#F59E0B"
            bg_style = "background: rgba(239, 68, 68, 0.12); border-left: 3px solid #EF4444;" if sev in ("CRITICAL", "HIGH") else "background: rgba(245, 158, 11, 0.12); border-left: 3px solid #F59E0B;"
            title = html.escape(str(line_findings[0].get("title", "Issue")))
            indicator = f'<span style="background: {badge_color}; color: #FFFFFF; font-size: 0.68rem; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-left: 8px;" title="{title}">⚠ {sev}</span>'
        else:
            bg_style = "border-left: 3px solid transparent;"
            indicator = ""

        html_lines.append(
            f'<div style="display: flex; font-family: monospace; font-size: 0.85rem; padding: 2px 8px; {bg_style}">'
            f'<span style="color: #64748B; width: 42px; user-select: none; text-align: right; margin-right: 14px;">{idx}</span>'
            f'<span style="color: #E2E8F0; flex: 1; white-space: pre-wrap; word-break: break-all;">{safe_code}</span>'
            f'{indicator}'
            f'</div>'
        )

    viewer_html = f"""
    <div style="background: #0D1117; border: 1px solid #30363D; border-radius: 8px; padding: 8px 0; margin-bottom: 16px; overflow-x: auto; max-height: 420px;">
        <div style="padding: 4px 12px; border-bottom: 1px solid #21262D; margin-bottom: 6px; font-size: 0.8rem; color: #8B949E; font-family: monospace;">
            📄 <b>{html.escape(filename)}</b> ({len(lines)} lines)
        </div>
        {''.join(html_lines)}
    </div>
    """
    st.markdown(viewer_html, unsafe_allow_html=True)


def render_diff_code_preview(
    original_code: str,
    refactored_code: str,
    language: str = "cpp",
) -> None:
    """Renders a structured Before vs After side-by-side or split code preview."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Original Code (With Vulnerabilities)**")
        st.code(original_code, language=language, line_numbers=True)
    with col2:
        st.markdown("**🟢 Refactored Code (All Safe Fixes Applied)**")
        st.code(refactored_code, language=language, line_numbers=True)
