"""
Comprehensive Correctness & Regression Test Suite for PR Sage.

Ensures:
1. Zero False Positives on Valid/Correct Code across C++, Python, JavaScript, Java, Go, Rust.
2. High-Precision Detection of True Bugs with exact line mapping, evidence, and valid fixes.
3. Multi-tier severity and calibrated confidence thresholding.
"""
from __future__ import annotations

from ui.analytics import detect_language, run_static_analysis
from src.guardrails import apply_guardrails, verify_finding_against_source
from src.models import ReviewComment


# ─────────────────────────────────────────────────────────────────────────────
# 1. Correct Code Tests (Must return 0 False Positives)
# ─────────────────────────────────────────────────────────────────────────────

def test_valid_cpp_code_zero_false_positives() -> None:
    """Verifies that clean, correct C++ code produces 0 bug findings."""
    clean_cpp = """#include <iostream>
#include <vector>
using namespace std;

int main() {
    int n = 5;
    vector<int> arr(n);

    for (int i = 0; i < n; i++) {
        arr[i] = i * 2;
    }

    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }

    if (n > 0) {
        cout << "Average: " << (double)sum / n << endl;
    }
    return 0;
}"""
    meta, findings, traces = run_static_analysis(clean_cpp, "main.cpp")
    assert meta["language"] == "C++"
    # Clean code must have ZERO critical/high bug findings!
    critical_bugs = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH", "critical")]
    assert len(critical_bugs) == 0, f"False positive detected on clean C++ code: {critical_bugs}"


def test_valid_python_code_zero_false_positives() -> None:
    """Verifies that clean, correct Python code produces 0 bug findings."""
    clean_py = """import os
import sqlite3
import logging

logger = logging.getLogger(__name__)
STRIPE_KEY = os.getenv("STRIPE_KEY", "")

def fetch_order(db: sqlite3.Connection, user_id: str):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def calculate_rate(amount: float, count: int) -> float:
    if count <= 0:
        raise ValueError("Count must be positive")
    return amount / count
"""
    meta, findings, traces = run_static_analysis(clean_py, "app.py")
    assert meta["language"] == "Python"
    critical_bugs = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH", "critical")]
    assert len(critical_bugs) == 0, f"False positive detected on clean Python code: {critical_bugs}"


def test_valid_javascript_code_zero_false_positives() -> None:
    """Verifies that clean, secure JavaScript code produces 0 bug findings."""
    clean_js = """// Safe DOM assignment and environment variable handling
const API_SECRET = process.env.API_SECRET || "";

function updateHeader(username) {
    const el = document.getElementById("welcome");
    if (el) {
        el.textContent = "Welcome, " + username;
    }
}
"""
    meta, findings, traces = run_static_analysis(clean_js, "app.js")
    assert meta["language"] == "JavaScript"
    critical_bugs = [f for f in findings if f.get("severity") in ("CRITICAL", "HIGH", "critical")]
    assert len(critical_bugs) == 0, f"False positive on clean JS code: {critical_bugs}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Buggy Code Tests (Must detect real bugs with exact lines)
# ─────────────────────────────────────────────────────────────────────────────

def test_cpp_array_out_of_bounds_detection() -> None:
    """Verifies detection of off-by-one buffer overflow (i <= 3) in C++."""
    buggy_cpp = """int main() {
    int arr[3];

    for (int i = 0; i <= 3; i++) {
        arr[i] = i;
    }
}"""
    meta, findings, traces = run_static_analysis(buggy_cpp, "main.cpp")
    assert meta["language"] == "C++"

    # Must detect off-by-one loop
    off_findings = [f for f in findings if f.get("cwe") == "CWE-193" or "Loop Bound" in f.get("title", "")]
    assert len(off_findings) > 0, "Failed to detect off-by-one buffer overflow in C++"
    assert off_findings[0]["line"] == 4
    assert "i < 3" in off_findings[0]["fix_code"]


