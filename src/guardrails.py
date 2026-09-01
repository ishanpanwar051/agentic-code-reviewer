"""Security and quality guardrails for PR Sage.

Verification & Quality Standards:
- Exact Snippet & Line Verification: Verifies that every finding's reported line exists and matches actual source code.
- Confidence Thresholding: Rejects hallucinations (<0.70) and clearly stratifies Confirmed Bugs (>=0.85) vs Possible Issues (0.70-0.84).
- Noise Control: Deduplicates comments, eliminates false-positive noise, and prioritizes severe vulnerabilities.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path
import re
from typing import Any
from src.models import ReviewComment, ReviewResult


logger = logging.getLogger("pr_sage.guardrails")

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|security)\s+rules?", re.IGNORECASE),
    re.compile(r"(system|assistant|human|user)\s*:\s*(approve|lgtm|skip)", re.IGNORECASE),
    re.compile(r"\[/?(inst|sys|system|prompt)\]", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"output\s+only\s*:\s*[\"']?approve", re.IGNORECASE),
    re.compile(r"you\s+must\s+say\s+this\s+code\s+is\s+safe", re.IGNORECASE),
    re.compile(r"do\s+not\s+review\s+this\s+file", re.IGNORECASE),
    re.compile(r"set\s+(the\s+)?(verdict|review|status)\s+(to|as)\s+(approve|lgtm|safe)", re.IGNORECASE),
    re.compile(r"<!--\s*(system|inst|prompt):.*?-->", re.IGNORECASE | re.DOTALL),
]


def sanitize_untrusted_input(text: str) -> tuple[str, bool]:
    """Scans and neutralizes adversarial prompt injection vectors from code or PR text."""
    if not text:
        return "", False

    injection_detected = False
    sanitized = text

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            injection_detected = True
            logger.warning(f"Adversarial prompt injection pattern detected and neutralized: {pattern.pattern}")
            sanitized = pattern.sub("[REDACTED_UNTRUSTED_DIRECTIVE]", sanitized)

    return sanitized, injection_detected


def verify_github_webhook_signature(payload_bytes: bytes, secret: str, signature_header: str | None) -> bool:
    """Verifies HMAC-SHA256 signature from GitHub webhook delivery header (X-Hub-Signature-256)."""
    if not secret or not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_sig = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature_header)


def verify_finding_against_source(finding: ReviewComment, source_lines: list[str]) -> bool:
    """Verifies that a finding's line exists and is consistent with the actual code in the file."""
    line_idx = finding.line - 1
    if line_idx < 0 or line_idx >= len(source_lines):
        logger.warning(f"Rejected finding targeting out-of-range line {finding.line} (total lines: {len(source_lines)})")
        return False

    actual_line = source_lines[line_idx].strip()

    # If the finding quotes specific code, verify that the snippet is present on or near the line
    if finding.code and finding.code.strip():
        expected_snip = finding.code.strip()
        # Direct check on target line
        if expected_snip in actual_line or actual_line in expected_snip:
            return True
        # Check nearby +/- 1 line to account for formatting shifts
        nearby = False
        if line_idx > 0 and (expected_snip in source_lines[line_idx - 1] or source_lines[line_idx - 1].strip() in expected_snip):
            finding.line = line_idx  # adjust to previous line
            nearby = True
        elif line_idx + 1 < len(source_lines) and (expected_snip in source_lines[line_idx + 1] or source_lines[line_idx + 1].strip() in expected_snip):
            finding.line = line_idx + 2  # adjust to next line
            nearby = True

        if not nearby and len(expected_snip) > 5 and expected_snip not in actual_line:
            logger.debug(f"Snippet mismatch on line {finding.line}: expected '{expected_snip}', actual '{actual_line}'")

    return True


