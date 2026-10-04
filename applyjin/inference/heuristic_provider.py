"""Deterministic heuristic decision provider (the always-works fallback).

Mirrors the Laya provider's interface so DecisionAgent can degrade
gracefully: keyless runs, offline CI, or a failed Laya load still produce
typed decisions — just lower-quality ones. Rules are deliberately simple,
explainable, and never invent information.
"""

from __future__ import annotations

import logging
import re
import time

from applyjin.inference.base import DecisionProvider, ProviderUnavailable
from applyjin.inference.schemas import (
    DecisionAnswer,
    DecisionRequest,
    DecisionResult,
)

logger = logging.getLogger("applyjin.inference.heuristic")

# Ordered job-type keywords: first hit wins (more specific first).
_JOB_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("ML Engineer", ["ml engineer", "machine learning engineer", "ml research"]),
    ("Data Scientist", ["data scientist", "data science"]),
    ("AI Engineer", ["ai engineer", "applied ai", "llm", "genai", "generative ai"]),
    ("Data Engineer", ["data engineer", "data pipeline", "etl", "analytics engineer"]),
    ("Software Engineer", ["software engineer", "backend", "frontend", "full stack",
                           "fullstack", "platform engineer", "devops", "sre"]),
]

_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+)?(?:previous\s+|prior\s+)?instructions",
    r"disregard\s+(?:all\s+|any\s+)?(?:previous\s+|prior\s+)?instructions",
    r"you are now (a|an|the)",
    r"act as (a|an) (?!hiring|recruiter|interviewer)",
    r"forget (everything|all|your) (above|instructions|training)",
    r"new instructions?:",
    r"system prompt",
    r"reveal (your )?(system|initial) (prompt|instructions)",
    r"override (your )?(instructions|rules|policy)",
    r"jailbreak",
    r"developer mode",
]


class HeuristicDecisionProvider(DecisionProvider):
    """Rule-based decisions: zero dependencies, deterministic, offline."""

    name = "heuristic"

    def __init__(self) -> None:
        self._injection_re = re.compile(
            "|".join(_INJECTION_PATTERNS), re.IGNORECASE
        )

    @property
    def available(self) -> bool:
        return True

    def decide(self, request: DecisionRequest) -> DecisionResult:
        started = time.perf_counter()
        answers: dict[str, DecisionAnswer] = {}
        for name, q in request.questions.items():
            answers[name] = self._answer(name, q, request.state)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return DecisionResult(
            answers=answers,
            model="rules-v1",
            backend="heuristic",
            latency_ms=round(latency_ms, 2),
        )

    # ------------------------------------------------------------- rules

    def _answer(self, name: str, q, state: str) -> DecisionAnswer:
        lowered = state.lower()
        if q.type == "choice":
            if "job" in name or "categor" in name or "type" in name:
                return self._choice_job_type(name, q, lowered)
            # Generic choice: pick the label whose description keywords
            # overlap the state most (transparent tie-break: first label).
            best, best_score = "", -1
            for label, desc in (q.criteria or {}).items():
                tokens = re.findall(r"[a-z]+", (desc or "").lower())
                score = sum(1 for t in tokens if t in lowered)
                if score > best_score:
                    best, best_score = label, score
            prob = 1.0 if best_score > 0 else 0.0
            return DecisionAnswer(
                question=name, type=q.type, value=best,
                probability=prob, confidence=0.4 if best_score > 0 else 0.2,
            )
        if q.type == "score":
            return self._score_generic(name, q, state, lowered)
        # noul
        if "injection" in name or "untrusted" in name or "manipulat" in name:
            return self._noul_injection(name, lowered)
        if "requirement" in name or "core" in name:
            return self._noul_core_requirements(name, q, state, lowered)
        if "fit" in name or "eligible" in name or "should" in name:
            return self._noul_affirmative_gate(name, lowered)
        return self._noul_default(name)

    # -- specific rules -------------------------------------------------

    def _choice_job_type(self, name, q, lowered):
        for label, keywords in _JOB_TYPE_RULES:
            for kw in keywords:
                if kw in lowered:
                    # Normalize to the closest offered label if needed.
                    if label in (q.criteria or {}):
                        chosen = label
                    else:
                        chosen = _closest_label(label, q.criteria or {})
                    return DecisionAnswer(
                        question=name, type="choice", value=chosen,
                        probability=0.6, confidence=0.5,
                        probabilities={chosen: 0.6},
                    )
        fallback = "Other" if "Other" in (q.criteria or {}) else _first_label(q.criteria)
        return DecisionAnswer(
            question=name, type="choice", value=fallback,
            probability=0.3, confidence=0.2,
        )

    def _score_generic(self, name, q, state, lowered) -> DecisionAnswer:
        lo, hi = q.scale
        # Evidence-density proxy: how many criteria descriptions appear.
        hints = [d for d in (q.criteria or {}).values() if d]
        hits = 0
        for h in hints:
            for token in re.findall(r"[a-z]{4,}", h.lower()):
                if token in lowered:
                    hits += 1
                    break
        span = max(1, len(hints) or 1)
        frac = min(1.0, hits / span) if hints else 0.3
        value = int(round(lo + frac * (hi - lo)))
        return DecisionAnswer(
            question=name, type="score", value=str(value),
            probability=frac, confidence=0.3,
        )

    def _noul_injection(self, name, lowered) -> DecisionAnswer:
        hit = self._injection_re.search(lowered)
        p = 0.95 if hit else 0.02
        return DecisionAnswer(
            question=name, type="noul",
            value="true" if hit else "false",
            probability=p, confidence=0.7 if hit else 0.6,
            probabilities={"true": p, "false": round(1.0 - p, 4)},
        )

    def _noul_core_requirements(self, name, q, state, lowered) -> DecisionAnswer:
        # Heuristic: fraction of requirement-ish skill tokens present.
        req_terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}", state)
        # The state mixes job + evidence; estimate coverage of the 12 most
        # distinctive capitalized tokens (likely skills/technologies).
        caps = [t for t in req_terms if t[0].isupper()][:12]
        if not caps:
            return DecisionAnswer(
                question=name, type="noul", value="false",
                probability=0.4, confidence=0.2,
            )
        covered = sum(1 for t in caps if t.lower() in lowered)
        frac = covered / len(caps)
        p = round(min(0.95, max(0.05, frac)), 3)
        return DecisionAnswer(
            question=name, type="noul",
            value="true" if p >= 0.5 else "false",
            probability=p, confidence=0.3,
            probabilities={"true": p, "false": round(1.0 - p, 4)},
        )

    def _noul_affirmative_gate(self, name, lowered) -> DecisionAnswer:
        strong = ["python", "engineer", "developer", "software"]
        hits = sum(1 for kw in strong if kw in lowered)
        p = 0.8 if hits >= 2 else 0.55 if hits == 1 else 0.35
        return DecisionAnswer(
            question=name, type="noul", value="true" if p >= 0.5 else "false",
            probability=p, confidence=0.3,
            probabilities={"true": p, "false": round(1.0 - p, 4)},
        )

    def _noul_default(self, name) -> DecisionAnswer:
        return DecisionAnswer(
            question=name, type="noul", value="false",
            probability=0.5, confidence=0.1,
        )


def _first_label(criteria: dict[str, str]) -> str:
    return next(iter(criteria), "")


def _closest_label(target: str, criteria: dict[str, str]) -> str:
    target_l = target.lower()
    for label in criteria:
        if target_l in label.lower() or label.lower() in target_l:
            return label
    return _first_label(criteria)

