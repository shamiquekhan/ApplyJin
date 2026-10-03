"""Benchmark matrix and quality gates for vLLM experiments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class BenchmarkCase:
    model: str
    quantization: str
    context_tokens: int
    concurrency: int
    output_tokens: int
    prefix_caching: bool


def build_matrix(
    models: list[str],
    quantizations: list[str] = ["baseline", "awq"],
    contexts: list[int] = [1024, 4096, 8192, 16384],
    concurrencies: list[int] = [1, 2, 4, 8],
    outputs: list[int] = [128, 512, 1024],
    prefix_caching: list[bool] = [False, True],
) -> list[BenchmarkCase]:
    return [
        BenchmarkCase(*values)
        for values in product(models, quantizations, contexts, concurrencies, outputs, prefix_caching)
    ]


def quantization_gate(
    baseline: dict[str, float], candidate: dict[str, float],
    *, quality_tolerance: float = 0.02, latency_tolerance: float = 0.20,
) -> dict[str, bool | float]:
    """Accept quantization only when quality and latency stay within bounds."""
    quality_delta = candidate.get("quality", 0.0) - baseline.get("quality", 0.0)
    baseline_latency = baseline.get("p95_latency_ms", 0.0)
    latency_change = (
        (candidate.get("p95_latency_ms", 0.0) - baseline_latency) / baseline_latency
        if baseline_latency else 0.0
    )
    return {
        "quality_delta": round(quality_delta, 4),
        "latency_change": round(latency_change, 4),
        "accepted": quality_delta >= -quality_tolerance and latency_change <= latency_tolerance,
    }