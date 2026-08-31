"""
ui/components/onboarding.py — Onboarding Tour, Empty State, and Error UX Components.
"""
from __future__ import annotations

import html
import streamlit as st
from ui.state import dismiss_tour, is_tour_dismissed


def render_onboarding_banner() -> None:
    """Renders a collapsible/dismissible onboarding tour for new users."""
    if is_tour_dismissed():
        return

    with st.expander("👋 Quick Tour: Getting Started with PR Sage", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("##### 1. Select Code or Live PR")
            st.caption("Choose from realistic polyglot vulnerability presets (Python, C++, Java, Rust, Go), paste your own code, or fetch live open-source PR diffs.")
        with c2:
            st.markdown("##### 2. 4-Stage Deterministic Pipeline")
            st.caption("PR Sage walks AST symbols, audits OWASP/CWE security risks, evaluates error handling, and applies strict deduplication guardrails.")
        with c3:
            st.markdown("##### 3. 1-Click Auto-Fix & Patches")
            st.caption("Review inline comments directly attached to code lines, preview refactored safe code, and download ready-to-merge `git apply fix.patch` files.")

        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        if st.button("✓ Got it! Dismiss Tour", key="btn_dismiss_tour"):
            dismiss_tour()
            st.rerun()


def render_empty_state(filename: str) -> None:
    """Renders clean approved empty state when zero vulnerabilities are detected."""
    safe_fn = html.escape(str(filename))
    st.markdown(f"""
    <div class="empty-state">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🎉</div>
        <h3 style="color: #10B981; margin-bottom: 4px;">Codebase Approved! Zero Vulnerabilities Detected</h3>
        <p style="color: #94A3B8; font-size: 0.9rem; max-width: 500px; margin: 0 auto;">
            All 4 pipeline stages passed for <code>{safe_fn}</code>. No critical security flaws, unhandled exceptions, or prompt injection directives found.
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_error_state(error_message: str, fallback_label: str = "Polyglot AST Engine") -> None:
    """Renders a friendly error notification with graceful degradation notes."""
    safe_msg = html.escape(str(error_message))
    safe_fb = html.escape(str(fallback_label))
    st.warning(f"⚠️ Remote AI inference note: `{safe_msg}`. Seamlessly switched to **{safe_fb}**.")
