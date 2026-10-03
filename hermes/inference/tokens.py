"""Token counting: a dependency-free baseline plus model-specific counters.

Every budget, truncation, and router ``context_length`` value in ApplyJin is
expressed in model tokens. ``ApproximateTokenCounter`` is the default (no
third-party imports, ~4 chars/token behaviour); when a model's tokenizer is
installed, ``counter_for_model`` silently upgrades to exact counting.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Protocol, runtime_checkable

logger = logging.getLogger("hermes.tokens")


def estimate_tokens(text: str) -> int:
    """Estimate tokens without a model-specific tokenizer (word/punct units)."""
    if not text:
        return 0
    return max(1, len(re.findall(r"\w+|[^\w\s]", text)))


@runtime_checkable
class TokenCounter(Protocol):
    """Counts and truncates text in model-token units."""

    def count(self, text: str) -> int:
        ...

    def truncate(self, text: str, max_tokens: int) -> str:
        ...


class ApproximateTokenCounter:
    """Regex word/punctuation estimator — the documented default baseline."""

    def count(self, text: str) -> int:
        return estimate_tokens(text)

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        if self.count(text) <= max_tokens:
            return text
        low, high = 0, len(text)
        while low < high:  # binary search: count() is monotonic over prefixes
            mid = (low + high + 1) // 2
            if self.count(text[:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1
        return text[:low].rstrip()


class HuggingFaceTokenCounter:
    """Exact counting with a model's HuggingFace tokenizer."""

    def __init__(self, model: str) -> None:
        if not model:
            raise ValueError("HuggingFaceTokenCounter requires a model name")
        from transformers import AutoTokenizer  # deferred: heavy import

        self.model = model
        self._tokenizer = AutoTokenizer.from_pretrained(model)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._tokenizer.encode(text, add_special_tokens=False))

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        ids = self._tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= max_tokens:
            return text
        return self._tokenizer.decode(ids[:max_tokens]).strip()


class VLLMTokenCounter(HuggingFaceTokenCounter):
    """Tokenizer of the model served by the local vLLM server."""

    def __init__(self, model: str | None = None) -> None:
        super().__init__(model or os.getenv("VLLM_MODEL", ""))


def counter_for_model(model: str | None = None) -> TokenCounter:
    """Exact counter for ``model`` when its tokenizer is installed, else baseline."""
    if model:
        try:
            return HuggingFaceTokenCounter(model)
        except Exception as exc:  # noqa: BLE001 — optional dependency / offline
            logger.debug("Tokenizer for %s unavailable (%s) — using approximation", model, exc)
    return ApproximateTokenCounter()
