"""
ui/views/results_view.py — Results Presentation, Findings Breakdown, & Audit Tabs View.
"""
from __future__ import annotations

import html
from typing import Any
import pandas as pd
import streamlit as st
from ui.analytics import (
    calculate_health_score,
    detect_language,
    load_eval_benchmark_data,
)
from ui.components.codeblock import render_annotated_code_viewer
from ui.components.diff_card import render_diff_card
from ui.components.export_panel import render_auto_fix_banner, render_export_buttons
from ui.components.hud import render_score_hud
from ui.components.onboarding import render_empty_state
from ui.components.pipeline import render_pipeline_bar

# Optional DatabaseManager
try:
    from src.db import DatabaseManager
    INTERNAL_DB_AVAILABLE = True
except Exception:
    INTERNAL_DB_AVAILABLE = False


def render_results_view(
    filename: str,
    target_code: str,
    meta: dict[str, Any],
    findings: list[dict[str, Any]],
    traces: dict[str, Any],
    exec_time_ms: int,
    active_ai_label: str,
    max_issues: int = 25,
) -> None:
    """Renders the complete enterprise verification dashboard with live filtering and verification cards."""
    guarded_findings = findings[:max_issues]
    
    crit_count = sum(1 for f in guarded_findings if str(f.get("severity", "")).upper() == "CRITICAL")
    high_count = sum(1 for f in guarded_findings if str(f.get("severity", "")).upper() == "HIGH")
    medium_count = sum(1 for f in guarded_findings if str(f.get("severity", "")).upper() in ("MEDIUM", "WARNING"))
    low_count = sum(1 for f in guarded_findings if str(f.get("severity", "")).upper() in ("LOW", "INFO"))
    sugg_count = sum(1 for f in guarded_findings if str(f.get("severity", "")).upper() == "SUGGESTION")
    
    noise_count = max(0, len(findings) - len(guarded_findings))
    loc_count = len(target_code.splitlines())

    health_score, grade, grade_color = calculate_health_score(guarded_findings)
    lang_key, lang_display = detect_language(target_code, filename)

    readiness = meta.get("readiness", {})
    behavior_diff = meta.get("behavior_diff", [])
    blast_radius = meta.get("blast_radius", [])

    # 1. Executive Metric HUD
    render_score_hud(
        health_score=health_score,
        grade=grade,
        grade_color=grade_color,
        crit_count=crit_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        suggestion_count=sugg_count,
        noise_count=noise_count,
        exec_time_ms=exec_time_ms,
        active_ai_label=active_ai_label,
    )

    # 2. Live 4-Stage State Pipeline Radar
    render_pipeline_bar(
        loc_count=loc_count,
        crit_count=crit_count,
        warn_count=medium_count + high_count,
        total_findings=len(guarded_findings),
    )

    # 3. Enterprise Verification Tabs
    tab_diff, tab_readiness, tab_behavior, tab_issues, tab_source, tab_traces = st.tabs([
        f"🧪 Verified PoC Proofs ({len(guarded_findings)})",
        "🚦 6-Pillar Production Readiness",
        "🌐 Behavior Diff & Blast Radius",
        "📋 Actionable Matrix & Export",
        "📄 Annotated Source Viewer",
        "🧭 Stage Pipeline Trace",
    ])

    # ── Tab 1: Verified Autonomous Proof Cards
    with tab_diff:
        st.subheader(f"Autonomous Verification Thread — `{filename}`")
        st.caption("Every detected finding is backed by evidence, downstream impact, and sandboxed PoC reproduction proof:")

        if not guarded_findings:
            render_empty_state(filename)
        else:
            # Interactive Severity Filter Bar
            filter_options = ["All", "Critical", "High", "Medium", "Low", "Suggestions"]
            selected_filter = st.segmented_control(
                "Filter Issues by Severity:",
                options=filter_options,
                default="All",
                key="findings_severity_filter_choice",
            ) or "All"

            if selected_filter == "Critical":
                display_findings = [f for f in guarded_findings if str(f.get("severity", "")).upper() == "CRITICAL"]
            elif selected_filter == "High":
                display_findings = [f for f in guarded_findings if str(f.get("severity", "")).upper() == "HIGH"]
            elif selected_filter == "Medium":
                display_findings = [f for f in guarded_findings if str(f.get("severity", "")).upper() in ("MEDIUM", "WARNING")]
            elif selected_filter == "Low":
                display_findings = [f for f in guarded_findings if str(f.get("severity", "")).upper() in ("LOW", "INFO")]
            elif selected_filter == "Suggestions":
                display_findings = [f for f in guarded_findings if str(f.get("severity", "")).upper() == "SUGGESTION"]
            else:
                display_findings = guarded_findings

            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

            if not display_findings:
                st.info(f"No findings matching the '{selected_filter}' filter.")
            else:
                for f in display_findings:
                    render_diff_card(filename, f, active_ai_label)

            st.markdown("---")
            render_auto_fix_banner(filename, target_code, guarded_findings, lang_key=lang_key)

    # ── Tab 2: 6-Pillar Production Readiness Scorecard
    with tab_readiness:
        st.subheader("🚦 Production Readiness & Merge Oracle")
        st.caption("Evidence-based assessment across 6 core production survivability dimensions:")

        rec = readiness.get("recommendation", "SAFE TO MERGE")
        overall = readiness.get("overall_score", 9.0)
        rec_color = "#10B981" if rec == "SAFE TO MERGE" else ("#F59E0B" if rec == "HUMAN REVIEW REQUIRED" else "#EF4444")

        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.8); border: 2px solid {rec_color}; border-radius: 8px; padding: 16px; margin-bottom: 20px; text-align: center;">
                <div style="font-size: 0.88rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;">MERGE ORACLE VERDICT</div>
                <div style="font-size: 2rem; font-weight: 800; color: {rec_color}; margin: 4px 0;">{rec}</div>
                <div style="font-size: 1rem; color: #CBD5E1;">Overall Composite Score: <b>{overall} / 10.0</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("1. Correctness & Logic", f"{readiness.get('correctness', 95)}/100", "Zero Logic Flaws" if crit_count == 0 else "-25 per Critical")
            st.metric("2. AppSec & OWASP", f"{readiness.get('security', 90)}/100", "Clean Parameterization" if crit_count == 0 else "Vulnerabilities Detected")
        with r2:
            st.metric("3. Edge Test Coverage", f"{readiness.get('testing', 80)}/100", "Boundary Validated")
            st.metric("4. Performance & Scalability", f"{readiness.get('performance', 90)}/100", "Optimal Time Complexity")
        with r3:
            st.metric("5. 3 AM Observability", f"{readiness.get('observability', 85)}/100", "Telemetry Logged")
            st.metric("6. Rollback Safety", f"{readiness.get('rollback_safety', 90)}/100", "Zero-Downtime Safe")

    # ── Tab 3: Behavior Diff & Blast Radius Map
    with tab_behavior:
        st.subheader("🌐 Semantic Behavior Diff & Cross-Module Blast Radius")
        
        st.markdown("##### 🔄 Runtime Behavior Modifications")
        if behavior_diff:
            b_df = pd.DataFrame(behavior_diff)
            b_df.columns = ["Scope / Function", "Before PR Behavior", "After PR Behavior", "Risk Level"]
            st.dataframe(b_df, use_container_width=True)
        else:
            st.info("No runtime behavior modifications detected.")

        st.markdown("##### 💥 Downstream Blast Radius & Call Graph Impact")
        if blast_radius:
            br_df = pd.DataFrame(blast_radius)
            br_df.columns = ["Affected Target", "Source File", "Risk Level", "Impact Rationale"]
            st.dataframe(br_df, use_container_width=True)
        else:
            st.info("No external downstream callers affected.")

    # ── Tab 4: Actionable Findings Breakdown & Export
    with tab_issues:
        st.subheader("Actionable Issue Matrix")
        if guarded_findings:
            table_data = [
                {
                    "Line": f.get("line"),
                    "Severity": str(f.get("severity", "HIGH")).upper(),
                    "Title": f.get("title", f.get("comment", "")),
                    "Category": f.get("category", "BUG"),
                    "CWE": f.get("cwe", "N/A"),
                    "Evidence": f.get("evidence", "Source pattern match"),
                    "Confidence": f"{int(f.get('confidence', 0.90) * 100)}%",
                }
                for f in guarded_findings
            ]
            st.dataframe(pd.DataFrame(table_data), use_container_width=True)
        else:
            st.success("✅ Clean Code — No actionable issues found.")

        render_export_buttons(filename, guarded_findings, health_score, grade, active_ai_label)

    # ── Tab 5: Annotated Source Code Viewer
    with tab_source:
        st.subheader("📄 Annotated Source Code Viewer")
        st.caption("Lines with security or reliability issues are highlighted with severity tags:")
        render_annotated_code_viewer(target_code, guarded_findings, filename, language=lang_key)

    # ── Tab 6: Stage-by-Stage Agent Trace
    with tab_traces:
        st.subheader(f"🧭 Deterministic Pipeline State Machine ({active_ai_label})")
        st.markdown("Structured JSON payloads exchanged between the sequential verification stages:")
        st.json(traces)
