"""Multi-step Agent Orchestrator for PR Sage.

Interview Rationale (WHY):
- Deterministic Stage Pipeline vs Free-Form Loops:
  Free-form LLM agents often wander, loop indefinitely, or hallucinate tool parameters.
  A deterministic state-machine orchestrator guarantees exact execution order, reproducible runs,
  and enforceable error boundaries across every pull request.
- Sequential File Processing (8GB RAM Constraint):
  Processes diff chunks strictly sequentially with model unloads, preventing concurrent inference spikes
  that could trigger Out-Of-Memory (OOM) killer on modest machines.
- Multi-Level Guardrails & Telemetry:
  Enforces noise control (MAX_COMMENTS_PER_FILE=5, MAX_COMMENTS_PER_PR=10), comment severity sorting
  (critical > warning > info), confidence thresholding (>=0.80), unified patch generation, and operational telemetry.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
import re
import time
from typing import Any
from rich.console import Console
from rich.table import Table
from pydantic import BaseModel, Field
from src.config import Settings, get_settings
from src.db import DatabaseManager
from src.diff_parser import chunk_file_diff, parse_unified_diff
from src.github_client import GitHubClient
from src.guardrails import apply_guardrails, generate_unified_patch, sanitize_untrusted_input
from src.llm import LLMClient
from src.models import CodeChunk, FileDiff, ReviewComment, ReviewResult, ReviewTelemetry, StageResult
from src.stages import ErrorHandlingStage, ReviewStage, SecurityStage, UnderstandStage


logger = logging.getLogger("pr_sage.agent")
console = Console()


def _static_ast_audit(code: str, filename: str) -> list[ReviewComment]:
    """Offline Python AST and security pattern scanner for resilient zero-API-key fallback."""
    findings: list[ReviewComment] = []
    lines = code.splitlines()

    # 1. AST Syntax Check
    if filename.endswith((".py", ".pyw")):
        try:
            ast.parse(code)
        except SyntaxError as syn:
            findings.append(
                ReviewComment(
                    path=filename,
                    line=syn.lineno or 1,
                    severity="critical",
                    category="bug",
                    cwe_id="CWE-1188",
                    comment=f"SyntaxError: {syn.msg}. Code fails to compile.",
                    suggested_fix=None,
                    confidence=0.99,
                )
            )

    # 2. Pattern Scans
    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # SQL Injection
        if re.search(r'(?i)(SELECT|INSERT|UPDATE|DELETE).*(f["\']|%\s*\w+|\.format\(|\+\s*\w+)', line) or ("execute(" in line and 'f"' in line):
            findings.append(
                ReviewComment(
                    path=filename,
                    line=idx,
                    severity="critical",
                    category="security",
                    cwe_id="CWE-89",
                    comment="SQL Injection Risk: SQL query constructed via unescaped string interpolation.",
                    suggested_fix="cursor.execute('SELECT * FROM table WHERE col = ?', (param,))",
                    confidence=0.95,
                )
            )
        # Hardcoded Secret Key
        if re.search(r'(?i)(secret_key|api_key|password|jwt_secret|private_key|token|auth_token)\s*[:=]\s*["\'][a-zA-Z0-9_\-!@#$]{8,}["\']', line):
            findings.append(
                ReviewComment(
                    path=filename,
                    line=idx,
                    severity="critical",
                    category="security",
                    cwe_id="CWE-798",
                    comment="Hardcoded Secret: Sensitive token or credential is hardcoded in source code.",
                    suggested_fix='import os\nAPI_KEY = os.getenv("API_KEY", "")',
                    confidence=0.95,
                )
            )
        # Bare except
        if re.search(r'^\s*except\s*:\s*(pass)?', raw_line):
            findings.append(
                ReviewComment(
                    path=filename,
                    line=idx,
                    severity="warning",
                    category="reliability",
                    cwe_id="CWE-391",
                    comment="Silent Exception Swallowing: Bare `except:` drops all unhandled exceptions without logging.",
                    suggested_fix="except Exception as exc:\n    logger.error(f'Error: {exc}')\n    raise",
                    confidence=0.95,
                )
            )
        # Unchecked None dereference
        if re.search(r'\.get\([^)]+\)\.(upper|lower|split|strip|get)\(', line):
            findings.append(
                ReviewComment(
                    path=filename,
                    line=idx,
                    severity="warning",
                    category="reliability",
                    cwe_id="CWE-476",
                    comment="Unchecked NoneType Dereference: Chained call on dictionary `.get()` may raise AttributeError.",
                    suggested_fix='val = data.get("key")\nres = val.upper() if val is not None else None',
                    confidence=0.85,
                )
            )
        # Command Injection
        if re.search(r'subprocess\.(run|Popen|call|check_output)\(.*shell\s*=\s*True', line) or re.search(r'os\.system\(', line):
            findings.append(
                ReviewComment(
                    path=filename,
                    line=idx,
                    severity="critical",
                    category="security",
                    cwe_id="CWE-78",
                    comment="OS Command Injection: `shell=True` or `os.system` with dynamic arguments allows arbitrary command execution.",
                    suggested_fix='subprocess.run(["cmd", "arg1", "arg2"], shell=False)',
                    confidence=0.95,
                )
            )

    return findings


# =====================================================================
# Agent State Management
# =====================================================================


class AgentState(BaseModel):
    """Encapsulates the full execution state of the code review pipeline."""

    pr_number: int
    owner: str
    repo: str
    file_diffs: list[FileDiff] = Field(default_factory=list)
    per_file: dict[str, Any] = Field(default_factory=dict)
    all_findings: list[ReviewComment] = Field(default_factory=list)
    summary: str = ""

    def validate_state(self) -> None:
        """Detects state corruption or invalid configuration before execution."""
        if self.pr_number <= 0:
            raise ValueError(f"Invalid PR number: {self.pr_number}")
        if not self.owner or not self.repo:
            raise ValueError(f"Invalid repository target: {self.owner}/{self.repo}")
        if not isinstance(self.per_file, dict) or not isinstance(self.all_findings, list):
            raise ValueError("Agent state data structures corrupted.")


# =====================================================================
# PR Sage Orchestrator
# =====================================================================


class PRSageAgent:
    """Orchestrates multi-step code reviews across PR diffs."""

    def __init__(
        self,
        settings: Settings | None = None,
        github: GitHubClient | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or get_settings(DRY_RUN=True)
        self.github = github or GitHubClient(token=self.settings.GITHUB_TOKEN)
        self.llm = llm or LLMClient(
            model=self.settings.MODEL_NAME,
            api_key=self.settings.GROQ_API_KEY,
            base_url=self.settings.GROQ_BASE_URL,
            timeout=self.settings.REQUEST_TIMEOUT,
            max_retries=self.settings.MAX_RETRIES,
            keep_alive=self.settings.OLLAMA_KEEP_ALIVE,
        )
        self.db = DatabaseManager.get_instance(self.settings.DATABASE_PATH)

        # Initialize sequential pipeline stages
        self.stage_understand = UnderstandStage()
        self.stage_security = SecurityStage()
        self.stage_error = ErrorHandlingStage()
        self.stage_review = ReviewStage()

    def review_file(self, file_path: str | Path) -> ReviewResult:
        """Executes the 4-stage review on a local file without requiring GitHub API."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        code = path.read_text(encoding="utf-8")
        return self.review_code(code, filename=path.name)

    def review_code(
        self,
        code: str,
        filename: str = "snippet.py",
        min_confidence: float = 0.80,
    ) -> ReviewResult:
        """Executes the 4-stage review on a raw code string with full telemetry and patch generation."""
        start_time = time.time()
        clean_code, injection_detected = sanitize_untrusted_input(code)

        lines = clean_code.splitlines()
        line_numbers = list(range(1, len(lines) + 1))
        chunk = CodeChunk(
            chunk_id=0,
            file_path=filename,
            start_line=1,
            end_line=len(lines),
            lines=lines,
            line_numbers=line_numbers,
            added_line_numbers=line_numbers,
            is_partial=False,
        )

        console.print(f"[bold cyan]🔍 PR Sage reviewing file:[/bold cyan] `{filename}` ({len(lines)} lines)")
        if injection_detected:
            console.print("[bold red]⚠️ Adversarial prompt injection detected and neutralized.[/bold red]")

        used_model = self.settings.MODEL_NAME
        try:
            chunk_findings, chunk_note = self._process_chunk(chunk)
        except Exception as exc:
            logger.warning(f"LLM review failed: {exc}. Falling back to AST compiler engine.")
            chunk_findings = _static_ast_audit(clean_code, filename)
            chunk_note = "AST fallback"
            used_model = "ast-fallback"

        # Apply guardrails with confidence filtering
        final_comments = apply_guardrails(
            comments=chunk_findings,
            max_per_file=self.settings.MAX_COMMENTS_PER_FILE,
            max_per_pr=self.settings.MAX_COMMENTS_PER_PR,
            min_confidence=min_confidence,
            valid_lines_by_file={filename: chunk.added_line_numbers},
        )

        latency_ms = int((time.time() - start_time) * 1000)
        est_tokens = len(code.split()) * 2
        est_cost = round((est_tokens / 1000) * 0.0001, 6)

        telemetry = ReviewTelemetry(
            prompt_tokens=int(est_tokens * 0.7),
            completion_tokens=int(est_tokens * 0.3),
            total_tokens=est_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=est_cost,
            model_name=used_model,
        )

        final_summary = f"## 🤖 PR Sage Review\nReviewed `{filename}` ({len(lines)} LOC) in {latency_ms}ms.\n\n"
        final_summary += f"Detected **{len(final_comments)} actionable issues** (Confidence $\\ge {min_confidence:.0%}$)."
        if injection_detected:
            final_summary += "\n\n🛡️ *Adversarial prompt injection directives neutralized.*"

        patch = generate_unified_patch(final_comments, filename)

        review_result = ReviewResult(
            comments=final_comments,
            summary=final_summary,
            telemetry=telemetry,
            patch_content=patch,
        )

        # Output JSON and SQLite persistence
        output_path = Path("review_output.json")
        output_path.write_text(review_result.model_dump_json(indent=2), encoding="utf-8")
        self.db.save_review(review_result, repo="local/workspace", pr_number=0, filename=filename)

        self._print_summary_table(review_result)
        console.print(f"[bold green]✓ Review complete ({latency_ms}ms). Saved findings to `{output_path}` and database.[/bold green]")
        return review_result

    def run(
        self,
        pr_number: int,
        owner: str | None = None,
        repo: str | None = None,
        dry_run: bool | None = None,
    ) -> ReviewResult:
        """Executes the full 4-stage review pipeline for a pull request."""
        start_time = time.time()
        effective_dry_run = dry_run if dry_run is not None else self.settings.DRY_RUN

        target_owner, target_repo = self._resolve_repo(owner, repo)
        console.print(f"[bold cyan]🔍 PR Sage starting review on {target_owner}/{target_repo} #{pr_number}[/bold cyan]")
        if effective_dry_run:
            console.print("[yellow]⚡ Running in DRY-RUN mode (reviews will not be posted to GitHub).[/yellow]")

        # 1. Fetch PR Metadata & Unified Diff with Sanitization
        pr_meta = self.github.fetch_pr(target_owner, target_repo, pr_number)
        head_sha = pr_meta.get("head", {}).get("sha", "HEAD")
        raw_pr_title = pr_meta.get("title", f"PR #{pr_number}")
        pr_title, title_injected = sanitize_untrusted_input(raw_pr_title)
        raw_diff = self.github.fetch_pr_diff(target_owner, target_repo, pr_number)
        clean_diff, diff_injected = sanitize_untrusted_input(raw_diff)

        if title_injected or diff_injected:
            console.print("[bold red]⚠️ Adversarial prompt injection detected in PR and neutralized.[/bold red]")

        # 2. Deterministic Diff Parsing & Filtering
        file_diffs = parse_unified_diff(clean_diff, skip_patterns=self.settings.SKIP_PATHS)

        state = AgentState(
            pr_number=pr_number,
            owner=target_owner,
            repo=target_repo,
            file_diffs=file_diffs,
        )
        state.validate_state()

        console.print(f"[green]✓ Parsed {len(file_diffs)} reviewable file diffs (skipped ignored & binary assets)[/green]")

        # 3. Sequential File Processing (8GB RAM Rule)
        valid_lines_by_file: dict[str, list[int]] = {}

        for file_diff in file_diffs:
            if file_diff.is_binary or file_diff.is_rename or file_diff.change_type == "DELETED" or not file_diff.hunks:
                continue

            console.print(f"\n[bold blue]📂 Processing file:[/bold blue] `{file_diff.new_path}` (+{file_diff.total_additions}, -{file_diff.total_deletions})")
            chunks = chunk_file_diff(
                file_diff=file_diff,
                max_lines=self.settings.CHUNK_SIZE_LINES,
                overlap=self.settings.CHUNK_OVERLAP_LINES,
            )

            file_findings: list[ReviewComment] = []
            file_notes: list[str] = []
            added_lines_for_file: list[int] = []

            for chunk in chunks:
                added_lines_for_file.extend(chunk.added_line_numbers)
                chunk_findings, chunk_note = self._process_chunk(chunk)
                file_findings.extend(chunk_findings)
                if chunk_note:
                    file_notes.append(chunk_note)

            valid_lines_by_file[file_diff.new_path] = added_lines_for_file

            # Per-file deduplication and capping
            capped_file_findings = apply_guardrails(
                comments=file_findings,
                max_per_file=self.settings.MAX_COMMENTS_PER_FILE,
                max_per_pr=100,  # Global cap applied later
                min_confidence=0.80,
                valid_lines_by_file={file_diff.new_path: added_lines_for_file},
            )
            state.all_findings.extend(capped_file_findings)
            state.per_file[file_diff.new_path] = {
                "chunks_count": len(chunks),
                "findings": capped_file_findings,
                "notes": "\n".join(file_notes),
            }

        # 4. Global Guardrails & Priority Capping
        final_comments = apply_guardrails(
            comments=state.all_findings,
            max_per_file=self.settings.MAX_COMMENTS_PER_FILE,
            max_per_pr=self.settings.MAX_COMMENTS_PER_PR,
            min_confidence=0.80,
            valid_lines_by_file=valid_lines_by_file,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        total_tokens = sum(len(f.comment.split()) for f in final_comments) * 10 + 500
        telemetry = ReviewTelemetry(
            prompt_tokens=int(total_tokens * 0.7),
            completion_tokens=int(total_tokens * 0.3),
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=round((total_tokens / 1000) * 0.0001, 6),
            model_name=self.settings.MODEL_NAME,
        )

        final_summary = self._generate_summary(pr_title, pr_number, len(file_diffs), final_comments)
        if title_injected or diff_injected:
            final_summary += "\n\n🛡️ *Adversarial prompt injection directives neutralized.*"

        patch = generate_unified_patch(final_comments)

        review_result = ReviewResult(
            comments=final_comments,
            summary=final_summary,
            telemetry=telemetry,
            patch_content=patch,
        )

        # 5. Output / Posting & Database Record
        output_path = Path("review_output.json")
        output_path.write_text(review_result.model_dump_json(indent=2), encoding="utf-8")
        self.db.save_review(
            review_result=review_result,
            repo=f"{target_owner}/{target_repo}",
            pr_number=pr_number,
            commit_sha=head_sha,
        )

        if effective_dry_run:
            console.print(f"\n[bold green]✓ Dry run complete. Saved {len(final_comments)} review findings to `{output_path}` and database.[/bold green]")
        else:
            self._submit_github_review(
                owner=target_owner,
                repo=target_repo,
                pr_number=pr_number,
                commit_id=head_sha,
                summary=final_summary,
                comments=final_comments,
            )
            console.print(f"\n[bold green]✓ Successfully posted review with {len(final_comments)} comments on GitHub PR #{pr_number}[/bold green]")

        self._print_summary_table(review_result)
        return review_result

    def _process_chunk(self, chunk: Any) -> tuple[list[ReviewComment], str]:
        """Executes the 4 review stages sequentially on a single CodeChunk."""
        ctx: dict[str, Any] = {
            "file_path": chunk.file_path,
            "lines": chunk.lines,
            "line_numbers": getattr(chunk, "line_numbers", []),
            "added_line_numbers": chunk.added_line_numbers,
            "start_line": chunk.start_line,
        }

        # Stage 1: Understand
        res_understand: StageResult = self.stage_understand.run(ctx, self.llm)
        ctx["understand_notes"] = res_understand.notes

        # Stage 2: Security
        res_security: StageResult = self.stage_security.run(ctx, self.llm)
        ctx["security_notes"] = res_security.notes

        # Stage 3: Error Handling
        res_error: StageResult = self.stage_error.run(ctx, self.llm)

        # Stage 4: Consolidated Review
        ctx["prior_findings"] = res_security.findings + res_error.findings
        res_review: StageResult = self.stage_review.run(ctx, self.llm)

        return res_review.findings, res_review.notes

    def _generate_summary(
        self,
        pr_title: str,
        pr_number: int,
        files_count: int,
        comments: list[ReviewComment],
    ) -> str:
        """Generates structured Markdown review header."""
        critical_count = sum(1 for c in comments if c.severity == "critical")
        warning_count = sum(1 for c in comments if c.severity == "warning")
        info_count = sum(1 for c in comments if c.severity == "info")

        summary_lines = [
            f"## 🤖 PR Sage Automated Review",
            f"Reviewed **{files_count} files** for PR #{pr_number}: `{pr_title}`.\n",
            f"### 📊 Findings Summary",
            f"- 🔴 **Critical:** {critical_count}",
            f"- 🟡 **Warnings:** {warning_count}",
            f"- 🔵 **Info/Suggestions:** {info_count}\n",
        ]

        if not comments:
            summary_lines.append("✅ **No critical issues found.** Code changes look clean and well-structured.")
        else:
            summary_lines.append("Please review the line-level comments below before merging.")

        return "\n".join(summary_lines)

    def _submit_github_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_id: str,
        summary: str,
        comments: list[ReviewComment],
    ) -> None:
        """Translates ReviewComment objects to GitHub REST API payload."""
        formatted_comments: list[dict[str, Any]] = []
        for c in comments:
            badge = f"**[{c.severity.upper()}] [{c.category.upper()}]**"
            formatted_comments.append(
                {
                    "path": c.path,
                    "line": c.line,
                    "body": f"{badge} {c.comment}",
                }
            )

        self.github.post_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            commit_id=commit_id,
            body=summary,
            event="COMMENT",
            comments=formatted_comments,
        )

    def _resolve_repo(self, owner: str | None, repo: str | None) -> tuple[str, str]:
        """Resolves target owner and repo from parameters or settings."""
        if owner and repo:
            return owner, repo
        if self.settings.REPO and "/" in self.settings.REPO:
            parts = self.settings.REPO.split("/", 1)
            return parts[0], parts[1]
        return "unknown-owner", "unknown-repo"

    @staticmethod
    def _print_summary_table(review_result: ReviewResult) -> None:
        """Displays rich formatted terminal review table."""
        table = Table(title="PR Sage Review Findings", show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right", style="yellow")
        table.add_column("Severity", style="bold")
        table.add_column("Category", style="blue")
        table.add_column("Confidence", justify="right", style="green")
        table.add_column("Comment")

        for c in review_result.comments:
            sev_style = "red" if c.severity == "critical" else ("yellow" if c.severity == "warning" else "blue")
            table.add_row(
                c.path,
                str(c.line),
                f"[{sev_style}]{c.severity.upper()}[/{sev_style}]",
                c.category,
                f"{c.confidence:.0%}",
                c.comment,
            )

        if review_result.comments:
            console.print(table)

