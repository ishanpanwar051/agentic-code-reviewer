"""Unified diff parser and code-aware chunking engine for PR Sage.

Interview Rationale (WHY):
- Deterministic Line Offsets: Never rely on LLMs to count lines from raw diffs.
  GitHub review comments require exact 1-indexed target line numbers from the new file version.
- Added-Lines-Only Review: High signal-to-noise ratio. By identifying only '+' lines,
  we prevent the model from complaining about preexisting legacy code outside the PR scope.
- Code-Aware Chunking: Splits massive PR diffs (>150 lines) into overlapping windows (20 lines overlap)
  so local context (function headers, imports) is preserved without truncating changes or corrupting line numbers.
"""

from __future__ import annotations

import re
from src.config import should_skip_path
from src.models import CodeChunk, DiffHunk, DiffLine, FileDiff


HUNK_HEADER_REGEX = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$"
)
DIFF_GIT_REGEX = re.compile(r"^diff --git\s+a/(.*?)\s+b/(.*?)$")


def _clean_path(path_str: str) -> str:
    """Strips git diff prefixes (a/, b/) and quotes."""
    path = path_str.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def parse_unified_diff(
    raw_diff: str,
    skip_patterns: list[str] | None = None,
) -> list[FileDiff]:
    """Parses a unified git diff string into a structured list of FileDiff objects.

    Handles:
    - Standard git diffs (`diff --git a/... b/...`)
    - Added, Modified, Deleted, and Renamed file modes
    - Binary file detection
    - 100% similarity rename detection
    - Hunk headers with varied syntax (`@@ -1 +1 @@`, `@@ -0,0 +1,50 @@`, `@@ -10,5 +10,7 @@`)
    - `\\ No newline at end of file` markers
    - Skip path filtering via glob patterns
    """
    if not raw_diff or not raw_diff.strip():
        return []

    lines = raw_diff.splitlines()
    file_diffs: list[FileDiff] = []

    current_file_lines: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            if current_file_lines:
                parsed_file = _parse_single_file_diff(current_file_lines, skip_patterns)
                if parsed_file is not None:
                    file_diffs.append(parsed_file)
                current_file_lines = []
        current_file_lines.append(line)

    if current_file_lines:
        parsed_file = _parse_single_file_diff(current_file_lines, skip_patterns)
        if parsed_file is not None:
            file_diffs.append(parsed_file)

    return file_diffs


def _parse_single_file_diff(
    lines: list[str],
    skip_patterns: list[str] | None,
) -> FileDiff | None:
    """Parses lines belonging to a single file diff block."""
    if not lines:
        return None

    old_path = ""
    new_path = ""
    change_type: str = "MODIFIED"
    is_binary = False
    is_rename = False
    similarity_index = 0

    first_line = lines[0]
    git_match = DIFF_GIT_REGEX.match(first_line)
    if git_match:
        old_path = git_match.group(1)
        new_path = git_match.group(2)

    hunk_start_indices: list[int] = []

    for idx, line in enumerate(lines):
        if line.startswith("new file mode"):
            change_type = "ADDED"
        elif line.startswith("deleted file mode"):
            change_type = "DELETED"
        elif line.startswith("similarity index"):
            # e.g., 'similarity index 100%'
            parts = line.split()
            if len(parts) >= 3 and parts[2].rstrip("%").isdigit():
                similarity_index = int(parts[2].rstrip("%"))
        elif line.startswith("rename from"):
            old_path = line[len("rename from ") :].strip()
            change_type = "RENAMED"
        elif line.startswith("rename to"):
            new_path = line[len("rename to ") :].strip()
            change_type = "RENAMED"
        elif line.startswith("Binary files ") and "differ" in line:
            is_binary = True
        elif line.startswith("--- "):
            raw_old = line[4:].strip()
            if raw_old != "/dev/null":
                old_path = _clean_path(raw_old)
            else:
                change_type = "ADDED"
        elif line.startswith("+++ "):
            raw_new = line[4:].strip()
            if raw_new != "/dev/null":
                new_path = _clean_path(raw_new)
            else:
                change_type = "DELETED"
        elif line.startswith("@@ "):
            hunk_start_indices.append(idx)

    if similarity_index == 100:
        is_rename = True

    # Fallback paths if not discovered from headers
    if not old_path and not new_path and git_match:
        old_path = git_match.group(1)
        new_path = git_match.group(2)
    elif not old_path:
        old_path = new_path
    elif not new_path:
        new_path = old_path

    # Apply skip filter based on target file path
    target_check_path = new_path if new_path and new_path != "/dev/null" else old_path
    if skip_patterns and should_skip_path(target_check_path, skip_patterns):
        return None

    # Parse hunks
    hunks: list[DiffHunk] = []
    total_additions = 0
    total_deletions = 0

    if not is_binary and not is_rename and hunk_start_indices:
        for i, start_idx in enumerate(hunk_start_indices):
            end_idx = (
                hunk_start_indices[i + 1]
                if i + 1 < len(hunk_start_indices)
                else len(lines)
            )
            hunk_lines_raw = lines[start_idx:end_idx]
            hunk, adds, dels = _parse_hunk(hunk_lines_raw)
            if hunk is not None:
                hunks.append(hunk)
                total_additions += adds
                total_deletions += dels

    return FileDiff(
        old_path=old_path,
        new_path=new_path,
        change_type=change_type,  # type: ignore[arg-type]
        is_binary=is_binary,
        is_rename=is_rename,
        hunks=hunks,
        total_additions=total_additions,
        total_deletions=total_deletions,
    )


