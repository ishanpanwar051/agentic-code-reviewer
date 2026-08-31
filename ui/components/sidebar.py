"""
ui/components/sidebar.py — AI Model Hub & Guardrail Configuration Sidebar.
"""
from __future__ import annotations

import os
from typing import Tuple
import streamlit as st


def render_sidebar() -> Tuple[str, str, str, int, bool, bool]:
    """Renders the enterprise configuration sidebar and returns selected settings."""
    with st.sidebar:
        st.markdown("### 🧠 AI Model Hub")

        provider = st.selectbox(
            "Select AI Engine Mode",
            [
                "🔥 Auto-Hybrid Pipeline (AST + AI Deep Logic - Recommended)",
                "⚡ Built-in AST Only (Offline / Zero-Network)",
                "✨ Google Gemini (Gemini 2.0 Flash / 1.5 Pro)",
                "🟣 Anthropic Claude (Claude 3.5 Sonnet / Haiku)",
                "🧠 OpenAI (GPT-4o / GPT-4o-mini / Codex)",
                "☁️ Groq Cloud (Llama 3.3 70B / Llama 3.1 8B)",
                "🦙 Local Ollama (localhost:11434)"
            ],
            index=0,
            help="Auto-Hybrid runs instant polyglot compiler AST rules + Deep AI reasoning concurrently!",
        )

        user_api_key = ""
        selected_model_name = ""

        if "Gemini" in provider or "Auto-Hybrid" in provider:
            user_api_key = st.text_input(
                "Gemini / LLM API Key (Optional for Deep Logic)",
                value=os.environ.get("GEMINI_API_KEY", ""),
                type="password",
                help="Optional: If provided, LLM performs deep semantic audit in addition to AST rules.",
            )
            selected_model_name = "gemini-2.0-flash"

        elif "Claude" in provider:
            user_api_key = st.text_input(
                "Anthropic API Key",
                value=os.environ.get("ANTHROPIC_API_KEY", ""),
                type="password",
                help="API key from console.anthropic.com",
            )
            selected_model_name = st.selectbox(
                "Claude Model",
                ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
            )

        elif "OpenAI" in provider:
            user_api_key = st.text_input(
                "OpenAI API Key",
                value=os.environ.get("OPENAI_API_KEY", ""),
                type="password",
                help="API key from platform.openai.com",
            )
            selected_model_name = st.selectbox(
                "OpenAI Model",
                ["gpt-4o", "gpt-4o-mini", "o1-mini"],
            )

        elif "Groq" in provider:
            user_api_key = st.text_input(
                "Groq API Key",
                value=os.environ.get("GROQ_API_KEY", ""),
                type="password",
                help="Free low-latency key from console.groq.com",
            )
            selected_model_name = st.selectbox(
                "Groq Model",
                ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            )

        elif "Ollama" in provider:
            selected_model_name = st.text_input("Ollama Model Tag", value="llama3.2:3b")

        st.markdown("---")
        st.markdown("### 🛡️ Guardrails Configuration")
        max_issues = st.slider(
            "Max Issues to Show",
            min_value=1,
            max_value=50,
            value=15,
            step=1,
            help="Limits notification fatigue and caps review comments per file.",
        )
        strict_added = st.checkbox(
            "Strict Line Clamping (Added Lines Only)",
            value=True,
            help="Ensures comments only target lines actually changed in the diff.",
        )
        prompt_guard = st.checkbox(
            "Prompt Injection Sanitizer",
            value=True,
            help="Neutralizes adversarial instructions embedded in comments or PR bodies.",
        )

        st.markdown("---")
        st.caption("✨ **PR Sage Enterprise AI Reviewer v2.8.0**")

    return provider, user_api_key, selected_model_name, max_issues, strict_added, prompt_guard
