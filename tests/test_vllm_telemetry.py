import asyncio
from types import SimpleNamespace

from applyjin.inference.vllm_client import VLLMProvider


class _Completions:
    async def create(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=1),
        )


class _Client:
    chat = SimpleNamespace(completions=_Completions())


def test_vllm_generation_records_usage_telemetry():
    provider = VLLMProvider(model="local", client=_Client())
    assert asyncio.run(provider.generate([{"role": "user", "content": "hi"}])) == "hello"
    assert provider.last_metrics is not None
    assert provider.last_metrics.input_tokens == 3
    assert provider.last_metrics.output_tokens == 1