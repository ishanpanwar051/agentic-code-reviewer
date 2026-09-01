"""Domain data models for PR Sage — AI Software Verification & Reliability Platform.

Pydantic v2 Strong Typing Contracts:
- Proof of Concept (PoC) & Sandbox Verification Models.
- Cross-File Blast Radius & Behavior Diff Models.
- 6-Pillar Production Readiness Scorecard.
- Evidence-Backed Review Findings.
"""

from __future__ import annotations

import time
from typing import Any, Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ProofOfConcept(BaseModel):
    """Runnable test case / proof that demonstrates an issue or validates a fix."""

    code: str = Field(description="Runnable reproduction test or snippet.")
    runtime_output: str = Field(default="", description="Observed runtime error / output in sandbox.")
    verified: bool = Field(default=False, description="True if the failure was proven in runtime execution.")
    reproduced: bool = Field(default=False, description="True if reproduction script successfully triggered the bug.")


class BlastRadiusItem(BaseModel):
    """Represents a downstream component or API affected by a modified function."""

    target: str = Field(description="Affected downstream function, endpoint, or worker.")
    file_path: str = Field(description="File containing the affected component.")
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(default="MEDIUM")
    impact_reason: str = Field(description="Why this component is impacted by the change.")


class ProductionReadinessScore(BaseModel):
    """Comprehensive 6-pillar production readiness assessment."""

    correctness: int = Field(default=95, ge=0, le=100, description="Correctness & Logic Safety (0-100)")
    security: int = Field(default=90, ge=0, le=100, description="AppSec & OWASP Compliance (0-100)")
    testing: int = Field(default=80, ge=0, le=100, description="Edge-Case Test Coverage (0-100)")
    performance: int = Field(default=90, ge=0, le=100, description="Performance & Complexity (0-100)")
    observability: int = Field(default=85, ge=0, le=100, description="Logging & Tracing Readiness (0-100)")
    rollback_safety: int = Field(default=90, ge=0, le=100, description="Zero-Downtime Rollback Safety (0-100)")
    overall_score: float = Field(default=8.8, ge=0.0, le=10.0, description="Overall Composite Score (0.0 - 10.0)")
    recommendation: Literal["SAFE TO MERGE", "HUMAN REVIEW REQUIRED", "BLOCK MERGE"] = Field(
        default="SAFE TO MERGE"
    )


class BehaviorDiffItem(BaseModel):
    """Semantic before-and-after runtime behavior change."""

    scope: str = Field(description="Function or module scope.")
    before_behavior: str = Field(description="Execution behavior before this PR.")
    after_behavior: str = Field(description="Execution behavior after this PR.")
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(default="LOW")


class ReviewComment(BaseModel):
    """A structured, evidence-backed review finding targeting a specific line on a codebase or PR."""

    path: str = Field(default="module.py", description="Relative file path targeted by this comment.")
    line: int = Field(default=1, description="Target 1-indexed line number in the source file.")
    severity: str = Field(
        default="HIGH",
        description="Severity classification: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', or 'SUGGESTION'.",
    )
    category: str = Field(
        default="BUG",
        description="Functional classification: 'BUG', 'SECURITY', 'RELIABILITY', 'PERFORMANCE', 'STYLE', or 'CLARITY'.",
    )
    title: str = Field(
        default="Code Issue",
        description="Short, concise summary title of the finding.",
    )
    code: str | None = Field(
        default=None,
        description="Exact code snippet extracted from the source line.",
    )
    explanation: str = Field(
        default="",
        description="Clear explanation of why this code is problematic and what error/vulnerability it causes.",
    )
    evidence: str | None = Field(
        default=None,
        description="Concrete trace or proof demonstrating why the bug is reachable and triggers incorrect behavior.",
    )
    impact: str | None = Field(
        default=None,
        description="Downstream architectural or runtime failure impact.",
    )
    proof_of_concept: ProofOfConcept | None = Field(
        default=None,
        description="Runnable proof-of-concept script proving this vulnerability/bug.",
    )
    comment: str = Field(
        default="",
        description="Unified human-readable review comment.",
    )
    cwe_id: str | None = Field(
        default=None,
        description="Common Weakness Enumeration ID (e.g. CWE-89, CWE-798, CWE-193, CWE-369).",
    )
    suggested_fix: str | None = Field(
        default=None,
        description="Concrete, syntax-valid replacement code snippet resolving the issue.",
    )
    confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence probability (0.0 to 1.0) that this finding is a genuine true positive.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize severity
            sev = str(data.get("severity", "HIGH")).upper()
            if sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "SUGGESTION"):
                data["severity"] = sev
            elif sev == "WARNING":
                data["severity"] = "HIGH"
            elif sev == "INFO":
                data["severity"] = "LOW"
            else:
                data["severity"] = "MEDIUM"

            # Normalize explanation / comment
            expl = data.get("explanation") or data.get("comment") or data.get("description") or ""
            data["explanation"] = expl
            if not data.get("comment"):
                data["comment"] = expl

            # Normalize code snippet
            if not data.get("code") and data.get("bad_code"):
                data["code"] = data["bad_code"]

            # Normalize fix
            if not data.get("suggested_fix") and data.get("fix_code"):
                data["suggested_fix"] = data["fix_code"]

        return data