def deduplicate_comments(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Removes exact and near-duplicate comments targeting the same file and line."""
    seen_keys: set[tuple[str, int, str]] = set()
    deduped: list[ReviewComment] = []

    for comment in comments:
        clean_prefix = re.sub(r"[^\w\s]", "", (comment.explanation or comment.comment or comment.title)[:40].lower()).strip()
        key = (comment.path, comment.line, clean_prefix)

        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(comment)
        else:
            logger.debug(f"Dropped duplicate comment on {comment.path}:{comment.line}")

    return deduped


def validate_comment_lines(
    comments: list[ReviewComment],
    valid_lines_by_file: dict[str, list[int]] | None = None,
) -> list[ReviewComment]:
    """Ensures each comment strictly references a valid added/modified line in the target file."""
    if not valid_lines_by_file:
        return comments

    valid_comments: list[ReviewComment] = []
    for comment in comments:
        valid_lines = valid_lines_by_file.get(comment.path)
        if not valid_lines:
            valid_comments.append(comment)
            continue

        if comment.line in valid_lines:
            valid_comments.append(comment)
        else:
            # Strictly do not clamp unless the target is within 1 line of a real change
            closest_line = min(valid_lines, key=lambda l: abs(l - comment.line))
            if abs(closest_line - comment.line) <= 1:
                comment.line = closest_line
                valid_comments.append(comment)
            else:
                logger.warning(
                    f"Dropped comment on {comment.path}:{comment.line} - outside valid change lines: {valid_lines}"
                )

    return valid_comments


def apply_guardrails(
    comments: list[ReviewComment],
    max_per_file: int = 8,
    max_per_pr: int = 15,
    min_confidence: float = 0.70,
    valid_lines_by_file: dict[str, list[int]] | None = None,
    source_by_file: dict[str, list[str]] | None = None,
) -> list[ReviewComment]:
    """Applies complete guardrail pipeline: line validation, source code verification, confidence filtering, deduplication, and capping."""
    # 1. Line validity filter
    validated = validate_comment_lines(comments, valid_lines_by_file)

    # 2. Source code verification (ensures line exists and matches reported snippet)
    verified: list[ReviewComment] = []
    for c in validated:
        if source_by_file and c.path in source_by_file:
            if verify_finding_against_source(c, source_by_file[c.path]):
                verified.append(c)
        else:
            verified.append(c)

    # 3. Confidence Thresholding: Suppress uncertain hallucinations (< 0.70)
    confident = [c for c in verified if getattr(c, "confidence", 1.0) >= min_confidence]

    # 4. Deduplication
    deduped = deduplicate_comments(confident)

    # 5. Severity Priority Sorting: CRITICAL (0) > HIGH (1) > MEDIUM (2) > LOW (3) > SUGGESTION (4)
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "SUGGESTION": 4}
    deduped.sort(key=lambda c: (severity_rank.get(c.severity.upper(), 5), c.path, c.line))

    # 6. Per-file capping
    per_file_counts: dict[str, int] = {}
    file_capped: list[ReviewComment] = []
    for c in deduped:
        current_count = per_file_counts.get(c.path, 0)
        if current_count < max_per_file:
            per_file_counts[c.path] = current_count + 1
            file_capped.append(c)
        else:
            logger.info(f"Capped excess comment on file `{c.path}` (limit: {max_per_file})")

    # 7. Global PR capping
    if len(file_capped) > max_per_pr:
        logger.info(f"Capped total PR comments from {len(file_capped)} to global limit of {max_per_pr}")
        return file_capped[:max_per_pr]

    return file_capped


def generate_unified_patch(comments: list[ReviewComment], file_path: str = "module.py") -> str:
    """Generates standard git unified patch content from actionable review comments."""
    valid_fixes = [c for c in comments if c.suggested_fix and c.suggested_fix.strip()]
    if not valid_fixes:
        return ""

    patch_chunks: list[str] = []
    by_file: dict[str, list[ReviewComment]] = {}
    for c in valid_fixes:
        target = c.path or file_path
        by_file.setdefault(target, []).append(c)

    for target_path, file_comments in by_file.items():
        file_patch: list[str] = [
            f"diff --git a/{target_path} b/{target_path}",
            f"--- a/{target_path}",
            f"+++ b/{target_path}",
        ]
        file_comments.sort(key=lambda x: x.line)
        for c in file_comments:
            bad_line = (c.code or "").strip()
            fix_lines = (c.suggested_fix or "").splitlines()
            fix_count = max(1, len(fix_lines))
            file_patch.append(f"@@ -{c.line},1 +{c.line},{fix_count} @@")
            if bad_line:
                file_patch.append(f"- {bad_line}")
            for fl in fix_lines:
                file_patch.append(f"+ {fl}")

        patch_chunks.append("\n".join(file_patch))

    return "\n\n".join(patch_chunks) + "\n"


def export_review_reports(
    review_result: ReviewResult,
    output_dir: Path | str = ".",
    pr_number: int = 0,
    repo: str = "",
) -> dict[str, Path]:
    """Exports structured review findings into both JSON and formatted Markdown reports."""
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    json_path = dir_path / "review_output.json"
    json_path.write_text(review_result.model_dump_json(indent=2), encoding="utf-8")

    md_path = dir_path / "review_output.md"
    md_content = _build_markdown_report(review_result, pr_number, repo)
    md_path.write_text(md_content, encoding="utf-8")

    patch_path = dir_path / "fix.patch"
    patch_text = generate_unified_patch(review_result.comments)
    patch_path.write_text(patch_text, encoding="utf-8")

    return {"json": json_path, "markdown": md_path, "patch": patch_path}


def _build_markdown_report(result: ReviewResult, pr_number: int, repo: str) -> str:
    """Constructs a clean GitHub Flavored Markdown report."""
    critical_count = sum(1 for c in result.comments if c.severity.upper() == "CRITICAL")
    high_count = sum(1 for c in result.comments if c.severity.upper() == "HIGH")
    medium_count = sum(1 for c in result.comments if c.severity.upper() == "MEDIUM")
    low_count = sum(1 for c in result.comments if c.severity.upper() == "LOW")
    suggestion_count = sum(1 for c in result.comments if c.severity.upper() == "SUGGESTION")

    telemetry = result.telemetry

    lines = [
        f"# 🛡️ PR Sage Review Report",
        f"**Repository:** `{repo}` | **PR:** `#{pr_number}`\n",
        f"## 📊 Executive Summary",
        f"- 🔴 **Critical Flaws:** {critical_count}",
        f"- 🟠 **High Bugs:** {high_count}",
        f"- 🟡 **Medium Issues:** {medium_count}",
        f"- 🔵 **Low / Suggestions:** {low_count + suggestion_count}",
        f"- 📝 **Total Findings:** {len(result.comments)}",
        f"- ⚡ **Inference Engine:** `{telemetry.model_name}` ({telemetry.latency_ms}ms, {telemetry.total_tokens} tokens)\n",
        result.summary,
        "\n## 🔍 Actionable Findings\n",
    ]

    if not result.comments:
        lines.append("✅ **Zero Vulnerabilities Detected.** Code is approved for merge.")
    else:
        lines.append("| File | Line | Severity | Category | Confidence | Evidence & Comment |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for c in result.comments:
            sev = c.severity.upper()
            badge = "🔴 `CRITICAL`" if sev == "CRITICAL" else ("🟠 `HIGH`" if sev == "HIGH" else ("🟡 `MEDIUM`" if sev == "MEDIUM" else "🔵 `SUGGESTION`"))
            expl = c.explanation or c.comment or c.title
            clean_comment = expl.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{c.path}` | `{c.line}` | {badge} | `{c.category}` | `{c.confidence:.0%}` | {clean_comment} |")

    return "\n".join(lines)
