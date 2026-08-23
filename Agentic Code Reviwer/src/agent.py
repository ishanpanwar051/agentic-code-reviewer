"""Multi-step Agent Orchestrator for PR Sage.

Interview Rationale (WHY):
- Deterministic Stage Pipeline vs Free-Form Loops:
  Free-form LLM agents often wander, loop indefinitely, or hallucinate tool parameters.
  A deterministic state-machine orchestrator guarantees exact execution order, reproducible runs,
  and enforceable error boundaries across every pull request.
- Sequential File Processing (8GB RAM Constraint):
  Processes diff chunks strictly sequentially with model unloads, preventing concurrent inference spikes
  that could trigger Out-Of-Memory (OOM) killer on modest machines.
- Multi-Level Guardrails:
  Enforces noise control (MAX_COMMENTS_PER_FILE=5, MAX_COMMENTS_PER_PR=10), comment severity sorting
  (critical > warning > info), and dry-run safety modes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table
from pydantic import BaseModel, Field
from src.config import Settings, get_settings
from src.diff_parser import chunk_file_diff, parse_unified_diff
from src.github_client import GitHubClient
from src.llm import LLMClient
from src.models import FileDiff, ReviewComment, ReviewResult, StageResult
from src.stages import ErrorHandlingStage, ReviewStage, SecurityStage, UnderstandStage


logger = logging.getLogger("pr_sage.agent")
console = Console()


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
            base_url=self.settings.OLLAMA_BASE_URL,
            timeout=self.settings.REQUEST_TIMEOUT,
            max_retries=self.settings.MAX_RETRIES,
        )

        # Initialize sequential pipeline stages
        self.stage_understand = UnderstandStage()
        self.stage_security = SecurityStage()
        self.stage_error = ErrorHandlingStage()
        self.stage_review = ReviewStage()

    def run(
        self,
        pr_number: int,
        owner: str | None = None,
        repo: str | None = None,
        dry_run: bool | None = None,
    ) -> ReviewResult:
        """Executes the full 4-stage review pipeline for a pull request."""
        effective_dry_run = dry_run if dry_run is not None else self.settings.DRY_RUN

        # Resolve repository owner and name
        target_owner, target_repo = self._resolve_repo(owner, repo)

        console.print(f"[bold cyan]🔍 PR Sage starting review on {target_owner}/{target_repo} #{pr_number}[/bold cyan]")
        if effective_dry_run:
            console.print("[yellow]⚡ Running in DRY-RUN mode (reviews will not be posted to GitHub).[/yellow]")

        # 1. Fetch PR Metadata & Unified Diff
        pr_meta = self.github.fetch_pr(target_owner, target_repo, pr_number)
        head_sha = pr_meta.get("head", {}).get("sha", "HEAD")
        pr_title = pr_meta.get("title", f"PR #{pr_number}")
        raw_diff = self.github.fetch_pr_diff(target_owner, target_repo, pr_number)

        # 2. Deterministic Diff Parsing & Filtering
        file_diffs = parse_unified_diff(raw_diff, skip_patterns=self.settings.SKIP_PATHS)

        state = AgentState(
            pr_number=pr_number,
            owner=target_owner,
            repo=target_repo,
            file_diffs=file_diffs,
        )
        state.validate_state()

        console.print(f"[green]✓ Parsed {len(file_diffs)} reviewable file diffs (skipped ignored & binary assets)[/green]")

        # 3. Sequential File Processing (8GB RAM Rule: One file & chunk at a time)
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

            for chunk in chunks:
                chunk_findings, chunk_note = self._process_chunk(chunk)
                file_findings.extend(chunk_findings)
                if chunk_note:
                    file_notes.append(chunk_note)

            # Per-file deduplication and capping
            capped_file_findings = self._apply_file_guardrails(file_findings, file_diff.new_path)
            state.all_findings.extend(capped_file_findings)
            state.per_file[file_diff.new_path] = {
                "chunks_count": len(chunks),
                "findings": capped_file_findings,
                "notes": "\n".join(file_notes),
            }

        # 4. Global Guardrails & Priority Capping
        final_comments = self._apply_global_guardrails(state.all_findings)
        final_summary = self._generate_summary(pr_title, pr_number, len(file_diffs), final_comments)

        review_result = ReviewResult(comments=final_comments, summary=final_summary)

        # 5. Output / Posting
        if effective_dry_run:
            output_path = Path("review_output.json")
            output_path.write_text(review_result.model_dump_json(indent=2), encoding="utf-8")
            console.print(f"\n[bold green]✓ Dry run complete. Saved {len(final_comments)} review findings to `{output_path}`[/bold green]")
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

    def _apply_file_guardrails(
        self,
        findings: list[ReviewComment],
        file_path: str,
    ) -> list[ReviewComment]:
        """Deduplicates comments on a single file and enforces MAX_COMMENTS_PER_FILE cap."""
        # Deduplicate
        seen: set[tuple[int, str]] = set()
        deduped: list[ReviewComment] = []
        for f in findings:
            key = (f.line, f.comment[:30].strip().lower())
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        # Sort by severity priority: critical > warning > info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        deduped.sort(key=lambda x: (severity_order.get(x.severity, 3), x.line))

        # Cap per file
        max_file = self.settings.MAX_COMMENTS_PER_FILE
        if len(deduped) > max_file:
            logger.info(f"Capped comments on {file_path} from {len(deduped)} to {max_file}.")
            return deduped[:max_file]
        return deduped

    def _apply_global_guardrails(self, all_findings: list[ReviewComment]) -> list[ReviewComment]:
        """Sorts all findings across PR files and enforces MAX_COMMENTS_PER_PR cap."""
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        sorted_findings = sorted(all_findings, key=lambda x: (severity_order.get(x.severity, 3), x.path, x.line))

        max_pr = self.settings.MAX_COMMENTS_PER_PR
        if len(sorted_findings) > max_pr:
            logger.info(f"Capped PR comments from {len(sorted_findings)} to {max_pr}.")
            return sorted_findings[:max_pr]
        return sorted_findings

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
        table.add_column("Comment")

        for c in review_result.comments:
            sev_style = "red" if c.severity == "critical" else ("yellow" if c.severity == "warning" else "blue")
            table.add_row(
                c.path,
                str(c.line),
                f"[{sev_style}]{c.severity.upper()}[/{sev_style}]",
                c.category,
                c.comment,
            )

        if review_result.comments:
            console.print(table)
