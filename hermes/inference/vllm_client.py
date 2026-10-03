"""OpenAI-compatible vLLM provider with a deferred optional dependency."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any

from hermes.inference.llm import LLMProvider
from hermes.inference.metrics import GenerationObservation, INFERENCE_METRICS


class VLLMProvider(LLMProvider):
    """Call a local vLLM OpenAI-compatible server."""

    name = "vllm"

    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None, timeout: float = 60.0, client: Any | None = None) -> None:
        self.base_url = base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
        self.model = model or os.getenv("VLLM_MODEL", "")
        self.api_key = api_key or os.getenv("VLLM_API_KEY", "local")
        self.timeout = timeout
        self.last_metrics: GenerationObservation | None = None
        if client is not None:
            self.client = client
            return
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("vLLM support requires: pip install '.[vllm]'") from exc
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout)

    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> str:
        if not self.model:
            raise ValueError("VLLM_MODEL must be set before generating text")
        started = time.perf_counter()
        try:
            response = await self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens)
            content = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            observation = GenerationObservation(
                provider=self.name,
                model=self.model,
                latency_ms=(time.perf_counter() - started) * 1000,
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            )
            self.last_metrics = observation
            INFERENCE_METRICS.record_generation(observation)
            return content
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

    async def stream(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> AsyncIterator[str]:
        if not self.model:
            raise ValueError("VLLM_MODEL must be set before generating text")
        started = time.perf_counter()
        first_token_at: float | None = None
        output_tokens = 0
        try:
            response = await self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True)
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    first_token_at = first_token_at or time.perf_counter()
                    output_tokens += max(1, len(delta.split()))
                    yield delta
            finished = time.perf_counter()
            ttft_ms = ((first_token_at or finished) - started) * 1000
            observation = GenerationObservation(
                provider=self.name,
                model=self.model,
                latency_ms=(finished - started) * 1000,
                ttft_ms=ttft_ms,
                tpot_ms=max(0.0, (finished - (first_token_at or finished)) * 1000) / output_tokens if output_tokens else 0.0,
                output_tokens=output_tokens,
            )
            self.last_metrics = observation
            INFERENCE_METRICS.record_generation(observation)
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
