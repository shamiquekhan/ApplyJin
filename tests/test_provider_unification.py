"""Phase 3: one canonical provider per chain entry, one sync→async runner."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import hermes.utils.llm_router as lr
from hermes.config import ChainProvider, LLMConfig, RetrySettings
from hermes.inference.litellm_client import LiteLLMProvider
from hermes.inference.llm import run_provider
from hermes.inference.metrics import INFERENCE_METRICS
from hermes.inference.vllm_client import VLLMProvider
from hermes.utils.llm_router import LLMRouter


def _vllm_router() -> LLMRouter:
    router = LLMRouter(LLMConfig(retries=RetrySettings(attempts=0, backoff_seconds=0)))
    router.config.chain = [
        ChainProvider(
            provider="vllm",
            model="openai/Qwen/Qwen3-8B",
            api_base="http://localhost:8000/v1",
        )
    ]
    return router


class TestVLLMDispatch:
    def test_vllm_entry_builds_provider_with_stripped_model(self, monkeypatch):
        seen: dict[str, object] = {}

        class _FakeVLLM:
            def __init__(self, base_url=None, model=None, api_key=None, timeout=60.0, client=None):
                seen.update(base_url=base_url, model=model, api_key=api_key, timeout=timeout)

            async def generate(self, messages, temperature=0.2, max_tokens=2048):
                seen.update(messages=messages, temperature=temperature, max_tokens=max_tokens)
                return "from-vllm"

        monkeypatch.setattr(lr, "VLLMProvider", _FakeVLLM)
        router = _vllm_router()
        gen = router.config.generation
        resp = router.complete("hi")

        assert resp.text == "from-vllm"
        assert resp.model == "openai/Qwen/Qwen3-8B"
        assert resp.provider == "openai"
        assert seen["model"] == "Qwen/Qwen3-8B"  # OpenAI client gets the bare name
        assert seen["base_url"] == "http://localhost:8000/v1"
        assert seen["api_key"] == "local"
        assert seen["timeout"] == gen.timeout_seconds
        assert seen["messages"] == [{"role": "user", "content": "hi"}]
        assert seen["temperature"] == gen.temperature
        assert seen["max_tokens"] == gen.max_tokens

    def test_vllm_dispatch_records_generation_telemetry(self, monkeypatch):
        class _Completions:
            async def create(self, **kwargs):
                assert kwargs["model"] == "Qwen/Qwen3-8B"
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
                    usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2),
                )

        class _Client:
            chat = SimpleNamespace(completions=_Completions())

        def _factory(**kwargs):
            kwargs["client"] = _Client()
            return VLLMProvider(**kwargs)

        monkeypatch.setattr(lr, "VLLMProvider", _factory)
        before = len(INFERENCE_METRICS.generation_observations)
        resp = _vllm_router().complete("hi")
        new = INFERENCE_METRICS.generation_observations[before:]

        assert resp.text == "hi"
        observation = next(o for o in new if o.provider == "vllm")
        assert observation.input_tokens == 7
        assert observation.output_tokens == 2
        assert observation.failed is False

    def test_adapter_cache_reuses_instance_per_entry(self, monkeypatch):
        built: list[dict] = []

        class _FakeVLLM:
            def __init__(self, **kwargs):
                built.append(kwargs)

            async def generate(self, messages, temperature=0.2, max_tokens=2048):
                return "x"

        monkeypatch.setattr(lr, "VLLMProvider", _FakeVLLM)
        router = _vllm_router()
        entry = router._usable_providers()[0]

        first = router._adapter_for(entry, 60.0)
        second = router._adapter_for(entry, 60.0)

        assert first is second
        assert len(built) == 1


class TestLiteLLMAdapter:
    def test_keyed_adapter_passes_kwargs_and_records_usage(self):
        seen: dict[str, object] = {}

        def completion(**kwargs):
            seen.update(kwargs)
            return {
                "choices": [{"message": {"content": "adapter-ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }

        adapter = LiteLLMProvider(
            model="gemini/gemini-3.6-flash",
            api_key="k",
            timeout=30.0,
            provider_name="gemini",
            completion=completion,
        )
        messages = [{"role": "user", "content": "hi"}]
        text = asyncio.run(adapter.generate(messages, temperature=0.7, max_tokens=11))

        assert text == "adapter-ok"
        assert seen["model"] == "gemini/gemini-3.6-flash"
        assert seen["api_key"] == "k"
        assert "api_base" not in seen
        assert seen["temperature"] == 0.7
        assert seen["max_tokens"] == 11
        assert seen["timeout"] == 30.0
        assert adapter.last_metrics is not None
        assert adapter.last_metrics.provider == "gemini"
        assert adapter.last_metrics.input_tokens == 5
        assert adapter.last_metrics.output_tokens == 3

    def test_local_entry_includes_api_base_and_placeholder_key(self):
        seen: dict[str, object] = {}

        def completion(**kwargs):
            seen.update(kwargs)
            return {"choices": [{"message": {"content": "local-ok"}}]}

        adapter = LiteLLMProvider(
            model="ollama/x",
            api_base="http://localhost:11434",
            completion=completion,
        )
        asyncio.run(adapter.generate([{"role": "user", "content": "hi"}]))

        assert seen["api_base"] == "http://localhost:11434"
        assert seen["api_key"] == "ollama"


def test_vllm_construction_failure_falls_back_to_litellm_seam(monkeypatch):
    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("vLLM support requires: pip install '.[vllm]'")

    monkeypatch.setattr(lr, "VLLMProvider", _Boom)

    class _SeamRouter(LLMRouter):
        def __init__(self):
            super().__init__(LLMConfig(retries=RetrySettings(attempts=0, backoff_seconds=0)))
            self.calls: list[dict] = []

        def _litellm_completion(self):
            return self

        def completion(self, **kwargs):
            self.calls.append(kwargs)
            return {"choices": [{"message": {"content": "fallback"}}]}

    router = _SeamRouter()
    router.config.chain = [
        ChainProvider(
            provider="vllm",
            model="openai/Qwen/Qwen3-8B",
            api_base="http://localhost:8000/v1",
        )
    ]
    resp = router.complete("hi")

    assert resp.text == "fallback"
    # LiteLLM strips the routing prefix itself, so the fallback keeps it.
    assert router.calls[0]["model"] == "openai/Qwen/Qwen3-8B"
    assert router.calls[0]["api_base"] == "http://localhost:8000/v1"


class TestRunProvider:
    def test_runs_from_sync_context(self):
        async def work():
            await asyncio.sleep(0)
            return 42

        assert run_provider(work()) == 42

    def test_runs_from_inside_a_running_event_loop(self):
        async def work():
            await asyncio.sleep(0)
            return "loop-safe"

        async def outer():
            return run_provider(work())

        assert asyncio.run(outer()) == "loop-safe"
