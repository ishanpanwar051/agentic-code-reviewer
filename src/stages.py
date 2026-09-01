"""Four-stage multi-step review pipeline for PR Sage.

Multi-Step Pipeline Architecture:
- Stage 1 (Understand): Deep comprehension of diff intent and risk hotspots.
- Stage 2 (Security): AppSec vulnerability audit with concrete proof and CWE mapping.
- Stage 3 (Error Handling): Reliability, exception safety, and boundary checks.
- Stage 4 (Review): Consolidation, deduplication, evidence verification, and summary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import re
from typing import Any
from pydantic import BaseModel, Field
from src.llm import LLMClient
from src.models import ReviewComment, StageResult


logger = logging.getLogger("pr_sage.stages")


def detect_language(file_path: str) -> str:
    """Detects markdown language identifier from file extension or path."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    ext_map = {
        "py": "python",
        "pyw": "python",
        "cpp": "cpp",
        "cxx": "cpp",
        "cc": "cpp",
        "c": "c",
        "h": "cpp",
        "hpp": "cpp",
        "js": "javascript",
        "jsx": "javascript",
        "mjs": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "java": "java",
        "go": "go",
        "rs": "rust",
        "cs": "csharp",
        "php": "php",
        "rb": "ruby",
        "sh": "bash",
        "bash": "bash",
        "kt": "kotlin",
        "kts": "kotlin",
        "swift": "swift",
        "sql": "sql",
        "html": "html",
        "css": "css",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
    }
    return ext_map.get(ext, "python")


# =====================================================================
# Stage Output Data Schemas
# =====================================================================


class UnderstandResult(BaseModel):
    """Structured understanding of file diff intent and risk hotspots."""

    summary: str = Field(description="High-level explanation of what this code change accomplishes.")
    intent: str = Field(description="The functional or architectural intention behind the modification.")
    risk_areas: list[str] = Field(
        default_factory=list,
        description="Key sensitive functions, APIs, or data flows that warrant deep security/error scrutiny.",
    )


class SecurityResult(BaseModel):
    """Structured findings for security vulnerabilities and dangerous patterns."""

    findings: list[ReviewComment] = Field(
        default_factory=list,
        description="List of security vulnerabilities detected in the newly added lines.",
    )
    notes: str = Field(
        default="",
        description="Security posture notes or threat model observations for downstream review.",
    )


class ErrorHandlingResult(BaseModel):
    """Structured findings for unhandled exceptions, silent failures, and resource management."""

    findings: list[ReviewComment] = Field(
        default_factory=list,
        description="List of error handling or reliability bugs detected in the newly added lines.",
    )
    notes: str = Field(
        default="",
        description="Reliability and exception-handling notes for downstream review.",
    )


class ConsolidatedReviewResult(BaseModel):
    """Consolidated review output containing finalized comments and high-level assessment."""

    comments: list[ReviewComment] = Field(
        default_factory=list,
        description="Final actionable code review comments.",
    )
    summary: str = Field(
        default="",
        description="Summary assessment of code quality, architecture, and merge readiness.",
    )


# =====================================================================
# Base Stage Interface
# =====================================================================


class BaseStage(ABC):
    """Abstract base class for deterministic pipeline review stages."""

    name: str = "base"
    output_model: type[BaseModel] = BaseModel
    system_prompt: str = (
        "You are an expert static code analysis AI agent. "
        "Review the provided code changes strictly and objectively against the actual source lines. "
        "1. Never invent code, files, or line numbers. Every issue must quote real source code. "
        "2. Provide concrete evidence for why an issue causes failure. "
        "3. If the code is correct, report zero findings."
    )

    def run(self, ctx: dict[str, Any], llm: LLMClient) -> StageResult:
        """Executes the stage with exception isolation and fallback logging."""
        prompt = self._build_prompt(ctx)
        try:
            parsed = llm.complete_structured(
                prompt=prompt,
                output_model=self.output_model,
                system=self.system_prompt,
            )
            return self._result(parsed, ctx)
        except Exception as exc:
            logger.warning(f"Stage '{self.name}' failed on {ctx.get('file_path')}: {exc}. Skipping gracefully.")
            return StageResult(
                stage=self.name,
                findings=[],
                notes=f"skipped: {exc}",
            )

    @abstractmethod
    def _build_prompt(self, ctx: dict[str, Any]) -> str:
        """Constructs stage-specific prompt with context."""
        raise NotImplementedError

    @abstractmethod
    def _result(self, parsed: Any, ctx: dict[str, Any]) -> StageResult:
        """Transforms validated model output into StageResult."""
        raise NotImplementedError

    @staticmethod
    def _format_code_block(ctx: dict[str, Any]) -> str:
        """Formats code lines with exact line numbers and '+' marker for newly added lines."""
        lines = ctx.get("lines", [])
        line_numbers = ctx.get("line_numbers", [])
        added_lines = ctx.get("added_line_numbers", [])
        start_line = ctx.get("start_line", 1)

        formatted_lines: list[str] = []
        for i, line in enumerate(lines):
            lineno = line_numbers[i] if i < len(line_numbers) else (start_line + i)
            marker = "+" if lineno in added_lines else " "
            formatted_lines.append(f"{lineno:4d} {marker} | {line}")
        return "\n".join(formatted_lines)

    @staticmethod
    def _filter_valid_lines(
        findings: list[ReviewComment],
        valid_line_numbers: list[int],
        file_path: str,
        ctx: dict[str, Any] | None = None,
    ) -> list[ReviewComment]:
        """Ensures comments target only valid newly added line numbers with snippet alignment."""
        valid_set = set(valid_line_numbers)
        filtered: list[ReviewComment] = []
        lines = ctx.get("lines", []) if ctx else []
        line_numbers = ctx.get("line_numbers", []) if ctx else []

        for finding in findings:
            finding.path = file_path
            if not valid_set or finding.line in valid_set:
                filtered.append(finding)
            else:
                # If finding has a code snippet, search for exact matching line in chunk
                matched_line = None
                if finding.code and lines and line_numbers:
                    clean_code = finding.code.strip()
                    for idx, raw_l in enumerate(lines):
                        if clean_code in raw_l.strip() and line_numbers[idx] in valid_set:
                            matched_line = line_numbers[idx]
                            break

                if matched_line:
                    finding.line = matched_line
                    filtered.append(finding)
                else:
                    # Only clamp if within distance of 1
                    closest = min(valid_set, key=lambda x: abs(x - finding.line))
                    if abs(closest - finding.line) <= 1:
                        finding.line = closest
                        filtered.append(finding)
                    else:
                        logger.debug(f"Dropped finding outside valid change lines: {finding.line}")

        return filtered


