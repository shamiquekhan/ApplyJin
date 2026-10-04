"""Laya decision provider (in-process).

Uses the open-weight Laya System One engine (`pip install laya`) directly
via its Router — no HTTP service, no API key, no text generation. The heavy
import is deferred (same convention as litellm in llm_router.py) so tests
and keyless runs never load a checkpoint.

If Laya is not installed, has no cached checkpoint and no network, or fails
on a request, this provider reports unavailable / raises ProviderUnavailable
so DecisionAgent can fall back to the deterministic heuristic provider.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from applyjin.inference.base import DecisionProvider, ProviderUnavailable
from applyjin.inference.schemas import (
    DecisionRequest,
    DecisionResult,
)

logger = logging.getLogger("applyjin.inference.laya")

# Default rank descriptions for score questions when the caller supplies none.
_DEFAULT_SCORE_CRITERIA = {
    "0": "none at all",
    "1": "very weak",
    "2": "weak",
    "3": "moderate",
    "4": "strong",
    "5": "very strong",
}


def _score_criteria_list(question) -> list[str]:
    """Laya expects score criteria as a list ordered by rank."""
    criteria = question.criteria or {}
    if not criteria:
        criteria = _DEFAULT_SCORE_CRITERIA
    keys = sorted(criteria.keys(), key=lambda k: int(k))
    return [criteria[k] for k in keys]


def _questions_for_laya(request: DecisionRequest) -> dict[str, dict[str, Any]]:
    """Convert typed questions into Laya's native question shape."""
    out: dict[str, dict[str, Any]] = {}
    for name, q in request.questions.items():
        entry: dict[str, Any] = {
            "type": q.type,
            "instructions": q.instructions,
        }
        if q.labels:
            entry["labels"] = dict(q.labels)
        if q.type == "choice":
            if q.criteria:
                entry["criteria"] = dict(q.criteria)
        elif q.type == "score":
            entry["criteria"] = _score_criteria_list(q)
        # noul: no criteria needed (it is a yes/no probability).
        out[name] = entry
    return out


def _extract_answer(
    name: str,
    q,
    entry: dict[str, Any],
) -> Any:
    """Pull the normalized answer out of one Laya answer entry.

    Laya's answer shape (per checkpoint version) is roughly:
      choice -> {"choice": label, ...}
      score  -> {"score": int, ...}
      noul   -> {"noul": float, ...}
    plus confidence/abstention fields. Read defensively.
    """
    if q.type == "choice":
        value = entry.get("choice")
        if value is None and entry.get("answer") is not None:
            value = entry["answer"]
        return "" if value is None else str(value)
    if q.type == "score":
        value = entry.get("score")
        if value is None:
            value = entry.get("answer")
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return q.scale[0]
    # noul
    value = entry.get("noul")
    if value is None:
        value = entry.get("probability")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.5


class LayaDecisionProvider(DecisionProvider):
    """In-process Laya Router behind the DecisionProvider interface."""

    name = "laya"

    def __init__(
        self,
        model: Optional[str] = None,
        device: Optional[str] = None,
        preload: bool = False,
        max_len: Optional[int] = None,
    ) -> None:
        self._model = model or os.getenv("LAYA_MODEL") or None
        self._device = device or os.getenv("LAYA_DEVICE") or None
        self._preload = preload
        self._max_len = max_len or int(os.getenv("LAYA_MAX_LEN", "0")) or None
        self._router: Any = None
        self._import_failed = False
        self._failed_forever = False

    # ------------------------------------------------------------- setup

    def _get_router(self) -> Any:
        if self._router is not None:
            return self._router
        if self._import_failed or self._failed_forever:
            raise ProviderUnavailable("laya router unavailable")
        try:
            from laya import Router  # deferred: heavy import + checkpoint
        except ImportError as exc:
            logger.info("Laya not installed (%s) — heuristic decisions only", exc)
            self._import_failed = True
            raise ProviderUnavailable("laya is not installed") from exc
        try:
            kwargs: dict[str, Any] = {}
            if self._device:
                kwargs["device"] = self._device
            if self._preload:
                kwargs["preload"] = True
            self._router = Router(**kwargs)
        except Exception as exc:  # noqa: BLE001 — checkpoint load can vary
            logger.warning("Laya Router failed to load: %s", exc)
            self._failed_forever = True
            raise ProviderUnavailable(f"laya router load failed: {exc}") from exc
        return self._router

    @property
    def available(self) -> bool:
        try:
            self._get_router()
        except ProviderUnavailable:
            return False
        return True

    # ------------------------------------------------------------ decide

    def decide(self, request: DecisionRequest) -> DecisionResult:
        router = self._get_router()
        questions = _questions_for_laya(request)
        started = time.perf_counter()
        try:
            kwargs: dict[str, Any] = {}
            if self._model:
                kwargs["model"] = self._model
            if self._max_len:
                kwargs["max_len"] = self._max_len
            result = router.predict(request.state, questions, **kwargs)
        except ProviderUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — network, OOM, shape drift
            raise ProviderUnavailable(f"laya predict failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000.0

        answers_raw = (result or {}).get("answers", {})
        answers = {}
        for name, q in request.questions.items():
            entry = answers_raw.get(name)
            if not isinstance(entry, dict):
                raise ProviderUnavailable(
                    f"laya returned no answer for question '{name}'"
                )
            value = _extract_answer(name, q, entry)
            prob_map = entry.get("probabilities") or {}
            confidence = entry.get("answer_confidence")
            if confidence is None:
                confidence = entry.get("confidence", 0.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0

            if q.type == "choice":
                probability = prob_map.get(value) if prob_map else None
            elif q.type == "score":
                lo, hi = q.scale
                probability = (
                    (float(value) - lo) / (hi - lo) if hi > lo else None
                )
            else:  # noul — DecisionAnswer contract: value is "true"/"false",
                # the raw P(yes) belongs in probability.
                probability = float(value) if isinstance(value, float) else None
                if probability is not None:
                    value = "true" if probability >= 0.5 else "false"

            from applyjin.inference.schemas import DecisionAnswer

            answers[name] = DecisionAnswer(
                question=name,
                type=q.type,
                value=value if isinstance(value, str) else str(value),
                probability=probability,
                confidence=confidence,
                probabilities={
                    str(k): float(v)
                    for k, v in prob_map.items()
                    if isinstance(v, (int, float))
                },
            )

        routing = (result or {}).get("routing", {})
        model_name = str(routing.get("model", self._model or "laya"))

        return DecisionResult(
            answers=answers,
            model=model_name,
            backend="laya",
            latency_ms=round(latency_ms, 2),
            raw={"routing": routing} if routing else {},
        )

    def close(self) -> None:
        self._router = None
