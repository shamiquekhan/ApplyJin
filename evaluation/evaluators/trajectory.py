"""Simple expected-step evaluation for bounded agent workflows."""

from __future__ import annotations


def evaluate_trajectory(expected_steps: list[str], actual_steps: list[str]) -> dict[str, float]:
    expected = set(expected_steps)
    actual = set(actual_steps)
    return {
        "trajectory_recall": len(expected & actual) / len(expected) if expected else 1.0,
        "trajectory_precision": len(expected & actual) / len(actual) if actual else 0.0,
    }