# =====================================================================
# Stage 1: Understand Stage
# =====================================================================


class UnderstandStage(BaseStage):
    """Stage 1: Analyzes diff purpose, architectural intent, and identifies risk candidates."""

    name = "understand"
    output_model = UnderstandResult
    system_prompt = (
        "You are PR Sage's Code Comprehension Agent. "
        "Analyze the provided code changes, summarize their technical purpose, and identify potential risk areas. "
        "Focus on understanding the execution flow, variables, and intent."
    )

    def _build_prompt(self, ctx: dict[str, Any]) -> str:
        file_path = ctx.get("file_path", "unknown")
        lang = detect_language(file_path)
        formatted_code = self._format_code_block(ctx)

        return (
            f"Analyze the following {lang} code changes in `{file_path}`.\n\n"
            f"Line numbers marked with '+' are modified lines.\n\n"
            f"```{lang}\n{formatted_code}\n```\n\n"
            f"Provide:\n"
            f"1. summary: A concise technical summary of what this code does.\n"
            f"2. intent: The apparent developer intent (refactor, feature, bugfix).\n"
            f"3. risk_areas: List of specific functions, logic branches, or operations that might carry security or bug risks."
        )

    def _result(self, parsed: UnderstandResult, ctx: dict[str, Any]) -> StageResult:
        notes = (
            f"Summary: {parsed.summary}\n"
            f"Intent: {parsed.intent}\n"
            f"Risk Areas: {', '.join(parsed.risk_areas) if parsed.risk_areas else 'None noted'}"
        )
        return StageResult(stage=self.name, findings=[], notes=notes)


# =====================================================================
# Stage 2: Security Stage
# =====================================================================


class SecurityStage(BaseStage):
    """Stage 2: Detects injection, hardcoded secrets, unsafe memory access, and auth flaws."""

    name = "security"
    output_model = SecurityResult
    system_prompt = (
        "You are PR Sage's Application Security (AppSec) Agent. "
        "Inspect the modified lines for genuine security vulnerabilities: "
        "SQL/Command injection, Buffer Overflows (CWE-120/193), Hardcoded Secrets (CWE-798), SSRF, Path Traversal, "
        "Insecure Deserialization, Unsafe eval/exec, or Missing Auth Validation. "
        "Rules:\n"
        "1. Report ONLY genuine vulnerabilities reachable in the code.\n"
        "2. Quote the exact code snippet.\n"
        "3. Provide concrete proof/evidence.\n"
        "4. Assign confidence score (0.0 to 1.0).\n"
        "5. If code is secure, return zero findings."
    )

    def _build_prompt(self, ctx: dict[str, Any]) -> str:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])
        understand_notes = ctx.get("understand_notes", "None")
        lang = detect_language(file_path)
        formatted_code = self._format_code_block(ctx)

        return (
            f"File: `{file_path}` ({lang})\n"
            f"Understand Context:\n{understand_notes}\n\n"
            f"Code segment (lines marked '+' are newly added lines available for review):\n"
            f"```{lang}\n{formatted_code}\n```\n\n"
            f"Eligible added line numbers: {added_lines}\n\n"
            f"Review ONLY the '+' lines for security vulnerabilities. "
            f"For each finding, specify exact line number, code snippet, severity ('CRITICAL' or 'HIGH'), "
            f"category='SECURITY', explanation, concrete evidence, and suggested_fix in {lang}."
        )

    def _result(self, parsed: SecurityResult, ctx: dict[str, Any]) -> StageResult:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])

        valid_findings: list[ReviewComment] = []
        for finding in parsed.findings:
            finding.category = "SECURITY"
            finding.path = file_path
            valid_findings.append(finding)

        filtered_findings = self._filter_valid_lines(valid_findings, added_lines, file_path, ctx)
        return StageResult(stage=self.name, findings=filtered_findings, notes=parsed.notes)


