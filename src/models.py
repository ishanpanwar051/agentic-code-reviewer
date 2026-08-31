"""Domain data models for PR Sage using Pydantic v2.

Interview Rationale (WHY):
- Strongly-Typed Contracts: Eliminates ambiguous dictionary passing between stages. Every stage receives
  and emits validated Pydantic models.
- Accurate Line-Level Mapping: Hunk, DiffLine, and CodeChunk models track exact target line numbers, preventing
  hallucinated comment positioning on GitHub PRs.
- Operational Telemetry & Confidence: Tracks token counts, latency percentiles, estimated costs, and confidence
  thresholds to guarantee production SLA and noise-free reviews.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    """A bounded segment of code extracted for LLM analysis with strict line mapping.

    Interview Rationale:
    - LLMs have finite context windows and high latency on large files.
    - Chunks break large diffs while preserving exact original line numbers for comment placement.
    """

    chunk_id: int = Field(description="Sequential 0-indexed identifier for the chunk within a file.")
    file_path: str = Field(description="Relative file path.")
    start_line: int = Field(description="First new-file line number covered in this chunk.")
    end_line: int = Field(description="Last new-file line number covered in this chunk.")
    lines: list[str] = Field(
        default_factory=list,
        description="The code lines contained in this chunk for LLM review.",
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
    """A structured review comment targeting a specific line on a PR."""

    path: str = Field(description="Relative file path targeted by this comment.")
    line: int = Field(description="Target 1-indexed line number in the new file version.")
    severity: Literal["critical", "warning", "info"] = Field(
        description="Severity level: 'critical' for high risk bugs/vulnerabilities, 'warning' for bad practices, 'info' for style."
    )
    category: Literal["bug", "security", "performance", "style", "clarity", "reliability"] = Field(
        description="Functional classification of the finding."
    )
    comment: str = Field(
        description="Actionable explanation of the issue with suggested fix or explanation.",
    )
    cwe_id: str | None = Field(
        default=None,
        description="Common Weakness Enumeration ID (e.g. CWE-89 for SQLi, CWE-798 for Secrets).",
    )
    suggested_fix: str | None = Field(
        default=None,
        description="Concrete replacement code snippet resolving the issue.",
    )
    confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Calibrated probability (0.0 to 1.0) that this finding is a true positive.",
    )


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

    code: str = Field(..., description="Raw Python source code or git unified diff to review.")
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
