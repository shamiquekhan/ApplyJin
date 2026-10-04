"""Measured model profiles used by the generation router."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from applyjin.inference.router import ModelCandidate


class ModelRegistry:
    """Small JSON-backed registry; unmeasured models keep conservative defaults."""

    def __init__(self, profiles: dict[str, dict[str, Any]] | None = None) -> None:
        self.profiles = profiles or {}

    @classmethod
    def from_environment(cls) -> "ModelRegistry":
        path = os.getenv("APPLYJIN_MODEL_REGISTRY", "config/model_registry.json")
        registry_path = Path(path)
        if not registry_path.exists():
            return cls()
        return cls(json.loads(registry_path.read_text(encoding="utf-8")))

    def profile(self, model: str) -> dict[str, Any]:
        profile = self.profiles.get(model)
        if profile is None and model.startswith("openai/"):
            # Chain entries carry the LiteLLM routing prefix; registry keys
            # use the served model id (config/model_registry.example.json).
            profile = self.profiles.get(model.removeprefix("openai/"))
        return dict(profile or {})

    def candidate(self, model: str, *, provider: str = "", task: str = "") -> ModelCandidate:
        measured = self.profile(model)
        default_quality = 0.90 if task == "resume_generation" and provider == "vllm" else 0.80
        return ModelCandidate(
            name=model,
            quality=float(measured.get("quality", default_quality)),
            latency_ms=float(measured.get("p95_latency_ms", 100.0 if provider == "vllm" else 250.0)),
            resource_cost=float(measured.get("resource_cost", 1.0)),
            failure_probability=float(measured.get("failure_rate", 0.10)),
            max_context=int(measured.get("max_context_tokens", 8192)),
        )

    def update(self, model: str, metrics: dict[str, Any]) -> None:
        self.profiles[model] = {**self.profiles.get(model, {}), **metrics}

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.profiles, indent=2, sort_keys=True) + "\n", encoding="utf-8")