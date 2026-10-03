"""OpenAI-compatible vLLM provider with a deferred optional dependency."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from hermes.inference.llm import LLMProvider


class VLLMProvider(LLMProvider):
    """Call a local vLLM OpenAI-compatible server."""

    name = "vllm"

    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None, timeout: float = 60.0, client: Any | None = None) -> None:
        self.base_url = base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        self.model = model or os.getenv("VLLM_MODEL", "")
        self.api_key = api_key or os.getenv("VLLM_API_KEY", "local")
        self.timeout = timeout
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
        response = await self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        return response.choices[0].message.content or ""

    async def stream(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> AsyncIterator[str]:
        if not self.model:
            raise ValueError("VLLM_MODEL must be set before generating text")
        response = await self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
