"""
ui/state.py — Typed Session State Management for PR Sage Dashboard.
Eliminates magic strings, isolates render from execution side-effects, and prevents rerun loops.
"""
from __future__ import annotations

import time
from typing import Any
import uuid
import streamlit as st


class StateKeys:
    MODE = "app_mode"
    DIFF = "app_diff"
    TARGET_OVERRIDE = "app_target_override"
    REVIEW_CACHE = "app_review_cache"
    LAST_SIGNATURE = "app_last_signature"
    ACTIVE_FILENAME = "app_active_filename"
    TOUR_DISMISSED = "app_tour_dismissed"
    REVIEW_ID = "app_review_id"


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
        st.session_state[StateKeys.ACTIVE_FILENAME] = "main.cpp"
    if StateKeys.TOUR_DISMISSED not in st.session_state:
        st.session_state[StateKeys.TOUR_DISMISSED] = False
    if StateKeys.REVIEW_ID not in st.session_state:
        st.session_state[StateKeys.REVIEW_ID] = str(uuid.uuid4())[:8]


def get_cached_review() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], int, str, str] | None:
    """Retrieves cached (meta, findings, traces, exec_time_ms, ai_label, review_id) tuple if present."""
    return st.session_state.get(StateKeys.REVIEW_CACHE)


def set_cached_review(
    meta: dict[str, Any],
    findings: list[dict[str, Any]],
    traces: dict[str, Any],
    exec_time_ms: int,
    ai_label: str,
    signature: str,
) -> str:
    """Saves completed review payload with unique review ID and updates last execution signature."""
    review_id = f"rev-{int(time.time())}-{str(uuid.uuid4())[:6]}"
    st.session_state[StateKeys.REVIEW_ID] = review_id
    st.session_state[StateKeys.REVIEW_CACHE] = (meta, findings, traces, exec_time_ms, ai_label, review_id)
    st.session_state[StateKeys.LAST_SIGNATURE] = signature
    return review_id


def compute_signature(provider: str, filename: str, code: str) -> str:
    """Computes a deterministic hash signature of current review parameters."""
    return f"{provider}:{filename}:{hash(code)}"


def set_target_override(code: str) -> None:
    """Sets code buffer override for subsequent editor render."""
    st.session_state[StateKeys.TARGET_OVERRIDE] = code


def pop_target_override() -> str | None:
    """Consumes and clears any active code buffer override."""
    return st.session_state.pop(StateKeys.TARGET_OVERRIDE, None)


def dismiss_tour() -> None:
    """Marks onboarding tour as dismissed in session state."""
    st.session_state[StateKeys.TOUR_DISMISSED] = True


def is_tour_dismissed() -> bool:
    """Returns True if user has dismissed the onboarding tour."""
    return bool(st.session_state.get(StateKeys.TOUR_DISMISSED, False))