# =====================================================================
# Stage 3: Error Handling Stage
# =====================================================================


class ErrorHandlingStage(BaseStage):
    """Stage 3: Audits exception handling, unhandled edge cases, resource leaks, and crashes."""

    name = "error_handling"
    output_model = ErrorHandlingResult
    system_prompt = (
        "You are PR Sage's Reliability & Error Handling Agent. "
        "Audit modified lines for correctness and crash risks:\n"
        "1. Off-by-one errors and array out-of-bounds access.\n"
        "2. Null/NoneType pointer dereferences without check.\n"
        "3. Division by zero without boundary check.\n"
        "4. Silent exception swallows.\n"
        "5. Resource leaks (unclosed files/connections).\n"
        "Rules: Provide concrete evidence. If code is correct, return zero findings."
    )

    def _build_prompt(self, ctx: dict[str, Any]) -> str:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])
        understand_notes = ctx.get("understand_notes", "None")
        security_notes = ctx.get("security_notes", "None")
        lang = detect_language(file_path)
        formatted_code = self._format_code_block(ctx)

        return (
            f"File: `{file_path}` ({lang})\n"
            f"Understand Context:\n{understand_notes}\n"
            f"Security Notes:\n{security_notes}\n\n"
            f"Code segment (lines marked '+' are newly added lines):\n"
            f"```{lang}\n{formatted_code}\n```\n\n"
            f"Eligible added line numbers: {added_lines}\n\n"
            f"Audit the '+' lines for reliability bugs. "
            f"For each finding, specify line number, code snippet, severity ('CRITICAL', 'HIGH', or 'MEDIUM'), "
            f"category='RELIABILITY', explanation, evidence, and suggested_fix in {lang}."
        )

    def _result(self, parsed: ErrorHandlingResult, ctx: dict[str, Any]) -> StageResult:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])

        valid_findings: list[ReviewComment] = []
        for finding in parsed.findings:
            if finding.category not in ("BUG", "RELIABILITY", "PERFORMANCE"):
                finding.category = "RELIABILITY"
            finding.path = file_path
            valid_findings.append(finding)

        filtered_findings = self._filter_valid_lines(valid_findings, added_lines, file_path, ctx)
        return StageResult(stage=self.name, findings=filtered_findings, notes=parsed.notes)


# =====================================================================
# Stage 4: Review Stage
# =====================================================================


class ReviewStage(BaseStage):
    """Stage 4: Consolidates prior stage findings, performs quality/logic review, and deduplicates."""

    name = "review"
    output_model = ConsolidatedReviewResult
    system_prompt = (
        "You are PR Sage's Senior Staff Reviewer. "
        "Consolidate prior stage findings (Security, Error Handling), verify every finding against actual source lines, "
        "discard false positives or unverified claims, and produce final consolidated review findings. "
        "Style preferences must be marked as 'SUGGESTION'. Correct code must receive zero bug findings."
    )

    def _build_prompt(self, ctx: dict[str, Any]) -> str:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])
        prior_findings: list[ReviewComment] = ctx.get("prior_findings", [])
        understand_notes = ctx.get("understand_notes", "")
        lang = detect_language(file_path)
        formatted_code = self._format_code_block(ctx)

        prior_findings_text = "\n".join(
            f"- Line {f.line} [{f.severity}] [{f.category}]: {f.explanation or f.comment}"
            for f in prior_findings
        ) or "None detected in prior stages."

        return (
            f"File: `{file_path}` ({lang})\n"
            f"Understand Context:\n{understand_notes}\n\n"
            f"Prior Stage Findings:\n{prior_findings_text}\n\n"
            f"Code segment:\n"
            f"```{lang}\n{formatted_code}\n```\n\n"
            f"Eligible added line numbers: {added_lines}\n\n"
            f"Filter and consolidate the findings. Keep only verified, evidence-backed issues on '+' lines. "
            f"Provide a holistic markdown summary."
        )

    def _result(self, parsed: ConsolidatedReviewResult, ctx: dict[str, Any]) -> StageResult:
        file_path = ctx.get("file_path", "unknown")
        added_lines = ctx.get("added_line_numbers", [])
        prior_findings: list[ReviewComment] = ctx.get("prior_findings", [])

        candidate_findings = list(parsed.comments) if parsed.comments else list(prior_findings)

        seen_keys: set[tuple[str, int, str]] = set()
        deduped: list[ReviewComment] = []

        for item in candidate_findings:
            item.path = file_path
            clean_prefix = re.sub(r"[^\w\s]", "", (item.explanation or item.comment or item.title)[:40].lower()).strip()
            key = (item.path, item.line, clean_prefix)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(item)

        filtered = self._filter_valid_lines(deduped, added_lines, file_path, ctx)
        return StageResult(stage=self.name, findings=filtered, notes=parsed.summary)
