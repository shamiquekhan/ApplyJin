"""Typed schemas for the decision layer.

Three decision primitives (System One style):
  choice -> pick one label among alternatives
  score  -> assign an integer on a bounded scale (default 0..5)
  noul   -> yes/no with a probability

These models are provider-agnostic: agents build questions against these
types, never against a specific model's wire format.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

DecisionType = Literal["choice", "score", "noul"]


class DecisionQuestion(BaseModel):
    """One typed question to ask a decision model."""

    type: DecisionType
    instructions: str
    # choice: {label: description}; score: {str(rank): description};
    # noul: {true: ..., false: ...} (optional).
    criteria: dict[str, str] = Field(default_factory=dict)
    # score bounds; ignored for choice/noul.
    scale: tuple[int, int] = (0, 5)
    labels: dict[str, str] = Field(default_factory=dict)
    min_confidence: float | None = None


class DecisionRequest(BaseModel):
    """A batch of typed questions over one state."""

    state: str
    questions: dict[str, DecisionQuestion]


class DecisionAnswer(BaseModel):
    """Normalized answer for one question, whatever the provider."""

    question: str
    type: DecisionType
    # choice: winning label; score: integer rank; noul: "true"/"false".
    value: str = ""
    # noul: P(yes); score: normalized 0..1; choice: winner's probability
    # when the provider exposes one, else confidence.
    probability: Optional[float] = None
    confidence: float = 0.0
    # Full option->probability map when the provider exposes one.
    probabilities: dict[str, float] = Field(default_factory=dict)


class DecisionResult(BaseModel):
    """Answers for one request, plus routing metadata."""

    answers: dict[str, DecisionAnswer] = Field(default_factory=dict)
    model: str = ""
    backend: str = ""          # "laya" | "heuristic" | ...
    latency_ms: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


class DecisionTrace(BaseModel):
    """Persisted, inspectable record of one decision batch.

    Store hashes, not raw personal data: input_state_hash identifies the
    state without keeping the candidate's documents in telemetry.
    """

    decision_id: str
    job_id: str = ""
    stage: str = ""            # "classify" | "gate" | "injection" | ...
    model: str = ""
    backend: str = ""
    input_state_hash: str = ""
    questions: dict[str, DecisionQuestion] = Field(default_factory=dict)
    answers: dict[str, DecisionAnswer] = Field(default_factory=dict)
    policy_version: str = ""
    action: str = ""           # policy outcome, e.g. GENERATE/REVIEW/SKIP
    latency_ms: float = 0.0
    fallback_used: bool = False
    error: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


def state_hash(state: str, length: int = 12) -> str:
    """Short hash identifying a decision state without storing its text."""
    import hashlib

    return hashlib.sha256(state.encode("utf-8")).hexdigest()[:length]
