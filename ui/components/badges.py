"""
ui/components/badges.py — Standardized pill badge components with HTML sanitization.
"""
from __future__ import annotations

import html


def render_severity_badge(severity: str) -> str:
    """Renders a styled severity badge (Critical, Warning, Info)."""
    sev_lower = (severity or "info").lower().strip()
    if sev_lower == "critical":
        return '<span class="badge-crit">🔴 CRITICAL</span>'
    elif sev_lower == "warning":
        return '<span class="badge-warn">🟡 WARNING</span>'
    else:
        return '<span class="badge-info">🔵 INFO</span>'


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
