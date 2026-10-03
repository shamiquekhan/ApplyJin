"""Dependency-free percentile calculation for evaluation reports."""

from __future__ import annotations


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percentage / 100) * (len(ordered) - 1))))
    return ordered[index]
