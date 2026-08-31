"""
Unit tests for modular PR Sage UI architecture (ui/ package).
"""
from __future__ import annotations

from ui.analytics import (
    PRESET_SNIPPETS,
    calculate_health_score,
    detect_language,
    generate_git_patch,
    generate_markdown_report,
    generate_refactored_code,
    run_static_analysis,
)
from ui.components.badges import render_cwe_badge, render_engine_badge, render_severity_badge
from ui.styles import get_application_styles
from ui.theme import COLORS, TYPOGRAPHY


def test_theme_and_styles_generation() -> None:
    """Verifies that design tokens are populated and CSS stylesheet compiles."""
    assert COLORS.bg_app == "#0B0D13"
    assert COLORS.primary == "#6366F1"
    assert TYPOGRAPHY.font_sans != ""

    styles_css = get_application_styles()
    assert "<style>" in styles_css
    assert "</style>" in styles_css
    assert COLORS.bg_app in styles_css
    assert ".enterprise-nav" in styles_css
    assert ".diff-card" in styles_css


def test_polyglot_language_detection() -> None:
    """Verifies accurate language detection across various extensions and signatures."""
    assert detect_language("print('hello')", "test.py")[0] == "python"
    assert detect_language("#include <iostream>", "main.cpp")[0] == "cpp"
    assert detect_language("package main", "server.go")[0] == "go"
    assert detect_language("fn main() {}", "lib.rs")[0] == "rust"
    assert detect_language("public class App {}", "App.java")[0] == "java"
    assert detect_language("const x = 1;", "app.js")[0] == "javascript"
    assert detect_language("<?php echo 'hi';", "index.php")[0] == "php"


def test_run_static_analysis_vulnerabilities() -> None:
    """Verifies static AST and AppSec pattern detection on presets."""
    python_snippet = PRESET_SNIPPETS["🐍 Python: Vulnerable App (SQLi + Secret + Bare Except)"]
    meta, findings, traces = run_static_analysis(python_snippet, "app.py")

    assert len(findings) >= 3
    titles = [f["title"] for f in findings]
    cwes = [f["cwe"] for f in findings]

    # Verify key vulnerabilities are tagged
    assert any("SQL Injection" in t for t in titles)
    assert any("Hardcoded" in t for t in titles)
    assert any("CWE-89" in c for c in cwes)
    assert any("CWE-798" in c for c in cwes)
    assert "Stage 1: Understand" in traces
    assert "Stage 2: Security Audit" in traces


def test_calculate_health_score() -> None:
    """Verifies executive health score computation and grading."""
    # Critical finding reduces score by 25
    crit_findings = [{"severity": "critical"}, {"severity": "warning"}]
    score, grade, color = calculate_health_score(crit_findings)
    assert score == 65
    assert grade == "C"

    # Zero findings gives 100 A+
    clean_score, clean_grade, _ = calculate_health_score([])
    assert clean_score == 100
    assert clean_grade == "A+"


def test_refactored_code_and_patch_generation() -> None:
    """Verifies in-browser auto-fix and git patch outputs."""
    code = "import os\nSECRET = 'hardcoded_12345'\n"
    findings = [
        {
            "line": 2,
            "bad_code": "SECRET = 'hardcoded_12345'",
            "fix_code": 'SECRET = os.getenv("SECRET", "")',
            "severity": "critical",
            "title": "Secret",
        }
    ]
    refactored = generate_refactored_code(code, findings)
    assert 'os.getenv("SECRET", "")' in refactored

    patch = generate_git_patch("auth.py", findings, "Auto-Hybrid")
    assert "diff --git a/auth.py b/auth.py" in patch
    assert "+ SECRET = os.getenv(\"SECRET\", \"\")" in patch


def test_badge_html_sanitization() -> None:
    """Verifies that badges escape untrusted HTML directives."""
    cwe_badge = render_cwe_badge("<script>alert(1)</script>")
    assert "<script>" not in cwe_badge
    assert "&lt;script&gt;" in cwe_badge

    sev_badge = render_severity_badge("critical")
    assert "CRITICAL" in sev_badge

    engine_badge = render_engine_badge("<b>Gemini</b>")
    assert "<b>" not in engine_badge
    assert "&lt;b&gt;" in engine_badge
