"""Canonical async providers: a single-model LiteLLM adapter and the router bridge.

``LiteLLMProvider`` is the canonical ``LLMProvider`` for one chain entry: one
model, one key, one call. ``RouterProvider`` keeps the whole failover chain
behind the async contract while agents migrate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Callable

from hermes.inference.llm import LLMProvider
from hermes.inference.metrics import GenerationObservation, INFERENCE_METRICS

if TYPE_CHECKING:
    from hermes.utils.llm_router import LLMRouter


def _default_completion(**kwargs: Any) -> Any:
    """Lazy litellm import (heavy), mirroring ``LLMRouter._litellm_completion``."""
    import litellm

    litellm.suppress_debug_info = True  # hide "Give Feedback" banners
    # Gemini 3.x emits harmless sampling-param deprecation warnings.
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    return litellm.completion(**kwargs)


def _content(response: Any) -> str:
    choices = response["choices"] if isinstance(response, dict) else response.choices
    message = choices[0]["message"] if isinstance(choices[0], dict) else choices[0].message
    content = message["content"] if isinstance(message, dict) else message.content
    return content or ""


def _usage(response: Any) -> tuple[int, int]:
    usage = response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    if usage is None:
        return 0, 0

    def read(name: str) -> int:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        return int(value or 0)

    return read("prompt_tokens"), read("completion_tokens")


class LiteLLMProvider(LLMProvider):
    """Canonical single-model adapter over one LiteLLM completion call."""

    name = "litellm"

    def __init__(
        self,
        model: str,
        *,
        api_key: str = "",
        api_base: str | None = None,
        timeout: float = 60.0,
        provider_name: str = "litellm",
        completion: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout
        self.name = provider_name or "litellm"
        self.completion = completion
        self.last_metrics: GenerationObservation | None = None

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.timeout,
        }
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
            kwargs["api_key"] = self.api_key or "ollama"
        else:
            kwargs["api_key"] = self.api_key
        started = time.perf_counter()
        try:
            completion = self.completion or _default_completion
            response = await asyncio.to_thread(completion, **kwargs)
            input_tokens, output_tokens = _usage(response)
            observation = GenerationObservation(
                provider=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - started) * 1000,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.last_metrics = observation
            INFERENCE_METRICS.record_generation(observation)
            return _content(response)
        except Exception:
            observation = GenerationObservation(
                provider=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - started) * 1000,
                failed=True,
            )
            self.last_metrics = observation
            INFERENCE_METRICS.record_generation(observation)
            raise

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        # LiteLLMRouter's synchronous contract has no streaming method yet.
        yield await self.generate(messages, temperature, max_tokens)


class RouterProvider(LLMProvider):
    """Compatibility adapter: the whole sync ``LLMRouter`` chain, one async call."""

    name = "router"

    def __init__(self, router: "LLMRouter") -> None:
        self.router = router

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        system = "\n".join(
            message["content"] for message in messages if message.get("role") == "system"
        )
        prompt = "\n".join(
            message["content"] for message in messages if message.get("role") != "system"
        )
        response = await asyncio.to_thread(self.router.complete, prompt, system)
        return response.text

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        # LiteLLMRouter's synchronous contract has no streaming method yet.
        yield await self.generate(messages, temperature, max_tokens)
