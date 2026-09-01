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
    get_safe_secret_fix,
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
    assert detect_language("#include <iostream>", "payment_service.py")[0] == "cpp"
    assert detect_language("package main", "server.go")[0] == "go"
    assert detect_language("fn main() {}", "lib.rs")[0] == "rust"
    assert detect_language("public class App {}", "App.java")[0] == "java"
    assert detect_language("const x = 1;", "app.js")[0] == "javascript"
    assert detect_language("<?php echo 'hi';", "index.php")[0] == "php"


def test_language_specific_secret_fixes() -> None:
    """Verifies that get_safe_secret_fix produces valid code in target language."""
    cpp_fix = get_safe_secret_fix("cpp", "API_KEY")
    assert "std::getenv" in cpp_fix
    assert "process.env" not in cpp_fix

    py_fix = get_safe_secret_fix("python", "API_KEY")
    assert "os.getenv" in py_fix

    js_fix = get_safe_secret_fix("javascript", "API_KEY")
    assert "process.env" in js_fix


def test_cpp_vulnerability_analysis() -> None:
    """Verifies accurate C++ rule detections for SQLi, secrets, system(), and bare catch."""
    cpp_code = """
#include <iostream>
#include <sqlite3.h>
#include <cstdlib>

const char* API_KEY = "sk_live_1234567890abcdef";

void search_user(const char* username, sqlite3* db) {
    char query[512];
    sprintf(query, "SELECT * FROM users WHERE name = '%s'", username);
    sqlite3_exec(db, query, nullptr, nullptr, nullptr);
}

void run_command(const char* cmd) {
    system(cmd);
}

void process(int amount) {
    try {
        int x = 100 / amount;
    } catch (...) {
    }
}
"""
    meta, findings, traces = run_static_analysis(cpp_code, "code.cpp")
    assert meta["language"] == "C++"
    assert len(findings) >= 3

    # Check that the C++ secret fix uses std::getenv
    secret_findings = [f for f in findings if f["cwe"] == "CWE-798"]
    assert len(secret_findings) > 0
    assert "std::getenv" in secret_findings[0]["fix_code"]
    assert "process.env" not in secret_findings[0]["fix_code"]

    # Check SQL injection in C++
    sqli_findings = [f for f in findings if f["cwe"] == "CWE-89"]
    assert len(sqli_findings) > 0
    assert "sqlite3_prepare_v2" in sqli_findings[0]["fix_code"]


def test_cpp_loop_and_vla_detection() -> None:
    """Verifies that off-by-one loops, VLA arrays, and div-by-zero are accurately caught in C++."""
    user_cpp = """#include <iostream>
using namespace std;

int main() {
    int n;
    cin >> n;

    int arr[n];

    for (int i = 0; i <= n; i++) {
        cin >> arr[i];
    }

    int sum = 0;

    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }

    cout << "Average: " << sum / n << endl;

    return 0;
}"""
    meta, findings, traces = run_static_analysis(user_cpp, "main.cpp")
    assert meta["language"] == "C++"

    # Should detect off-by-one loop i <= n
    off_findings = [f for f in findings if f["cwe"] == "CWE-193"]
    assert len(off_findings) > 0
    assert "i < n" in off_findings[0]["fix_code"]

    # Should detect division by zero risk
    div_findings = [f for f in findings if f["cwe"] == "CWE-369"]
    assert len(div_findings) > 0


def test_calculate_health_score() -> None:
    """Verifies executive health score computation and grading."""
    crit_findings = [{"severity": "critical"}, {"severity": "warning"}]
    score, grade, color = calculate_health_score(crit_findings)
    assert score == 65
    assert grade == "C"

    clean_score, clean_grade, _ = calculate_health_score([])
    assert clean_score == 100
    assert clean_grade == "A+"


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
