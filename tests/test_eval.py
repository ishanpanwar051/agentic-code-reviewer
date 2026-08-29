"""Unit tests for evaluation harness and metrics calculation."""

import json
from pathlib import Path
import pytest
from eval_harness import (
    calculate_metrics,
    evaluate_commit_finding,
    load_dataset,
)
from src.models import ReviewComment


def test_calculate_metrics_perfect_score():
    """Verifies perfect precision, recall, and F1 calculation."""
    metrics = calculate_metrics(tp=10, fp=0, fn=0)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_calculate_metrics_with_false_positives():
    """Verifies precision drop with false positives."""
    metrics = calculate_metrics(tp=5, fp=5, fn=0)
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 0.6667


def test_calculate_metrics_zero_division():
    """Verifies zero division safety."""
    metrics = calculate_metrics(tp=0, fp=0, fn=0)
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_evaluate_commit_finding_tolerance():
    """Verifies that finding within +/- 1 line tolerance counts as True Positive."""
    comments = [
        ReviewComment(path="test.py", line=15, severity="critical", category="security", comment="Bug 1"),
        ReviewComment(path="test.py", line=50, severity="info", category="style", comment="Noise"),
    ]
    expected_lines = [16]  # Line 15 matches line 16 with tolerance=1

    tp, fp, fn = evaluate_commit_finding(comments, expected_lines, tolerance=1)
    assert tp == 1
    assert fp == 1
    assert fn == 0


def test_load_dataset_valid(tmp_path: Path):
    """Verifies loading jsonl dataset."""
    sample_file = tmp_path / "test_data.jsonl"
    sample_file.write_text(
        '{"id": 1, "repo": "a/b", "fix_message": "fix", "expected_lines": [10], "buggy_diff": "diff"}\n',
        encoding="utf-8",
    )
    dataset = load_dataset(sample_file)
    assert len(dataset) == 1
    assert dataset[0]["id"] == 1
    assert dataset[0]["expected_lines"] == [10]
