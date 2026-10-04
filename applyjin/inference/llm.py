"""Provider-neutral asynchronous text generation contracts."""

from __future__ import annotations

import asyncio
import atexit
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class LLMProvider(ABC):
    """The application-facing contract for local or remote generation."""

    name: str = "provider"

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2048) -> AsyncIterator[str]:
        raise NotImplementedError


class _ProviderRunner:
    """Persistent background loop so sync callers can run async providers.

    Providers are async, but the router and CLI are synchronous — and the web
    routes already run inside an event loop, so a per-call ``asyncio.run`` is
    not an option there. One daemon thread owns one loop for the process
    lifetime; coroutines are submitted with ``run_coroutine_threadsafe`` and
    the caller blocks on the result. Keeping a single loop also keeps each
    provider's HTTP client bound to one loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever,
                    name="applyjin-provider-loop",
                    daemon=True,
                )
                self._thread.start()
            return self._loop

    def submit(self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        loop = self._ensure_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            coro.close()  # never scheduled — avoid a "never awaited" warning
            raise
        try:
            return future.result(timeout)
        finally:
            if not future.done():
                future.cancel()

    def stop(self) -> None:
        with self._lock:
            loop, thread = self._loop, self._thread
            self._loop, self._thread = None, None
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)
            if thread.is_alive():
                return  # still draining; the process is exiting anyway
        if not loop.is_closed():
            loop.close()


_RUNNER = _ProviderRunner()
atexit.register(_RUNNER.stop)


def run_provider(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """Run a provider coroutine from synchronous code (running loop or not)."""
    return _RUNNER.submit(coro, timeout)
