"""Stable failure taxonomy shared by inference and evaluation telemetry."""

from __future__ import annotations

from enum import StrEnum


class FailureCode(StrEnum):
    RETRIEVAL_EMPTY = "RETRIEVAL_EMPTY"
    RETRIEVAL_LOW_CONFIDENCE = "RETRIEVAL_LOW_CONFIDENCE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_OVERLOADED = "MODEL_OVERLOADED"
    MODEL_OOM = "MODEL_OOM"
    MODEL_INVALID_OUTPUT = "MODEL_INVALID_OUTPUT"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_BAD_RESPONSE = "TOOL_BAD_RESPONSE"
    POLICY_REJECTION = "POLICY_REJECTION"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


def classify_failure(error: BaseException) -> FailureCode:
    """Map provider/tool exceptions to a stable operational category."""
    message = str(error).lower()
    name = type(error).__name__.lower()
    if "timeout" in message or "timeout" in name:
        return FailureCode.MODEL_TIMEOUT
    if "oom" in message or "out of memory" in message:
        return FailureCode.MODEL_OOM
    if "json" in message or "invalid" in message:
        return FailureCode.MODEL_INVALID_OUTPUT
    if "429" in message or "overload" in message:
        return FailureCode.MODEL_OVERLOADED
    return FailureCode.TOOL_BAD_RESPONSE