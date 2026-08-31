"""
ui/state.py — Typed Session State Management for PR Sage Dashboard.
Eliminates magic strings, isolates render from execution side-effects, and prevents rerun loops.
"""
from __future__ import annotations

from typing import Any
import streamlit as st


class StateKeys:
    MODE = "app_mode"
    DIFF = "app_diff"
    TARGET_OVERRIDE = "app_target_override"
    REVIEW_CACHE = "app_review_cache"
    LAST_SIGNATURE = "app_last_signature"
    ACTIVE_FILENAME = "app_active_filename"
    TOUR_DISMISSED = "app_tour_dismissed"


def init_session_state() -> None:
    """Initializes standard session state keys if not already present."""
    if StateKeys.MODE not in st.session_state:
        st.session_state[StateKeys.MODE] = "🧪 Preset Scenarios"
    if StateKeys.DIFF not in st.session_state:
        st.session_state[StateKeys.DIFF] = ""
    if StateKeys.TARGET_OVERRIDE not in st.session_state:
        st.session_state[StateKeys.TARGET_OVERRIDE] = None
    if StateKeys.REVIEW_CACHE not in st.session_state:
        st.session_state[StateKeys.REVIEW_CACHE] = None
    if StateKeys.LAST_SIGNATURE not in st.session_state:
        st.session_state[StateKeys.LAST_SIGNATURE] = ""
    if StateKeys.ACTIVE_FILENAME not in st.session_state:
        st.session_state[StateKeys.ACTIVE_FILENAME] = "app.py"
    if StateKeys.TOUR_DISMISSED not in st.session_state:
        st.session_state[StateKeys.TOUR_DISMISSED] = False


def get_cached_review() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], int, str] | None:
    """Retrieves cached (meta, findings, traces, exec_time_ms, ai_label) tuple if present."""
    return st.session_state.get(StateKeys.REVIEW_CACHE)


def set_cached_review(
    meta: dict[str, Any],
    findings: list[dict[str, Any]],
    traces: dict[str, Any],
    exec_time_ms: int,
    ai_label: str,
    signature: str,
) -> None:
    """Saves completed review payload and updates last execution signature."""
    st.session_state[StateKeys.REVIEW_CACHE] = (meta, findings, traces, exec_time_ms, ai_label)
    st.session_state[StateKeys.LAST_SIGNATURE] = signature


def compute_signature(provider: str, filename: str, code: str) -> str:
    """Computes a deterministic hash signature of current review parameters."""
    return f"{provider}:{filename}:{hash(code)}"


def pop_target_override() -> str | None:
    """Retrieves and clears one-time code override (e.g. from Auto-Fix)."""
    override = st.session_state.get(StateKeys.TARGET_OVERRIDE)
    if override is not None:
        st.session_state[StateKeys.TARGET_OVERRIDE] = None
    return override


def set_target_override(code: str) -> None:
    """Sets a one-time code override to load into the active editor or viewer."""
    st.session_state[StateKeys.TARGET_OVERRIDE] = code
    st.session_state[StateKeys.DIFF] = code


def is_tour_dismissed() -> bool:
    """Returns True if the user dismissed the onboarding guide."""
    return bool(st.session_state.get(StateKeys.TOUR_DISMISSED, False))


def dismiss_tour() -> None:
    """Marks onboarding tour as dismissed."""
    st.session_state[StateKeys.TOUR_DISMISSED] = True
