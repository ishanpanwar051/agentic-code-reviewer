"""
ui/components/badges.py — Standardized pill badge components with HTML sanitization.
"""
from __future__ import annotations

import html


def render_severity_badge(severity: str) -> str:
    """Renders a styled severity badge (CRITICAL, HIGH, MEDIUM, LOW, SUGGESTION)."""
    sev_upper = (severity or "MEDIUM").upper().strip()
    if sev_upper == "CRITICAL":
        return '<span class="badge-crit">🔴 CRITICAL</span>'
    elif sev_upper == "HIGH":
        return '<span class="badge-crit" style="background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.5); color: #F87171;">🟠 HIGH</span>'
    elif sev_upper == "MEDIUM":
        return '<span class="badge-warn">🟡 MEDIUM</span>'
    elif sev_upper == "LOW":
        return '<span class="badge-info">🔵 LOW</span>'
    elif sev_upper == "SUGGESTION":
        return '<span class="badge-info" style="background: rgba(139, 92, 246, 0.15); border-color: rgba(139, 92, 246, 0.4); color: #C084FC;">💡 SUGGESTION</span>'
    elif sev_upper == "WARNING":
        return '<span class="badge-warn">🟡 WARNING</span>'
    else:
        return '<span class="badge-info">🔵 INFO</span>'


def render_confidence_badge(confidence: float | None) -> str:
    """Renders a confidence probability badge."""
    if confidence is None:
        return ""
    conf_pct = int(confidence * 100) if confidence <= 1.0 else int(confidence)
    if conf_pct >= 85:
        color_style = "color: #34D399; background: rgba(52, 211, 153, 0.12); border: 1px solid rgba(52, 211, 153, 0.3);"
    elif conf_pct >= 70:
        color_style = "color: #FCD34D; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3);"
    else:
        color_style = "color: #94A3B8; background: rgba(148, 163, 184, 0.12); border: 1px solid rgba(148, 163, 184, 0.3);"

    return f'<span style="font-size: 0.75rem; font-family: monospace; padding: 2px 8px; border-radius: 4px; font-weight: 600; {color_style}">🎯 {conf_pct}% Conf.</span>'


def render_cwe_badge(cwe: str | None) -> str:
    """Renders a styled CWE security tag badge."""
    if not cwe:
        return '<span class="badge-cwe">AppSec</span>'
    safe_cwe = html.escape(str(cwe))
    return f'<span class="badge-cwe">{safe_cwe}</span>'


def render_engine_badge(engine_name: str) -> str:
    """Renders a monospace engine badge."""
    safe_name = html.escape(str(engine_name))
    return f'<span class="engine-pill">⚡ {safe_name}</span>'
