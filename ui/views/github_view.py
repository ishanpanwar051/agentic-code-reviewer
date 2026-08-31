"""
ui/views/github_view.py — Live GitHub Pull Request Fetcher View.
"""
from __future__ import annotations

from typing import Tuple
import httpx
import streamlit as st
from ui.analytics import PRESET_SNIPPETS


def render_github_view() -> Tuple[str, str]:
    """Renders the GitHub PR diff fetcher and returns (diff_content, active_filename)."""
    gh_c1, gh_c2 = st.columns([2, 1])
    with gh_c1:
        quick_pr = st.selectbox(
            "1-Click Open-Source Pull Requests:",
            [
                "pallets/flask — PR #5000",
                "psf/requests — PR #6000",
                "tiangolo/fastapi — PR #10000",
            ],
        )
    with gh_c2:
        gh_fetch = st.button("📥 Fetch Diff from GitHub", use_container_width=True)

    repo, pr_num = quick_pr.split(" — PR #")[0], quick_pr.split(" — PR #")[1]
    active_filename = f"{repo.replace('/', '_')}_PR_{pr_num}.diff"

    if gh_fetch:
        with st.spinner("Fetching unified diff from GitHub REST API..."):
            try:
                resp = httpx.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pr_num}",
                    headers={
                        "Accept": "application/vnd.github.v3.diff",
                        "User-Agent": "PR-Sage-Enterprise",
                    },
                    timeout=15.0,
                )
                if resp.is_success and resp.text:
                    diff_content = resp.text
                    st.session_state["github_fetched_diff"] = diff_content
                    st.session_state["github_fetched_filename"] = active_filename
                    st.success(f"✓ Successfully fetched PR #{pr_num} ({len(diff_content.splitlines())} lines)!")
                else:
                    st.error(f"Failed to fetch PR #{pr_num}: HTTP {resp.status_code}")
            except Exception as e:
                st.error(f"GitHub fetch failed: {e}")

    target_code = st.session_state.get(
        "github_fetched_diff",
        PRESET_SNIPPETS["🐍 Python: Vulnerable App (SQLi + Secret + Bare Except)"],
    )
    active_filename = st.session_state.get("github_fetched_filename", active_filename)

    return target_code, active_filename
