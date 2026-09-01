"""Domain data models for PR Sage using Pydantic v2.

Strongly-Typed Contracts:
- Accurate Line-Level Mapping: Tracks exact target line numbers, code snippets, and evidence.
- Multi-Tier Severity: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'SUGGESTION'.
- Evidence & Calibrated Confidence: Every reported issue must provide concrete evidence and confidence scores.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class DiffLine(BaseModel):
    """Represents a single line within a unified diff hunk."""

    model_config = ConfigDict(frozen=True)

    type: Literal["+", "-", " "] = Field(
        description="'+' for added line, '-' for removed line, ' ' for unchanged context line."
    )
    old_lineno: int | None = Field(
        default=None,
        description="Line number in the base/old file version (None for added lines).",
    )
    new_lineno: int | None = Field(
        default=None,
        description="Line number in the target/new file version (None for removed lines).",
    )
    content: str = Field(
        description="The line content without the leading '+', '-', or ' ' diff marker.",
    )


class DiffHunk(BaseModel):
    """Represents a contiguous block of diff changes starting with a unified diff header."""

    old_start: int = Field(description="Starting line in old file.")
    old_lines: int = Field(description="Number of lines in old file hunk.")
    new_start: int = Field(description="Starting line in new file.")
    new_lines: int = Field(description="Number of lines in new file hunk.")
    header: str = Field(description="Full hunk header line, e.g., '@@ -10,5 +10,7 @@ def foo():'.")
    lines: list[DiffLine] = Field(
        default_factory=list,
        description="Sequential list of diff lines within this hunk.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def added_line_numbers(self) -> list[int]:
        """Returns the list of exact new line numbers for added lines ('+') in this hunk."""
        return [
            line.new_lineno
            for line in self.lines
            if line.type == "+" and line.new_lineno is not None
        ]


class FileDiff(BaseModel):
    """Represents changes in a single file parsed from a unified git diff."""

    old_path: str = Field(description="Original file path prior to PR changes.")
    new_path: str = Field(description="Target file path after PR changes.")
    change_type: Literal["ADDED", "MODIFIED", "DELETED", "RENAMED"] = Field(
        description="Categorized type of file change."
    )
    is_binary: bool = Field(
        default=False,
        description="True if the file is a binary asset (images, binaries, etc.).",
    )
    is_rename: bool = Field(
        default=False,
        description="True if the file is a 100% similarity rename without functional changes.",
    )
    hunks: list[DiffHunk] = Field(
        default_factory=list,
        description="Parsed diff hunks containing modified lines.",
    )
    total_additions: int = Field(
        default=0,
        description="Total number of '+' lines added in this file.",
    )
    total_deletions: int = Field(
        default=0,
        description="Total number of '-' lines removed in this file.",
    )


class CodeChunk(BaseModel):
    """A bounded segment of code extracted for LLM analysis with strict line mapping."""

    chunk_id: int = Field(description="Sequential 0-indexed identifier for the chunk within a file.")
    file_path: str = Field(description="Relative file path.")
    start_line: int = Field(description="First new-file line number covered in this chunk.")
    end_line: int = Field(description="Last new-file line number covered in this chunk.")
    lines: list[str] = Field(
        default_factory=list,
        description="The code lines contained in this chunk for LLM review.",
    )
    line_numbers: list[int] = Field(
        default_factory=list,
        description="Exact 1-indexed line numbers corresponding to lines in this chunk.",
    )
    added_line_numbers: list[int] = Field(
        default_factory=list,
        description="Exact new line numbers that were newly added/modified inside this chunk.",
    )
    is_partial: bool = Field(
        default=False,
        description="True if the file was split into multiple chunks due to size limits.",
    )


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


class StageResult(BaseModel):
    """The structured output produced by an individual pipeline stage."""

    stage: str = Field(description="Name of the executing stage (e.g. understand, security, error_handling, review).")
    findings: list[ReviewComment] = Field(
        default_factory=list,
        description="Review comments detected during this specific stage.",
    )
    notes: str = Field(
        default="",
        description="Contextual observations or metadata passed to subsequent stages in agent state.",
    )


class ReviewTelemetry(BaseModel):
    """Operational telemetry tracking tokens, latency, and cost per review run."""

    prompt_tokens: int = Field(default=0, description="Total input tokens consumed.")
    completion_tokens: int = Field(default=0, description="Total generated completion tokens.")
    total_tokens: int = Field(default=0, description="Sum of prompt and completion tokens.")
    latency_ms: int = Field(default=0, description="Total execution time in milliseconds.")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated inference cost in USD.")
    model_name: str = Field(default="hybrid-ast", description="Active inference engine / model identifier.")
    stages_completed: list[str] = Field(
        default_factory=lambda: ["understand", "security", "error_handling", "guardrails"],
        description="Sequential pipeline stages completed.",
    )


class ReviewResult(BaseModel):
    """The aggregated, deduplicated, and guardrail-filtered final review for a PR."""

    comments: list[ReviewComment] = Field(
        default_factory=list,
        description="Final list of line-level review comments ready for posting.",
    )
    summary: str = Field(
        default="",
        description="High-level markdown summary describing PR changes, risks, and recommendations.",
    )
    telemetry: ReviewTelemetry = Field(
        default_factory=ReviewTelemetry,
        description="Latency, token, and cost telemetry for this review run.",
    )
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
