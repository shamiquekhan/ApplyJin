"""LiteLLM-based router with a provider failover chain.

Tries each configured provider in order (e.g. Gemini -> OpenRouter -> Ollama)
until one succeeds. Providers with no API key are skipped. When the entire
chain is empty or fails, `LLMUnavailable` is raised and agents fall back to
deterministic heuristic mode so the pipeline never hard-crashes.

Rate limiting: free tiers cap requests per minute (e.g. Gemini 3.6 Flash =
20 RPM). The router spaces calls by a configurable min interval per provider
and honors API "Please retry in Ns" hints on 429s.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from typing import Any, Optional

from applyjin.config import LLMConfig, RetrySettings
from applyjin.models import LLMResponse
from applyjin.inference.llm import run_provider
from applyjin.inference.litellm_client import LiteLLMProvider
from applyjin.inference.router import RoutingWeights, order_candidates
from applyjin.inference.model_registry import ModelRegistry
from applyjin.inference.vllm_client import VLLMProvider

logger = logging.getLogger("applyjin.llm")

# Conservative default spacing between calls to the same provider (seconds).
# Gemini free tier: 20 RPM -> 3.5s floor keeps us at ~17 calls/min.
_DEFAULT_MIN_INTERVAL = 3.5
# Max total minutes the router will spend waiting on one complete() call
# before giving up and letting the failover/heuristic fallback kick in.
_MAX_TOTAL_WAIT_SECONDS = 240
_RETRY_HINT_RE = re.compile(r"Please retry in ([\d.]+)s", re.IGNORECASE)


class LLMUnavailable(RuntimeError):
    """Raised when every provider in the chain fails or none is configured."""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    """Best-effort JSON extraction: fenced block, then first {...} span."""
    fenced = _JSON_FENCE_RE.search(text)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    candidates.append(text.strip())
    for cand in candidates:
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            continue
    return None


class LLMRouter:
    """Routes completion + JSON calls through a failover chain via LiteLLM."""

    def __init__(self, config: Optional[LLMConfig] = None, registry: Optional[ModelRegistry] = None) -> None:
        self.config = config or LLMConfig()
        self.registry = registry or ModelRegistry.from_environment()
        self._litellm = None
        self._last_call: dict[str, datetime] = {}   # provider -> last call time
        self._min_interval = _DEFAULT_MIN_INTERVAL
        self._adapters: dict[tuple, Any] = {}
        self._adapter_lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self._usable_providers())

    def _throttle(self, provider_model: str) -> None:
        """Space calls per provider to stay under free-tier RPM limits."""
        last = self._last_call.get(provider_model)
        if last is not None:
            elapsed = (datetime.utcnow() - last).total_seconds()
            wait = self._min_interval - elapsed
            if wait > 0:
                logger.debug("Throttling %s for %.1fs", provider_model, wait)
                time.sleep(wait)
        self._last_call[provider_model] = datetime.utcnow()

    def _usable_providers(self) -> list[dict[str, str]]:
        usable = []
        for entry in self.config.chain:
            if entry.provider == "ollama" and entry.model:
                usable.append(
                    {
                        "provider": "ollama",
                        "model": entry.model,
                        "api_base": entry.api_base or "http://localhost:11434",
                        "api_key": entry.api_key or "ollama",
                    }
                )
            elif entry.provider == "vllm" and entry.model:
                # vLLM serves an OpenAI-compatible API locally; no real key
                # needed (any non-empty string satisfies the client).
                usable.append(
                    {
                        "provider": "vllm",
                        "model": entry.model,
                        "api_base": entry.api_base or "http://localhost:8001/v1",
                        "api_key": entry.api_key or "local",
                    }
                )
            elif entry.model and entry.api_key:
                usable.append({"provider": entry.provider, "model": entry.model, "api_key": entry.api_key})
            else:
                logger.debug("Skipping %s (missing key or model)", entry.provider)
        return usable

    def _rotate(self, providers: list[dict[str, str]], current_model: str) -> list[dict[str, str]]:
        """Sibling models with the same key — the rotation pool.

        Gemini free-tier quota is per model, so when one model is hot its
        siblings usually still have headroom. Providers sharing an api_key
        are considered a rotation pool.
        """
        current_key = next(
            (p["api_key"] for p in providers if p["model"] == current_model), None
        )
        if current_key is None:
            return []
        return [
            p for p in providers
            if p["model"] != current_model
            and p.get("api_key") == current_key
            and "api_base" not in p
        ]

    def _litellm_completion(self):
        if self._litellm is None:
            import litellm  # deferred: heavy import

            litellm.suppress_debug_info = True  # hide "Give Feedback" banners
            import logging

            # Gemini 3.x emits harmless sampling-param deprecation warnings.
            logging.getLogger("LiteLLM").setLevel(logging.ERROR)
            self._litellm = litellm
        return self._litellm

    def _litellm_adapter(self, provider: dict[str, str], timeout_seconds: float) -> LiteLLMProvider:
        return LiteLLMProvider(
            model=provider["model"],
            api_key=provider.get("api_key", ""),
            api_base=provider.get("api_base"),
            timeout=timeout_seconds,
            provider_name=provider.get("provider", "litellm"),
            completion=lambda **kwargs: self._litellm_completion().completion(**kwargs),
        )

    def _adapter_for(self, provider: dict[str, str], timeout_seconds: float) -> Any:
        """Canonical ``LLMProvider`` for one chain entry, cached per entry."""
        key = (
            provider.get("provider", ""),
            provider.get("model", ""),
            provider.get("api_key", ""),
            provider.get("api_base"),
            timeout_seconds,
        )
        with self._adapter_lock:
            adapter = self._adapters.get(key)
            if adapter is not None:
                return adapter
            if provider.get("provider") == "vllm":
                adapter = self._vllm_adapter(provider, timeout_seconds)
            else:
                adapter = self._litellm_adapter(provider, timeout_seconds)
            self._adapters[key] = adapter
            return adapter

    def _vllm_adapter(self, provider: dict[str, str], timeout_seconds: float) -> Any:
        try:
            return VLLMProvider(
                base_url=provider.get("api_base"),
                # vLLM expects the bare model name; LiteLLM strips the
                # ``openai/`` routing prefix itself, the OpenAI client does not.
                model=provider["model"].removeprefix("openai/"),
                api_key=provider.get("api_key") or "local",
                timeout=timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 — missing optional deps etc.
            logger.debug(
                "vLLM provider unavailable for %s (%s) — falling back to LiteLLM",
                provider["model"], exc,
            )
            return self._litellm_adapter(provider, timeout_seconds)

    def complete(
        self,
        prompt: str,
        system: str = "",
        task: str = "generation",
        context_length: int = 0,
    ) -> LLMResponse:
        providers = self._usable_providers()
        if not providers:
            raise LLMUnavailable(
                "No LLM provider configured. Add a key to config/llm_config.yml "
                "or set GEMINI_API_KEY / OPENROUTER_API_KEY / etc."
            )

        gen = self.config.generation
        retries = self.config.retries
        last_error: Exception | None = None
        waited_total = 0.0

        # Choose the preferred model by explicit utility, then retain the
        # existing provider queue as the reliability fallback path.
        candidates = [
            self.registry.candidate(
                provider["model"], provider=provider.get("provider", ""), task=task
            )
            for provider in providers
        ]
        preferred = order_candidates(
            candidates,
            context_length=context_length,
            weights=RoutingWeights.from_environment(),
        )
        by_model = {provider["model"]: provider for provider in providers}
        providers = [by_model[candidate.name] for candidate in preferred]
        if not providers:
            raise LLMUnavailable(
                f"No configured provider supports {context_length} context tokens for task {task}"
            )

        # Rotation queue: on 429, same-key sibling models move to the front
        # (per-model quota means siblings usually still have headroom).
        queue: list[dict[str, str]] = list(providers)
        tried_models: set[str] = set()

        while queue:
            provider = queue[0]
            model = provider["model"]
            tried_models.add(model)
            attempt = 0
            rate_limit_waits = 0
            moved_on = False

            while attempt <= retries.attempts:
                if waited_total > _MAX_TOTAL_WAIT_SECONDS:
                    logger.warning(
                        "Router exceeded %.0fs total wait — failing over "
                        "(quota window too hot)", _MAX_TOTAL_WAIT_SECONDS,
                    )
                    queue.clear()
                    break
                try:
                    self._throttle(model)
                    messages = (
                        [{"role": "system", "content": system}] if system else []
                    ) + [{"role": "user", "content": prompt}]
                    adapter = self._adapter_for(provider, gen.timeout_seconds)
                    text = run_provider(
                        adapter.generate(
                            messages,
                            temperature=gen.temperature,
                            max_tokens=gen.max_tokens,
                        )
                    )
                    return LLMResponse(
                        text=text,
                        model=model,
                        provider=model.split("/")[0],
                    )
                except Exception as exc:  # noqa: BLE001 — provider errors vary
                    last_error = exc
                    message = str(exc)
                    # Connection-refused: provider simply down — next model.
                    if "Connection" in message or "refused" in message:
                        logger.debug(
                            "Provider %s unreachable, skipping: %s", model, exc
                        )
                        break
                    rate_limited = (
                        "429" in message
                        or "RateLimit" in type(exc).__name__
                        or "RESOURCE_EXHAUSTED" in message
                    )
                    if rate_limited:
                        # Rotate: same-key siblings first, then wait.
                        siblings = [
                            p for p in queue[1:] + queue[:1]
                            if p["model"] != model
                            and p.get("api_key") == provider.get("api_key")
                            and "api_base" not in p
                        ]
                        if siblings:
                            logger.warning(
                                "Provider %s rate-limited — rotating to %s",
                                model, siblings[0]["model"],
                            )
                            # move the hot model to the back of the queue
                            queue.append(queue.pop(0))
                            moved_on = True
                            break
                        if rate_limit_waits < 6:
                            rate_limit_waits += 1
                            hint = _RETRY_HINT_RE.search(message)
                            wait = (
                                float(hint.group(1)) + 1.0
                                if hint
                                else float(retries.backoff_seconds)
                            )
                            wait = min(wait, 90.0)
                            waited_total += wait
                            logger.warning(
                                "Provider %s rate-limited — waiting %.1fs then retrying",
                                model, wait,
                            )
                            time.sleep(wait)
                            continue
                    logger.warning(
                        "Provider %s attempt %d failed: %s",
                        model, attempt + 1, exc,
                    )
                    attempt += 1
                    if attempt <= retries.attempts:
                        time.sleep(retries.backoff_seconds)
                        waited_total += retries.backoff_seconds

            if moved_on or not queue:
                continue
            queue.pop(0)

        raise LLMUnavailable(f"All providers failed. Last error: {last_error}")

    def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        """Completion constrained to return a JSON object."""
        json_system = (
            (system + " " if system else "")
            + "Respond with ONLY a valid JSON object. No prose, no markdown fences."
        )
        response = self.complete(prompt, system=json_system)
        parsed = _extract_json(response.text)
        if parsed is None:
            raise LLMUnavailable(
                f"Provider {response.model} returned unparseable JSON: "
                f"{response.text[:200]}"
            )
        return parsed


def make_router(retries: Optional[RetrySettings] = None) -> LLMRouter:
    from applyjin.config import load_dotenv, load_llm_config

    load_dotenv()
    cfg = load_llm_config()
    if retries:
        cfg.retries = retries
    return LLMRouter(cfg)
