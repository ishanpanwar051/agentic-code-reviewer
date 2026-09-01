"""
ui/components/export_panel.py — Automated Patch Delivery & Report Export Component.
"""
from __future__ import annotations

import json
from typing import Any
import streamlit as st
from ui.analytics import generate_git_patch, generate_markdown_report, generate_refactored_code
from ui.components.codeblock import render_diff_code_preview
from ui.state import set_target_override


def render_auto_fix_banner(
    filename: str,
    original_code: str,
    guarded_findings: list[dict[str, Any]],
    lang_key: str = "python",
) -> None:
    """Renders the 1-Click in-browser Auto-Fix expander."""
    if not guarded_findings:
        return

    with st.expander("✨ 1-Click In-Browser Auto-Fix (Apply All Recommendations)", expanded=False):
        st.markdown("Automatically applies all validated safe replacements to produce clean, hardened code:")

        refactored_code = generate_refactored_code(original_code, guarded_findings)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.download_button(
                label=f"📥 Download Refactored File (`fixed_{filename}`)",
                data=refactored_code,
                file_name=f"fixed_{filename}",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            if st.button("🔄 Apply Fixes to Editor & Re-Scan", use_container_width=True):
                set_target_override(refactored_code)
                st.rerun()

        st.markdown("---")
        render_diff_code_preview(original_code, refactored_code, language=lang_key)


def render_export_buttons(
    filename: str,
    guarded_findings: list[dict[str, Any]],
    health_score: int,
    grade: str,
    active_ai_label: str,
) -> None:
    """Renders export action buttons for Git Patch, Markdown, and JSON."""
    st.markdown("---")
    st.subheader("📦 Export & Automated Patch Delivery")

    col1, col2, col3 = st.columns(3)

    git_patch = generate_git_patch(filename, guarded_findings, active_ai_label)
    md_report = generate_markdown_report(filename, guarded_findings, health_score, grade, active_ai_label)
    json_report = json.dumps(guarded_findings, indent=2)

    with col1:
        st.download_button(
            label="📥 Download `git apply fix.patch`",
            data=git_patch,
            file_name="fix.patch",
            mime="text/plain",
            use_container_width=True,
            help="Apply instantly in your terminal with: git apply fix.patch",
        )
    with col2:
        st.download_button(
            label="📥 Download Markdown (`review.md`)",
            data=md_report,
            file_name="review.md",
            mime="text/markdown",
            use_container_width=True,
            help="Executive Markdown summary suitable for GitHub PR descriptions or tickets.",
        )
    with col3:
        st.download_button(
            label="📥 Download JSON (`review.json`)",
            data=json_report,
            file_name="review.json",
            mime="application/json",
            use_container_width=True,
            help="Full structured JSON findings for CI/CD integration and automated ingestion.",
        )
