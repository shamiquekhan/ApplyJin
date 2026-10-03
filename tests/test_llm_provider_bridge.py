import asyncio

from hermes.inference.litellm_client import RouterProvider
from hermes.models import LLMResponse


class _Router:
    def complete(self, prompt, system=""):
        return LLMResponse(text=f"{system}:{prompt}", model="test", provider="test")


def test_router_bridge_implements_async_provider_contract():
    provider = RouterProvider(_Router())
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "prompt"},
    ]
    assert asyncio.run(provider.generate(messages)) == "system:prompt"
