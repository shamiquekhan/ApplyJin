"""Bridge the legacy synchronous LLMRouter to the async provider contract."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from hermes.inference.llm import LLMProvider

if TYPE_CHECKING:
    from hermes.utils.llm_router import LLMRouter


class LiteLLMProvider(LLMProvider):
    """Compatibility adapter while agents migrate to ``LLMProvider``."""

    name = "litellm"

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