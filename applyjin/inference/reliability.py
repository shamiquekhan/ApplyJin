"""Small dependency-free retry and circuit-breaker primitives."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class CircuitOpen(RuntimeError):
    """Raised before calling a provider while its circuit is open."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    @property
    def open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def before_call(self) -> None:
        if self.open:
            raise CircuitOpen("provider circuit is open")

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


async def call_with_retry(operation: Callable[[], Awaitable[T]], *, attempts: int = 2, backoff_seconds: float = 0.25, breaker: CircuitBreaker | None = None) -> T:
    """Retry provider failures and trip the optional breaker."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    breaker = breaker or CircuitBreaker()
    breaker.before_call()
    for attempt in range(attempts):
        try:
            result = await operation()
            breaker.success()
            return result
        except Exception:
            breaker.failure()
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(backoff_seconds * (2 ** attempt))
    raise AssertionError("unreachable")