def _parse_hunk(hunk_lines: list[str]) -> tuple[DiffHunk | None, int, int]:
    """Parses a single hunk block starting with @@ header."""
    if not hunk_lines:
        return None, 0, 0

    header_line = hunk_lines[0]
    match = HUNK_HEADER_REGEX.match(header_line)
    if not match:
        return None, 0, 0

    old_start_str, old_lines_str, new_start_str, new_lines_str, _ = match.groups()

    old_start = int(old_start_str)
    old_lines = int(old_lines_str) if old_lines_str is not None else (0 if old_start == 0 else 1)

    new_start = int(new_start_str)
    new_lines = int(new_lines_str) if new_lines_str is not None else (0 if new_start == 0 else 1)

    current_old_lineno = old_start
    current_new_lineno = new_start

    parsed_lines: list[DiffLine] = []
    additions = 0
    deletions = 0

    for line in hunk_lines[1:]:
        if not line:
            # Empty context line in unified diff
            parsed_lines.append(
                DiffLine(
                    type=" ",
                    old_lineno=current_old_lineno,
                    new_lineno=current_new_lineno,
                    content="",
                )
            )
            current_old_lineno += 1
            current_new_lineno += 1
            continue

        prefix = line[0]
        content = line[1:]

        if prefix == "+":
            parsed_lines.append(
                DiffLine(
                    type="+",
                    old_lineno=None,
                    new_lineno=current_new_lineno,
                    content=content,
                )
            )
            current_new_lineno += 1
            additions += 1
        elif prefix == "-":
            parsed_lines.append(
                DiffLine(
                    type="-",
                    old_lineno=current_old_lineno,
                    new_lineno=None,
                    content=content,
                )
            )
            current_old_lineno += 1
            deletions += 1
        elif prefix == " ":
            parsed_lines.append(
                DiffLine(
                    type=" ",
                    old_lineno=current_old_lineno,
                    new_lineno=current_new_lineno,
                    content=content,
                )
            )
            current_old_lineno += 1
            current_new_lineno += 1
        elif line.startswith(r"\ No newline at end of file"):
            # Marker line: does not increment line numbers
            continue

    hunk = DiffHunk(
        old_start=old_start,
        old_lines=old_lines,
        new_start=new_start,
        new_lines=new_lines,
        header=header_line,
        lines=parsed_lines,
    )
    return hunk, additions, deletions


def chunk_file_diff(
    file_diff: FileDiff,
    max_lines: int = 150,
    overlap: int = 20,
) -> list[CodeChunk]:
    """Divides a file's diff hunks into reviewable CodeChunk segments.

    Interview Rationale (WHY):
    - When a PR touches a 500-line file, sending everything in one prompt exhausts
      small model context windows (llama3.2:3b) and causes degradation in instruction following.
    - We partition hunks into code chunks of size `max_lines` with `overlap` lines of context.
    - Crucially: `added_line_numbers` inside each chunk strictly match real new-file line numbers,
      so any LLM review finding maps directly to a valid line for GitHub comment placement.
    """
    if file_diff.is_binary or file_diff.is_rename or file_diff.change_type == "DELETED":
        return []

    if not file_diff.hunks:
        return []

    # Extract all target lines (new version lines: '+' and ' ') with line metadata
    # Each entry: (new_lineno, content, is_added)
    target_lines: list[tuple[int, str, bool]] = []

    for hunk in file_diff.hunks:
        for line in hunk.lines:
            if line.type in ("+", " ") and line.new_lineno is not None:
                target_lines.append((line.new_lineno, line.content, line.type == "+"))

    if not target_lines:
        return []

    total_target_lines = len(target_lines)

    # If small enough, return as single self-contained chunk
    if total_target_lines <= max_lines:
        start_line = target_lines[0][0]
        end_line = target_lines[-1][0]
        chunk_lines = [item[1] for item in target_lines]
        added_lines = [item[0] for item in target_lines if item[2]]

        return [
            CodeChunk(
                chunk_id=0,
                file_path=file_diff.new_path,
                start_line=start_line,
                end_line=end_line,
                lines=chunk_lines,
                added_line_numbers=added_lines,
                is_partial=False,
            )
        ]

    # Partition large files into overlapping chunks
    step = max(1, max_lines - overlap)
    chunks: list[CodeChunk] = []
    chunk_idx = 0

    for i in range(0, total_target_lines, step):
        window = target_lines[i : i + max_lines]
        if not window:
            continue

        start_line = window[0][0]
        end_line = window[-1][0]
        chunk_lines = [item[1] for item in window]
        added_lines = [item[0] for item in window if item[2]]

        chunks.append(
            CodeChunk(
                chunk_id=chunk_idx,
                file_path=file_diff.new_path,
                start_line=start_line,
                end_line=end_line,
                lines=chunk_lines,
                added_line_numbers=added_lines,
                is_partial=True,
            )
        )
        chunk_idx += 1

        # If window reached the end of the file, break early
        if i + max_lines >= total_target_lines:
            break

    return chunks
