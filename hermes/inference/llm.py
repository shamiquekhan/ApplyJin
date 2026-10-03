"""Provider-neutral asynchronous text generation contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    """The application-facing contract for local or remote generation."""

    name: str = "provider"

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> AsyncIterator[str]:
        raise NotImplementedError