class ReviewTelemetry(BaseModel):
    """Operational telemetry tracking tokens, latency, and cost per review run."""

    prompt_tokens: int = Field(default=0, description="Total input tokens consumed.")
    completion_tokens: int = Field(default=0, description="Total generated completion tokens.")
    total_tokens: int = Field(default=0, description="Sum of prompt and completion tokens.")
    latency_ms: int = Field(default=0, description="Total execution time in milliseconds.")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated inference cost in USD.")
    model_name: str = Field(default="hybrid-ast", description="Active inference engine / model identifier.")
    stages_completed: list[str] = Field(
        default_factory=lambda: ["understand", "security", "error_handling", "guardrails", "sandbox_verify"],
        description="Sequential pipeline stages completed.",
    )


class ReviewResult(BaseModel):
    """The aggregated, deduplicated, and guardrail-filtered final review for a PR or file."""

    review_id: str = Field(default_factory=lambda: f"rev-{int(time.time()*1000)}", alias="reviewId")
    issues: list[ReviewComment] = Field(default_factory=list, alias="comments")
    comments: list[ReviewComment] = Field(default_factory=list)
    summary: str = Field(
        default="",
        description="High-level markdown summary describing PR changes, risks, and recommendations.",
    )
    score: float = Field(default=10.0, description="10-point code quality score.")
    health_score: int = Field(default=100, description="0-100 security health score.")
    grade: str = Field(default="A+", description="Letter grade (A+, A, B, C, F).")
    readiness: ProductionReadinessScore = Field(default_factory=ProductionReadinessScore)
    behavior_diff: list[BehaviorDiffItem] = Field(default_factory=list)
    blast_radius: list[BlastRadiusItem] = Field(default_factory=list)
    telemetry: ReviewTelemetry = Field(default_factory=ReviewTelemetry)
    patch_content: str = Field(
        default="",
        description="Automated git unified patch (git apply fix.patch) for 1-click refactoring.",
    )


# =====================================================================
# REST API Request & Response Schemas (FastAPI)
# =====================================================================


class CodeReviewRequest(BaseModel):
    """Request payload for reviewing raw code snippets."""

    code: str = Field(..., description="Raw source code or git unified diff to review.")
    filename: str = Field(default="module.py", description="Target filename for line number mapping.")
    model: str = Field(default="hybrid-ast", description="Model engine: 'hybrid-ast', 'gemini-2.0-flash', 'claude-3-5-sonnet', 'gpt-4o', 'groq'.")
    api_key: str | None = Field(default=None, description="Optional API key for proprietary LLM providers.")
    confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0, description="Minimum confidence score required to include findings.")


class PRReviewRequest(BaseModel):
    """Request payload for reviewing a GitHub Pull Request."""

    pr_number: int = Field(..., ge=1, description="GitHub Pull Request number.")
    owner: str = Field(..., description="GitHub repository owner (e.g. 'pallets').")
    repo: str = Field(..., description="GitHub repository name (e.g. 'flask').")
    dry_run: bool = Field(default=True, description="If True, skips posting comments to GitHub and returns JSON.")
    model: str = Field(default="hybrid-ast", description="Model engine to use.")
