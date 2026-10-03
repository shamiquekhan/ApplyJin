"""Small deterministic correctness evaluators for golden cases."""

from __future__ import annotations


def evaluate_classification(expected: str, actual: str) -> dict[str, float | bool]:
    matched = expected.strip().lower() == actual.strip().lower()
    return {"correct": matched, "score": 1.0 if matched else 0.0}


def evaluate_gating(expected: str, actual: str) -> dict[str, float | bool]:
    return evaluate_classification(expected, actual)
