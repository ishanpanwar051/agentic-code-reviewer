"""
ui/views/scenario_view.py — Preset Polyglot Vulnerability Scenarios View.
"""
from __future__ import annotations

from typing import Tuple
import streamlit as st
from ui.analytics import PRESET_SNIPPETS
from ui.state import pop_target_override


def render_scenario_view() -> Tuple[str, str]:
    """Renders the scenario selection dropdown and returns (code, filename)."""
    scenario_keys = list(PRESET_SNIPPETS.keys())
    selected_scenario = st.selectbox(
        "Select Polyglot Scenario to Inspect:",
        scenario_keys,
        index=0,
        help="Choose a preconfigured code snippet demonstrating real-world CVE and reliability patterns.",
    )

    override_code = pop_target_override()
    target_code = override_code or PRESET_SNIPPETS[selected_scenario]

    if "Python" in selected_scenario:
        active_filename = "app.py"
    elif "C/C++" in selected_scenario:
        active_filename = "process_data.cpp"
    elif "Java" in selected_scenario:
        active_filename = "OrderService.java"
    elif "JavaScript" in selected_scenario or "TypeScript" in selected_scenario:
        active_filename = "profile.js"
    elif "Go" in selected_scenario:
        active_filename = "main.go"
    elif "Rust" in selected_scenario:
        active_filename = "lib.rs"
    elif "PHP" in selected_scenario:
        active_filename = "index.php"
    elif "Clean" in selected_scenario:
        active_filename = "clean_app.py"
    else:
        active_filename = "injection_test.py"

    return target_code, active_filename
