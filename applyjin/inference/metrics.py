"""Dependency-free runtime metrics for local operation and tests."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerationObservation:
    provider: str
    model: str
    latency_ms: float
    ttft_ms: float = 0.0
    tpot_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False


@dataclass
class RuntimeMetrics:
    counters: Counter[str] = field(default_factory=Counter)
    latencies_ms: list[float] = field(default_factory=list)
    generation_observations: list[GenerationObservation] = field(default_factory=list)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def observe_latency(self, latency_ms: float) -> None:
        self.latencies_ms.append(round(latency_ms, 2))

    def record_generation(self, observation: GenerationObservation) -> None:
        self.generation_observations.append(observation)
        self.increment("generation_requests")
        if observation.failed:
            self.increment("generation_failures")

    def snapshot(self) -> dict[str, object]:
        latencies = sorted(self.latencies_ms)
        p95_index = max(0, min(len(latencies) - 1, round((len(latencies) - 1) * 0.95))) if latencies else 0
        return {
            "counters": dict(self.counters),
            "observations": len(latencies),
            "latency_p95_ms": latencies[p95_index] if latencies else 0.0,
            "generation_observations": len(self.generation_observations),
        }

    def prometheus_text(self, namespace: str = "applyjin") -> str:
        """Render counters and latency as Prometheus exposition text."""
        lines = []
        for name, value in sorted(self.counters.items()):
            metric = f"{namespace}_{name}"
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric} {value}")
        snapshot = self.snapshot()
        metric = f"{namespace}_decision_latency_p95_ms"
        lines.append(f"# TYPE {metric} gauge")
        lines.append(f"{metric} {snapshot['latency_p95_ms']}")
        return "\n".join(lines) + "\n"


DECISION_METRICS = RuntimeMetrics()
INFERENCE_METRICS = RuntimeMetrics()
