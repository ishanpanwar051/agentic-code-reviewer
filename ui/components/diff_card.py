"""
ui/components/diff_card.py — Autonomous Verification & Proof Card Component.
"""
from __future__ import annotations

import html
import textwrap
from typing import Any
import streamlit as st
from ui.components.badges import render_confidence_badge, render_cwe_badge, render_severity_badge


def render_diff_card(
    filename: str,
    finding: dict[str, Any],
    active_ai_label: str,
) -> None:
    """Renders a self-verifying autonomous proof card with PoC, impact, and verified status."""
    line_no = finding.get("line", "N/A")
    title_text = finding.get("title", "Detected Issue")
    severity = finding.get("severity", "HIGH")
    cwe = finding.get("cwe")
    confidence = finding.get("confidence", 0.90)
    bad_code = finding.get("bad_code", finding.get("code", finding.get("bad_snippet", "")))
    fix_code = finding.get("fix_code", finding.get("suggested_fix", finding.get("fix", "")))
    description = finding.get("description", finding.get("explanation", finding.get("comment", "")))
    evidence = finding.get("evidence")
    impact = finding.get("impact")
    poc = finding.get("proof_of_concept", {})

    safe_fn = html.escape(str(filename))
    safe_title = html.escape(str(title_text))
    safe_bad = html.escape(str(bad_code))
    safe_fix = html.escape(str(fix_code))
    safe_desc = html.escape(str(description))
    safe_ai = html.escape(str(active_ai_label))
    safe_evidence = html.escape(str(evidence)) if evidence else ""
    safe_impact = html.escape(str(impact)) if impact else ""

    cwe_badge_html = render_cwe_badge(cwe)
    sev_badge_html = render_severity_badge(severity)
    conf_badge_html = render_confidence_badge(confidence)

    bad_line_html = f'<div class="diff-bad-line">❌ - {safe_bad}</div>' if safe_bad else ""
    evidence_html = f'<div style="font-size: 0.82rem; color: #38BDF8; background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38BDF8; padding: 4px 8px; margin: 6px 0; border-radius: 0 4px 4px 0;">🔎 <b>Evidence:</b> {safe_evidence}</div>' if safe_evidence else ""
    impact_html = f'<div style="font-size: 0.82rem; color: #FB923C; background: rgba(251, 146, 60, 0.08); border-left: 3px solid #FB923C; padding: 4px 8px; margin: 6px 0; border-radius: 0 4px 4px 0;">💥 <b>Downstream Impact:</b> {safe_impact}</div>' if safe_impact else ""

    # Proof of Concept / Sandbox Verification Block (Strictly unindented to prevent Markdown codeblock conversion)
    poc_html = ""
    if poc and isinstance(poc, dict) and poc.get("code"):
        poc_code = html.escape(str(poc.get("code", "")))
        poc_out = html.escape(str(poc.get("runtime_output", "")))
        poc_html = (
            '<div style="margin-top: 8px; padding: 8px; background: rgba(15, 23, 42, 0.6); border: 1px dashed rgba(99, 102, 241, 0.4); border-radius: 6px;">'
            '<div style="font-size: 0.78rem; font-weight: 700; color: #818CF8; margin-bottom: 4px; display: flex; justify-content: space-between;">'
            '<span>🧪 SANDBOX REPRODUCTION PROOF (Auto-PoC)</span>'
            '<span style="color: #34D399;">✓ Executed in Sandbox</span>'
            '</div>'
            f'<pre style="margin: 0; padding: 4px 8px; background: #0B0D13; border-radius: 4px; font-size: 0.76rem; color: #CBD5E1; overflow-x: auto;">{poc_code}</pre>'
            f'<div style="margin-top: 4px; font-size: 0.76rem; font-family: monospace; color: #F87171; background: rgba(239, 68, 68, 0.1); padding: 2px 6px; border-radius: 4px;">{poc_out}</div>'
            '</div>'
        )

    fix_line_html = ""
    if safe_fix:
        fix_line_html = (
            '<div style="margin-top: 10px;">'
            '<div style="font-size: 0.82rem; color: #A78BFA; font-weight: 600; margin-bottom: 4px; display: flex; justify-content: space-between;">'
            '<span>Suggested Safe Replacement:</span>'
            '<span style="color: #34D399; font-size: 0.75rem;">✓ 1-Click Patch Ready</span>'
            '</div>'
            f'<div class="diff-fix-line">✅ + {safe_fix}</div>'
            '</div>'
        )

    # Build entire card without leading 4-space indentation
    card_html = (
        '<div class="diff-card">'
        '<div class="diff-header">'
        f'<div><b>{safe_fn}:{line_no}</b> — {safe_title}</div>'
        '<div style="display: flex; gap: 6px; align-items: center;">'
        f'{conf_badge_html}'
        f'{cwe_badge_html}'
        f'{sev_badge_html}'
        '</div>'
        '</div>'
        '<div class="diff-body">'
        f'{bad_line_html}'
        '<div class="comment-thread">'
        f'<div class="comment-author">🤖 PR Sage Verification Engine ({safe_ai})</div>'
        f'<div class="comment-text"><b>Why:</b> {safe_desc}</div>'
        f'{evidence_html}'
        f'{impact_html}'
        f'{poc_html}'
        f'{fix_line_html}'
        '</div>'
        '</div>'
        '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)
