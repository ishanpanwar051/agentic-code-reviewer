"""Tests for unified diff parser and code chunking logic."""

from src.diff_parser import chunk_file_diff, parse_unified_diff
from src.models import DiffHunk, DiffLine, FileDiff


def test_parse_single_hunk(diff_single_hunk: str):
    """Verifies single hunk parsing and line-number mathematics."""
    file_diffs = parse_unified_diff(diff_single_hunk)
    assert len(file_diffs) == 1

    fd = file_diffs[0]
    assert fd.new_path == "src/calculator.py"
    assert fd.change_type == "MODIFIED"
    assert len(fd.hunks) == 1

    hunk = fd.hunks[0]
    assert hunk.new_start == 10
    # Added lines: line 13 and line 14 (multiply function)
    assert hunk.added_line_numbers == [13, 14]
    assert fd.total_additions == 2
    assert fd.total_deletions == 0


def test_parse_multi_hunk(diff_multi_hunk: str):
    """Verifies multiple hunks within a single file."""
    file_diffs = parse_unified_diff(diff_multi_hunk)
    assert len(file_diffs) == 1

    fd = file_diffs[0]
    assert len(fd.hunks) == 2
    assert fd.hunks[0].added_line_numbers == [2]
    # In second hunk: line 22 and 23 are added
    assert fd.hunks[1].added_line_numbers == [22, 23]
    assert fd.total_additions == 3
    assert fd.total_deletions == 1


def test_parse_new_file(diff_new_file: str):
    """Verifies newly added file (@@ -0,0 +1,5 @@)."""
    file_diffs = parse_unified_diff(diff_new_file)
    assert len(file_diffs) == 1
    fd = file_diffs[0]
    assert fd.change_type == "ADDED"
    assert fd.old_path == "src/new_module.py"
    assert fd.new_path == "src/new_module.py"
    assert len(fd.hunks[0].added_line_numbers) == 5
    assert fd.hunks[0].added_line_numbers == [1, 2, 3, 4, 5]


def test_parse_deleted_file(diff_deleted_file: str):
    """Verifies deleted file mode."""
    file_diffs = parse_unified_diff(diff_deleted_file)
    assert len(file_diffs) == 1
    fd = file_diffs[0]
    assert fd.change_type == "DELETED"
    assert fd.total_deletions == 3


def test_parse_binary_and_rename(diff_binary_file: str, diff_rename_100: str):
    """Verifies binary assets and 100% renames are categorized."""
    bin_diffs = parse_unified_diff(diff_binary_file)
    assert len(bin_diffs) == 1
    assert bin_diffs[0].is_binary is True

    rename_diffs = parse_unified_diff(diff_rename_100)
    assert len(rename_diffs) == 1
    assert rename_diffs[0].is_rename is True
    assert rename_diffs[0].change_type == "RENAMED"


def test_parse_no_newline_marker(diff_no_newline: str):
    """Verifies '\ No newline at end of file' lines are safely ignored."""
    file_diffs = parse_unified_diff(diff_no_newline)
    assert len(file_diffs) == 1
    fd = file_diffs[0]
    assert len(fd.hunks) == 1
    assert fd.hunks[0].added_line_numbers == [1]


def test_parse_skip_paths_filter(diff_skip_paths: str):
    """Verifies skip_patterns excludes matching files."""
    file_diffs = parse_unified_diff(
        diff_skip_paths,
        skip_patterns=["package-lock.json", "dist/*"],
    )
    assert len(file_diffs) == 0


def test_parse_empty_diff():
    """Verifies empty diff returns empty list."""
    assert parse_unified_diff("") == []
    assert parse_unified_diff("   ") == []


def test_chunk_file_diff_small():
    """Small diff under max_lines produces single chunk with is_partial=False."""
    lines = [
        DiffLine(type=" ", old_lineno=1, new_lineno=1, content="import math"),
        DiffLine(type="+", old_lineno=None, new_lineno=2, content="def sq(x): return x*x"),
    ]
    hunk = DiffHunk(old_start=1, old_lines=1, new_start=1, new_lines=2, header="@@ -1 +1,2 @@", lines=lines)
    fd = FileDiff(old_path="a.py", new_path="a.py", change_type="MODIFIED", hunks=[hunk])

    chunks = chunk_file_diff(fd, max_lines=150, overlap=20)
    assert len(chunks) == 1
    assert chunks[0].is_partial is False
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert chunks[0].added_line_numbers == [2]


def test_chunk_file_diff_large():
    """Large diff produces overlapping chunks preserving exact line mappings."""
    lines = []
    for i in range(1, 301):
        lines.append(
            DiffLine(
                type="+" if i % 2 == 0 else " ",
                old_lineno=i if i % 2 != 0 else None,
                new_lineno=i,
                content=f"line {i}",
            )
        )
    hunk = DiffHunk(old_start=1, old_lines=150, new_start=1, new_lines=300, header="@@ -1,150 +1,300 @@", lines=lines)
    fd = FileDiff(old_path="large.py", new_path="large.py", change_type="MODIFIED", hunks=[hunk])

    chunks = chunk_file_diff(fd, max_lines=100, overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.is_partial is True
        assert chunk.file_path == "large.py"
        assert len(chunk.lines) <= 100
        # Verify added_line_numbers strictly fall within chunk line bounds
        for lineno in chunk.added_line_numbers:
            assert chunk.start_line <= lineno <= chunk.end_line
