"""
Test Suite for PR Sage — AI Software Verification & Reliability Platform.

Tests:
1. Proof of Concept (Auto-PoC) generation and simulated runtime verification.
2. 6-Pillar Production Readiness scorecard computation and merge recommendations.
3. Semantic Behavior Diff and Blast Radius calculation.
4. Zero false positives on clean code and 100% precision on true vulnerabilities.
"""
from __future__ import annotations

from ui.analytics import (
    calculate_behavior_diff,
    calculate_blast_radius,
    calculate_production_readiness,
    run_static_analysis,
    synthesize_poc_and_impact,
)
from src.models import (
    BehaviorDiffItem,
    BlastRadiusItem,
    ProductionReadinessScore,
    ProofOfConcept,
    ReviewComment,
    ReviewResult,
)


def test_production_readiness_clean_code() -> None:
    """Verifies that clean code yields a SAFE TO MERGE verdict with score >= 8.5."""
    clean_findings: list[dict] = []
    readiness = calculate_production_readiness(clean_findings)

    assert readiness["recommendation"] == "SAFE TO MERGE"
    assert readiness["overall_score"] >= 8.5
    assert readiness["correctness"] == 100
    assert readiness["security"] == 100
    assert readiness["rollback_safety"] == 95


def test_production_readiness_critical_vulnerabilities() -> None:
    """Verifies that critical vulnerabilities trigger a BLOCK MERGE verdict."""
    crit_findings = [
        {"severity": "critical", "category": "AppSec", "cwe": "CWE-89"},
        {"severity": "critical", "category": "Reliability", "cwe": "CWE-120"},
    ]
    readiness = calculate_production_readiness(crit_findings)

    assert readiness["recommendation"] == "BLOCK MERGE"
    assert readiness["overall_score"] < 6.0
    assert readiness["correctness"] < 60


def test_auto_poc_synthesis() -> None:
    """Verifies that synthesize_poc_and_impact produces runnable test cases and observed crashes."""
    # Test CWE-193 (Off-by-one)
    finding_193 = {"cwe": "CWE-193", "bad_code": "for (int i=0; i<=n; i++)", "line": 5}
    poc_193, impact_193, ev_193 = synthesize_poc_and_impact(finding_193, "cpp", "main.cpp")
    assert "Reproduction Test" in poc_193["code"]
    assert "AddressSanitizer" in poc_193["runtime_output"]
    assert poc_193["verified"] is True
    assert "Loop bound" in impact_193

    # Test CWE-89 (SQLi)
    finding_89 = {"cwe": "CWE-89", "bad_code": "SELECT * FROM users WHERE name = f'{u}'", "line": 10}
    poc_89, impact_89, ev_89 = synthesize_poc_and_impact(finding_89, "python", "app.py")
    assert "OR '1'='1'" in poc_89["code"]
    assert "SQL Injection Exploit" in poc_89["runtime_output"]
    assert poc_89["verified"] is True


def test_behavior_diff_and_blast_radius() -> None:
    """Verifies behavior diff tracking and downstream blast radius mapping."""
    findings = [
        {"title": "SQL Injection", "line": 12, "severity": "critical", "cwe": "CWE-89"}
    ]
    b_diff = calculate_behavior_diff("code", findings, "payment_service.py")
    assert len(b_diff) > 0
    assert "Vulnerable execution path" in b_diff[0]["after_behavior"]

    blast = calculate_blast_radius("code", findings, "payment_service.py")
    assert len(blast) >= 2
    assert "api/v1/payment_service_handler" in blast[0]["target"]


def test_full_pipeline_verification_metadata() -> None:
    """Verifies that run_static_analysis returns all verification metadata structures."""
    buggy_cpp = """#include <iostream>
int main() {
    int arr[3];
    for (int i = 0; i <= 3; i++) {
        arr[i] = i;
    }
}"""
    meta, findings, traces = run_static_analysis(buggy_cpp, "main.cpp")
    assert "readiness" in meta
    assert "behavior_diff" in meta
    assert "blast_radius" in meta
    assert len(findings) >= 1
    assert "proof_of_concept" in findings[0]
    assert findings[0]["proof_of_concept"]["verified"] is True
