"""Decision provider abstraction.

Agents depend on DecisionProvider, never on a concrete decision model.
This lets Laya be replaced (or upgraded) without touching agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from applyjin.inference.schemas import DecisionRequest, DecisionResult


class ProviderUnavailable(RuntimeError):
    """Raised when the decision provider cannot answer right now."""


class DecisionProvider(ABC):
    """A System One style decision engine: typed questions, no generation."""

    name: str = "provider"

    @abstractmethod
    def decide(self, request: DecisionRequest) -> DecisionResult:
        """Answer all questions in the request against the state."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether the provider can currently serve decisions."""

    def close(self) -> None:
        """Release any held resources (checkpoints, sessions)."""