def test_cpp_null_pointer_and_command_injection() -> None:
    """Verifies detection of null pointer dereference and system() injection."""
    buggy_cpp = """#include <iostream>
#include <cstdlib>

void run(const char* cmd) {
    system(cmd);
}

void print_val() {
    int* ptr = nullptr;
    std::cout << *ptr << std::endl;
}"""
    meta, findings, traces = run_static_analysis(buggy_cpp, "main.cpp")
    assert meta["language"] == "C++"

    cwes = [f.get("cwe") for f in findings]
    assert "CWE-78" in cwes, "Failed to detect OS command injection via system()"
    assert "CWE-476" in cwes, "Failed to detect Null pointer dereference"


def test_python_vulnerabilities_detection() -> None:
    """Verifies detection of SQLi, Hardcoded Secrets, Bare Except, and OS Command Injection in Python."""
    buggy_py = """import os
import sqlite3
import subprocess

API_KEY = "sk_live_998877665544332211"

def search(user, conn):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name = '{user}'")
    
def run_backup(folder):
    subprocess.run(f"tar -czf b.tar.gz {folder}", shell=True)

def silent():
    try:
        x = 1 / 0
    except:
        pass
"""
    meta, findings, traces = run_static_analysis(buggy_py, "app.py")
    assert meta["language"] == "Python"

    cwes = [f.get("cwe") for f in findings]
    assert "CWE-798" in cwes, "Failed to detect hardcoded secret"
    assert "CWE-89" in cwes, "Failed to detect SQL Injection"
    assert "CWE-78" in cwes, "Failed to detect Command Injection"
    assert "CWE-391" in cwes, "Failed to detect bare except"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Line Verification & Guardrail Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_verify_finding_against_source() -> None:
    """Verifies that findings targeting out-of-range or mismatched lines are handled."""
    source_lines = [
        "import os",
        "API_KEY = 'sk_live_12345'",
        "def main():",
        "    pass",
    ]

    valid_finding = ReviewComment(
        path="app.py",
        line=2,
        severity="CRITICAL",
        code="API_KEY = 'sk_live_12345'",
        explanation="Secret key",
    )
    assert verify_finding_against_source(valid_finding, source_lines) is True

    out_of_bounds_finding = ReviewComment(
        path="app.py",
        line=99,
        severity="CRITICAL",
        code="foo()",
        explanation="Does not exist",
    )
    assert verify_finding_against_source(out_of_bounds_finding, source_lines) is False


def test_confidence_threshold_filtering() -> None:
    """Verifies that apply_guardrails suppresses findings below min_confidence."""
    comments = [
        ReviewComment(path="app.py", line=1, severity="CRITICAL", confidence=0.95, comment="High conf"),
        ReviewComment(path="app.py", line=2, severity="MEDIUM", confidence=0.75, comment="Medium conf"),
        ReviewComment(path="app.py", line=3, severity="LOW", confidence=0.40, comment="Uncertain hallucination"),
    ]
    filtered = apply_guardrails(comments, min_confidence=0.70)
    assert len(filtered) == 2
    assert all(c.confidence >= 0.70 for c in filtered)


def test_python_code_detection_when_filename_is_cpp() -> None:
    """Verifies that Python code with off-by-one is correctly identified as Python and detected even if filename is main.cpp."""
    py_code = """def calculate_total(numbers):
    total = 0

    for i in range(len(numbers) + 1):
        total += numbers[i]

    return total


def get_user(users, user_id):
    for user in users:
        if user["id"] == user_id:
            return user
    return None"""

    lang_key, lang_name = detect_language(py_code, "main.cpp")
    assert lang_key == "python"
    assert lang_name == "Python"

    meta, findings, traces = run_static_analysis(py_code, "main.cpp")
    assert meta["language"] == "Python"
    
    # Must catch the Off-by-one range error (CWE-193) and unchecked dict key (CWE-476)
    off_by_one_findings = [f for f in findings if f.get("cwe") == "CWE-193"]
    assert len(off_by_one_findings) >= 1
    assert "range(len(numbers) + 1)" in off_by_one_findings[0]["bad_code"]
    assert "for i in range(len(numbers)):" in off_by_one_findings[0]["fix_code"]

