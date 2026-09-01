"""
ui/dashboard.py — Main Entrypoint for PR Sage Enterprise AI Code Reviewer.
Cohesive, modular architecture adhering to modern SaaS design standards.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from ui.analytics import (
    call_claude,
    call_gemini,
    call_groq,
    call_openai,
    run_static_analysis,
)
from ui.components.header import render_header
from ui.components.onboarding import render_error_state, render_onboarding_banner
from ui.components.sidebar import render_sidebar
from ui.state import (
    compute_signature,
    get_cached_review,
    init_session_state,
    set_cached_review,
)
from ui.styles import get_application_styles
from ui.views.editor_view import render_editor_view
from ui.views.github_view import render_github_view
from ui.views.results_view import render_results_view
from ui.views.scenario_view import render_scenario_view

# Optional backend database integration
try:
    from src.db import DatabaseManager
    from src.models import ReviewComment, ReviewResult, ReviewTelemetry
    BACKEND_DB_AVAILABLE = True
except Exception:
    BACKEND_DB_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 1. Page Configuration & Global Styling
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PR Sage — Enterprise AI Code Reviewer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(get_application_styles(), unsafe_allow_html=True)
init_session_state()

# ─────────────────────────────────────────────────────────────────────────────
# 2. Sidebar Configuration & Top Header
# ─────────────────────────────────────────────────────────────────────────────

provider, user_api_key, selected_model_name, max_issues, strict_added, prompt_guard = render_sidebar()
render_header(provider_label=provider, system_status="System Ready")
render_onboarding_banner()

# ─────────────────────────────────────────────────────────────────────────────
# 3. Target Input Selection
# ─────────────────────────────────────────────────────────────────────────────

mode = st.radio(
    "Select Review Target:",
    ["🧪 Preset Scenarios", "✍️ Custom Code / Diff Editor", "🐙 Live GitHub Pull Request"],
    horizontal=True,
    index=0,
)

if mode == "🧪 Preset Scenarios":
    target_code, active_filename = render_scenario_view()
elif mode == "✍️ Custom Code / Diff Editor":
    target_code, active_filename = render_editor_view()
else:
    target_code, active_filename = render_github_view()

# Ensure filename extension matches detected code language
lang_key, _ = detect_language(target_code or " ", active_filename)
if target_code.strip():
    if lang_key in ("cpp", "c") and active_filename.endswith((".py", ".pyw", "payment_service.py")):
        active_filename = "main.cpp"
    elif lang_key == "python" and active_filename.endswith((".cpp", ".c", ".h")):
        active_filename = "app.py"
    elif lang_key == "java" and active_filename.endswith((".py", ".cpp")):
        active_filename = "Main.java"
    elif lang_key == "go" and active_filename.endswith((".py", ".cpp")):
        active_filename = "main.go"
    elif lang_key == "rust" and active_filename.endswith((".py", ".cpp")):
        active_filename = "main.rs"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Explicit Execution Trigger (Runs ONLY on button click)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
b1, b2, b3 = st.columns([1, 2, 1])
with b2:
    run_btn = st.button("⚡ Run Multi-Stage Agentic Review", type="primary", use_container_width=True)

cached = get_cached_review()
current_sig = compute_signature(provider, active_filename, target_code)

if run_btn:
    if not target_code.strip():
        st.warning("Please paste or select some code before running the review.")
    else:
        with st.spinner("Executing 4-stage pipeline analysis..."):
            start_t = time.time()
            active_ai_label = provider.split(" (")[0]

            try:
                if "Auto-Hybrid" in provider:
                    static_meta, static_findings, traces = run_static_analysis(target_code, active_filename)
                    combined_findings = list(static_findings)
                    ai_ran = False

                    if user_api_key.strip():
                        try:
                            llm_meta, llm_findings, _ = call_gemini(target_code, user_api_key, "gemini-2.0-flash", active_filename)
                            existing_lines = {f.get("line") for f in static_findings}
                            for lf in llm_findings:
                                if lf.get("line") not in existing_lines:
                                    combined_findings.append(lf)
                            active_ai_label = f"Auto-Hybrid (AST + Gemini AI - {static_meta.get('language', 'Polyglot')})"
                            ai_ran = True
                        except Exception:
                            pass

                    if not ai_ran and os.environ.get("GROQ_API_KEY", "").strip():
                        try:
                            groq_key = os.environ.get("GROQ_API_KEY", "").strip()
                            llm_meta, llm_findings, _ = call_groq(target_code, groq_key, "llama-3.1-8b-instant", active_filename)
                            existing_lines = {f.get("line") for f in static_findings}
                            for lf in llm_findings:
                                if lf.get("line") not in existing_lines:
                                    combined_findings.append(lf)
                            active_ai_label = f"Auto-Hybrid (AST + Groq AI - {static_meta.get('language', 'Polyglot')})"
                            ai_ran = True
                        except Exception:
                            pass

                    if not ai_ran:
                        active_ai_label = f"Auto-Hybrid (Polyglot AST - {static_meta.get('language', 'Polyglot')})"

                    findings = combined_findings
                    meta = static_meta

                elif "Gemini" in provider and user_api_key.strip():
                    meta, findings, traces = call_gemini(target_code, user_api_key, selected_model_name, active_filename)
                    active_ai_label = f"Google Gemini ({selected_model_name})"
                elif "Claude" in provider and user_api_key.strip():
                    meta, findings, traces = call_claude(target_code, user_api_key, selected_model_name, active_filename)
                    active_ai_label = f"Anthropic Claude ({selected_model_name})"
                elif "OpenAI" in provider and user_api_key.strip():
                    meta, findings, traces = call_openai(target_code, user_api_key, selected_model_name, active_filename)
                    active_ai_label = f"OpenAI ({selected_model_name})"
                elif "Groq" in provider and user_api_key.strip():
                    meta, findings, traces = call_groq(target_code, user_api_key, selected_model_name, active_filename)
                    active_ai_label = f"Groq ({selected_model_name})"
                else:
                    meta, findings, traces = run_static_analysis(target_code, active_filename)
                    active_ai_label = f"Polyglot AST Engine ({meta.get('language', 'Generic')})"

            except Exception as exc:
                render_error_state(str(exc), fallback_label="Polyglot AST Engine")
                meta, findings, traces = run_static_analysis(target_code, active_filename)
                active_ai_label = f"Polyglot AST Engine ({meta.get('language', 'Generic')})"

            exec_time_ms = int((time.time() - start_t) * 1000)
            set_cached_review(meta, findings, traces, exec_time_ms, active_ai_label, current_sig)

            # Database persistence
            if BACKEND_DB_AVAILABLE:
                try:
                    db = DatabaseManager.get_instance()
                    review_comments = [
                        ReviewComment(
                            path=active_filename,
                            line=f.get("line", 1),
                            severity=f.get("severity", "info"),
                            category="security" if f.get("severity") == "critical" else "bug",
                            cwe_id=f.get("cwe"),
                            comment=f.get("description", f.get("comment", "")),
                            suggested_fix=f.get("fix_code", f.get("fix")),
                            confidence=0.90,
                        )
                        for f in findings
                    ]
                    telemetry = ReviewTelemetry(
                        total_tokens=len(target_code.split()) * 2,
                        latency_ms=exec_time_ms,
                        estimated_cost_usd=round((len(target_code.split()) * 2 / 1000) * 0.0001, 6),
                        model_name=active_ai_label,
                    )
                    rr = ReviewResult(
                        comments=review_comments,
                        summary=meta.get("summary", ""),
                        telemetry=telemetry,
                        patch_content="",
                    )
                    db.save_review(rr, repo="dashboard/console", pr_number=0, filename=active_filename)
                except Exception:
                    pass

# ─────────────────────────────────────────────────────────────────────────────
# 5. Render Results Dashboard View or Clean Ready State
# ─────────────────────────────────────────────────────────────────────────────

cached = get_cached_review()

if cached is not None:
    meta, findings, traces, exec_time_ms, active_ai_label = cached
    st.markdown("---")
    render_results_view(
        filename=active_filename,
        target_code=target_code,
        meta=meta,
        findings=findings,
        traces=traces,
        exec_time_ms=exec_time_ms,
        active_ai_label=active_ai_label,
        max_issues=max_issues,
    )
else:
    st.markdown("---")
    st.markdown("""
    <div class="empty-state">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🚀</div>
        <h3 style="color: #6366F1; margin-bottom: 6px;">Ready to Audit Your Code</h3>
        <p style="color: #94A3B8; font-size: 0.92rem; max-width: 560px; margin: 0 auto;">
            Choose a preset scenario above, write or paste your custom code in the editor, or fetch a live GitHub PR, then click <b>⚡ Run Multi-Stage Agentic Review</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)
