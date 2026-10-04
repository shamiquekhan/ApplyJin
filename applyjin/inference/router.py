"""Explicit, inspectable model-routing decisions."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RoutingWeights:
    quality: float = 1.0
    latency: float = 0.2
    resource: float = 0.1
    failure: float = 0.5

    @classmethod
    def from_environment(cls) -> "RoutingWeights":
        """Load routing trade-offs without embedding policy in prompts."""
        def value(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, default))
            except (TypeError, ValueError):
                return default

        return cls(
            quality=value("APPLYJIN_ROUTE_QUALITY_WEIGHT", 1.0),
            latency=value("APPLYJIN_ROUTE_LATENCY_WEIGHT", 0.2),
            resource=value("APPLYJIN_ROUTE_RESOURCE_WEIGHT", 0.1),
            failure=value("APPLYJIN_ROUTE_FAILURE_WEIGHT", 0.5),
        )


@dataclass(frozen=True)
class ModelCandidate:
    name: str
    quality: float
    latency_ms: float
    resource_cost: float
    failure_probability: float
    max_context: int = 8192
    latency_budget_ms: float = 1000.0
    resource_budget: float = 10.0

    @staticmethod
    def _bounded(value: float) -> float:
        return min(1.0, max(0.0, value))

    @property
    def latency_score(self) -> float:
        return self._bounded(self.latency_ms / self.latency_budget_ms)

    @property
    def resource_score(self) -> float:
        return self._bounded(self.resource_cost / self.resource_budget)


def utility(candidate: ModelCandidate, weights: RoutingWeights = RoutingWeights()) -> float:
    """Return the configured utility score used for model selection."""
    return (
        weights.quality * candidate._bounded(candidate.quality)
        - weights.latency * candidate.latency_score
        - weights.resource * candidate.resource_score
        - weights.failure * candidate._bounded(candidate.failure_probability)
    )


def choose_model(
    candidates: list[ModelCandidate],
    *,
    context_length: int = 0,
    weights: RoutingWeights = RoutingWeights(),
) -> ModelCandidate | None:
    """Choose the highest-utility capable model, or ``None`` for review."""
    capable = [candidate for candidate in candidates if candidate.max_context >= context_length]
    return max(capable, key=lambda candidate: utility(candidate, weights), default=None)


def order_candidates(
    candidates: list[ModelCandidate],
    *,
    context_length: int = 0,
    weights: RoutingWeights = RoutingWeights(),
) -> list[ModelCandidate]:
    """Return capable candidates in utility order for failover routing."""
    return sorted(
        (candidate for candidate in candidates if candidate.max_context >= context_length),
        key=lambda candidate: utility(candidate, weights),
        reverse=True,
    )
