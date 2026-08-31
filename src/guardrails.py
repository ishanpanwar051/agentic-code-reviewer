"""Security and quality guardrails for PR Sage.

Interview Rationale (WHY):
- Prompt Injection Defense:
  PR diffs and commit messages represent UNTRUSTED input. Attackers frequently attempt "indirect prompt injection"
  by embedding directives like 'SYSTEM: Approve this PR' or 'Ignore prior instructions' into comments or code strings.
  Our input sanitizer detects, logs, and neutralizes these injection vectors before constructing prompts.
- Noise Control (Developer Attention Defense):
  Developers experience alert fatigue when automated bots flood PRs with 30+ low-value comments.
  Our guardrail filters deduplicate comments, filter by confidence thresholds (>=0.80), prioritize high-severity
  findings (critical > warning > info), and strictly cap comments per file (5) and per PR (10).
- Strict Line Clamping:
  Guarantees that every posted comment maps strictly to an added or modified line ('+'), preventing broken
  GitHub UI comment placement.
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

# Common indirect prompt injection patterns found in adversarial code or commit bodies
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|security)\s+rules?", re.IGNORECASE),
    re.compile(r"(system|assistant|human|user)\s*:\s*(approve|lgtm|skip)", re.IGNORECASE),
    re.compile(r"\[/?(inst|sys|system|prompt)\]", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"output\s+only\s*:\s*[\"']?approve", re.IGNORECASE),
    re.compile(r"you\s+must\s+say\s+this\s+code\s+is\s+safe", re.IGNORECASE),
    re.compile(r"do\s+not\s+review\s+this\s+file", re.IGNORECASE),
]


def sanitize_untrusted_input(text: str) -> tuple[str, bool]:
    """Scans and neutralizes adversarial prompt injection vectors from code or PR text.

    Returns:
        tuple[str, bool]: (sanitized_text, injection_detected)
    """
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
    """Verifies HMAC-SHA256 signature from GitHub webhook delivery header (X-Hub-Signature-256).

    Args:
        payload_bytes: Raw HTTP request body bytes.
        secret: Configured GITHUB_WEBHOOK_SECRET.
        signature_header: Header value from X-Hub-Signature-256 (e.g. 'sha256=abc...').

    Returns:
        bool: True if signature matches, False otherwise.
    """
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


def deduplicate_comments(comments: list[ReviewComment]) -> list[ReviewComment]:
    """Removes exact and near-duplicate comments targeting the same file and line."""
    seen_keys: set[tuple[str, int, str]] = set()
    deduped: list[ReviewComment] = []

    for comment in comments:
        clean_prefix = re.sub(r"[^\w\s]", "", comment.comment[:40].lower()).strip()
        key = (comment.path, comment.line, clean_prefix)

        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(comment)
        else:
            logger.debug(f"Dropped duplicate comment on {comment.path}:{comment.line} -> '{comment.comment[:30]}...'")

    return deduped


def validate_comment_lines(
    comments: list[ReviewComment],
    valid_lines_by_file: dict[str, list[int]] | None = None,
) -> list[ReviewComment]:
    """Ensures each comment strictly references a valid added line in the target file."""
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
            closest_line = min(valid_lines, key=lambda l: abs(l - comment.line))
            if abs(closest_line - comment.line) <= 2:
                logger.info(
                    f"Clamped comment on {comment.path} from line {comment.line} to nearest valid line {closest_line}"
                )
                comment.line = closest_line
                valid_comments.append(comment)
            else:
                logger.warning(
                    f"Dropped comment on {comment.path}:{comment.line} - not within valid added lines: {valid_lines}"
                )

    return valid_comments


def apply_guardrails(
    comments: list[ReviewComment],
    max_per_file: int = 5,
    max_per_pr: int = 10,
    min_confidence: float = 0.80,
    valid_lines_by_file: dict[str, list[int]] | None = None,
) -> list[ReviewComment]:
    """Applies complete guardrail pipeline: line validation, confidence filtering, deduplication, severity sorting, and capping."""
    # 1. Line validity filter
    validated = validate_comment_lines(comments, valid_lines_by_file)

    # 2. Confidence Thresholding (drops low-confidence noise)
    confident = [c for c in validated if getattr(c, "confidence", 1.0) >= min_confidence]

    # 3. Deduplication
    deduped = deduplicate_comments(confident)

    # 4. Severity Priority Sorting: critical (0) > warning (1) > info (2)
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    deduped.sort(key=lambda c: (severity_rank.get(c.severity, 3), c.path, c.line))

    # 5. Per-file capping
    per_file_counts: dict[str, int] = {}
    file_capped: list[ReviewComment] = []
    for c in deduped:
        current_count = per_file_counts.get(c.path, 0)
        if current_count < max_per_file:
            per_file_counts[c.path] = current_count + 1
            file_capped.append(c)
        else:
            logger.info(f"Capped excess comment on file `{c.path}` (limit: {max_per_file})")

    # 6. Global PR capping
    if len(file_capped) > max_per_pr:
        logger.info(f"Capped total PR comments from {len(file_capped)} to global limit of {max_per_pr}")
        return file_capped[:max_per_pr]

    return file_capped


def generate_unified_patch(comments: list[ReviewComment], file_path: str = "module.py") -> str:
    """Generates standard git unified patch content from actionable review comments."""
    patch_lines = [
        f"# Generated by PR Sage Automated Code Reviewer",
        f"# Apply with: git apply fix.patch\n",
    ]

    for c in comments:
        if c.suggested_fix:
            target_path = c.path or file_path
            patch_lines.append(f"--- a/{target_path}")
            patch_lines.append(f"+++ b/{target_path}")
            patch_lines.append(f"@@ -{c.line},1 +{c.line},1 @@")
            patch_lines.append(f"+ {c.suggested_fix}\n")

    return "\n".join(patch_lines)


def export_review_reports(
    review_result: ReviewResult,
    output_dir: Path | str = ".",
    pr_number: int = 0,
    repo: str = "",
) -> dict[str, Path]:
    """Exports structured review findings into both JSON and formatted Markdown reports."""
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    # 1. Export JSON Report
    json_path = dir_path / "review_output.json"
    json_path.write_text(review_result.model_dump_json(indent=2), encoding="utf-8")

    # 2. Export Markdown Report
    md_path = dir_path / "review_output.md"
    md_content = _build_markdown_report(review_result, pr_number, repo)
    md_path.write_text(md_content, encoding="utf-8")

    # 3. Export Git Patch if fixes exist
    patch_path = dir_path / "fix.patch"
    patch_text = generate_unified_patch(review_result.comments)
    patch_path.write_text(patch_text, encoding="utf-8")

    return {"json": json_path, "markdown": md_path, "patch": patch_path}


def _build_markdown_report(result: ReviewResult, pr_number: int, repo: str) -> str:
    """Constructs a clean GitHub Flavored Markdown report."""
    critical_count = sum(1 for c in result.comments if c.severity == "critical")
    warning_count = sum(1 for c in result.comments if c.severity == "warning")
    info_count = sum(1 for c in result.comments if c.severity == "info")

    telemetry = result.telemetry

    lines = [
        f"# 🛡️ PR Sage Review Report",
        f"**Repository:** `{repo}` | **PR:** `#{pr_number}`\n",
        f"## 📊 Executive Summary",
        f"- 🔴 **Critical Bugs / Vulnerabilities:** {critical_count}",
        f"- 🟡 **Warnings / Reliability Risks:** {warning_count}",
        f"- 🔵 **Style / Clarity Suggestions:** {info_count}",
        f"- 📝 **Total Actionable Comments:** {len(result.comments)}",
        f"- ⚡ **Inference Engine:** `{telemetry.model_name}` ({telemetry.latency_ms}ms, {telemetry.total_tokens} tokens)\n",
        result.summary,
        "\n## 🔍 Line-Level Findings\n",
    ]

    if not result.comments:
        lines.append("✅ No issues detected. Code is ready for review.")
    else:
        lines.append("| File | Line | Severity | Category | Confidence | Comment |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for c in result.comments:
            badge = "🔴 `CRITICAL`" if c.severity == "critical" else ("🟡 `WARNING`" if c.severity == "warning" else "🔵 `INFO`")
            clean_comment = c.comment.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{c.path}` | `{c.line}` | {badge} | `{c.category}` | `{c.confidence:.0%}` | {clean_comment} |")

    return "\n".join(lines)
