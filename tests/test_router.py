"""Router hardening tests: throttling, retry-hint handling, empty output."""

from __future__ import annotations

import time

import pytest

from hermes.config import LLMConfig, ChainProvider, GenerationSettings, RetrySettings
from hermes.models import LLMResponse
from hermes.utils.llm_router import LLMRouter


class _ScriptedRouter(LLMRouter):
    """Router whose litellm 'completion' is a script of behaviors."""

    def __init__(self, behaviors: list) -> None:
        super().__init__(LLMConfig(retries=RetrySettings(attempts=2, backoff_seconds=0)))
        self.behaviors = behaviors
        self.calls = 0

    def _litellm_completion(self):
        return self

    def completion(self, **kwargs):
        behavior = self.behaviors[min(self.calls, len(self.behaviors) - 1)]
        self.calls += 1
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


def _ok_response(text="ok"):
    return {"choices": [{"message": {"content": text}}]}


class TestRateLimitHandling:
    def test_429_waits_and_retries_then_succeeds(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        rate_err = Exception(
            'litellm.RateLimitError: 429 ... "message": "Quota exceeded. '
            "Please retry in 12.5s."
        )
        router = _ScriptedRouter([rate_err, _ok_response("recovered")])
        router.config.chain = [
            ChainProvider(provider="gemini", model="gemini/gemini-3.6-flash", api_key="k")
        ]
        resp = router.complete("hi")
        assert resp.text == "recovered"
        assert router.calls == 2
        assert any(10 < s <= 90 for s in sleeps), sleeps  # honored the hint

    def test_connection_refused_skips_immediately(self):
        router = _ScriptedRouter([Exception("OllamaException Connection refused")])
        router.config.chain = [
            ChainProvider(provider="ollama", model="ollama/x", api_key="k")
        ]
        from hermes.utils.llm_router import LLMUnavailable

        with pytest.raises(LLMUnavailable):
            router.complete("hi")
        assert router.calls == 1  # no retries burned

    def test_throttle_spacing_between_calls(self, monkeypatch):
        # Replace sleep with a no-op recorder; check inter-call gap logic runs
        real_sleep = time.sleep
        call_times: list[float] = []

        class TimeRouter(_ScriptedRouter):
            def _throttle(self, model):
                self._last_call.setdefault("_t", 0)
                call_times.append(monotonic_stub[0])
                real_sleep(0)

        monotonic_stub = [0.0]
        router = TimeRouter([_ok_response("a"), _ok_response("b")])
        router.config.chain = [
            ChainProvider(provider="gemini", model="gemini/gemini-3.6-flash", api_key="k")
        ]
        router.complete("one")
        monotonic_stub[0] += 5.0  # pretend 5s passed
        router.complete("two")
        assert len(call_times) == 2


class TestProviderChain:
    def test_failover_to_second_provider(self):
        err = Exception("litellm.BadRequestError: nope")
        router = _ScriptedRouter([err, err, err, _ok_response("from-backup")])
        router.config.chain = [
            ChainProvider(provider="gemini", model="gemini/a", api_key="k"),
            ChainProvider(provider="openrouter", model="openrouter/b", api_key="k2"),
        ]
        resp = router.complete("hi")
        assert resp.text == "from-backup"
        assert resp.model == "openrouter/b"

    def test_rotation_on_429(self):
        """Hot model rotates to sibling with same key before waiting."""
        rate_err = Exception(
            "litellm.RateLimitError: 429 RESOURCE_EXHAUSTED — retry in 59.0s."
        )
        router = _ScriptedRouter([rate_err, _ok_response("from-sibling")])
        router.config.chain = [
            ChainProvider(provider="gemini", model="gemini/a", api_key="same"),
            ChainProvider(provider="gemini", model="gemini/b", api_key="same"),
            ChainProvider(provider="ollama", model="ollama/x", api_key="other"),
        ]
        # Pre-seed throttle times so no waiting happens in test
        from datetime import datetime, timedelta
        router._last_call = {}
        import hermes.utils.llm_router as lr
        original_sleep = time.sleep
        time.sleep = lambda s: None
        try:
            resp = router.complete("hi")
        finally:
            time.sleep = original_sleep
        assert resp.text == "from-sibling"
        assert resp.model == "gemini/b"

    def test_keyless_provider_skipped(self):
        router = LLMRouter()
        router.config.chain = [
            ChainProvider(provider="gemini", model="gemini/a", api_key=""),
            ChainProvider(provider="openrouter", model="openrouter/b", api_key="real"),
        ]
        assert [p["model"] for p in router._usable_providers()] == ["openrouter/b"]

    def test_no_providers_configured(self):
        router = LLMRouter()
        assert router.available is False
        from hermes.utils.llm_router import LLMUnavailable

        with pytest.raises(LLMUnavailable, match="No LLM provider"):
            router.complete("hi")
