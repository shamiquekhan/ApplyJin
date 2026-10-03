from __future__ import annotations

import asyncio

import pytest

from hermes.inference.context import build_context, estimate_tokens
from hermes.inference.reliability import CircuitBreaker, CircuitOpen, call_with_retry
from hermes.inference.router import ModelCandidate, RoutingWeights, order_candidates, utility
from hermes.inference.model_registry import ModelRegistry


def test_context_is_bounded_and_delimited():
    package = build_context("job " * 20, ["Python evidence", "second evidence", "third evidence"], "Use verified evidence only.", {"job": 10, "candidate_evidence": 18, "instructions": 8})
    assert estimate_tokens(package.job) <= 10
    assert package.retrieved_chunks == 3
    assert package.discarded_chunks == 0
    assert "<UNTRUSTED_JOB_DESCRIPTION>" in package.as_prompt()
    assert "<VERIFIED_CANDIDATE_EVIDENCE>" in package.as_prompt()
    assert package.input_tokens > 0
    assert estimate_tokens("Python APIs") >= 2


def test_context_budgets_are_token_units_end_to_end():
    package = build_context(
        job="word " * 200,
        evidence=["evidence " * 100, "second " * 100, "third " * 10],
        instructions="keep " * 100,
        budgets={"job": 40, "candidate_evidence": 60, "instructions": 20, "output": 30},
    )
    # every section respects its token budget
    assert estimate_tokens(package.job) <= 40
    assert sum(estimate_tokens(item) for item in package.candidate_evidence) <= 60
    assert estimate_tokens(package.instructions) <= 20
    # reported totals are in the same unit as the budgets
    assert package.budget_tokens == 40 + 60 + 20
    assert package.input_tokens <= package.budget_tokens
    assert package.context_utilization <= 1.0
    assert package.metadata["input_tokens"] == package.input_tokens
    # evidence that does not fit is counted as discarded, not silently kept
    assert package.retrieved_chunks == 3
    assert package.discarded_chunks == 2


def test_retry_then_success_resets_breaker():
    attempts = 0
    breaker = CircuitBreaker(failure_threshold=2)

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert asyncio.run(call_with_retry(operation, attempts=2, backoff_seconds=0, breaker=breaker)) == "ok"
    assert attempts == 2
    assert breaker.failures == 0


def test_breaker_opens_after_failures():
    breaker = CircuitBreaker(failure_threshold=1)

    async def operation():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        asyncio.run(call_with_retry(operation, attempts=1, breaker=breaker))
    with pytest.raises(CircuitOpen):
        asyncio.run(call_with_retry(operation, attempts=1, breaker=breaker))


def test_generation_candidates_are_ordered_by_configured_utility():
    candidates = [
        ModelCandidate("slow", quality=0.95, latency_ms=500, resource_cost=2, failure_probability=0.1),
        ModelCandidate("fast", quality=0.85, latency_ms=50, resource_cost=1, failure_probability=0.05),
    ]
    ordered = order_candidates(candidates, weights=RoutingWeights(quality=1, latency=0.5, resource=0.1, failure=0.5))
    assert [candidate.name for candidate in ordered] == ["fast", "slow"]
    assert utility(candidates[0], RoutingWeights()) > -1.0


def test_model_registry_prefers_measured_profile_values():
    registry = ModelRegistry({"local": {"quality": 0.99, "p95_latency_ms": 20, "failure_rate": 0.01}})
    candidate = registry.candidate("local", provider="vllm", task="resume_generation")
    assert candidate.quality == 0.99
    assert candidate.latency_ms == 20


def test_model_registry_matches_chain_entries_with_routing_prefix():
    registry = ModelRegistry({
        "Qwen/Qwen2.5-0.5B-Instruct": {"quality": 0.7, "max_context_tokens": 2048}
    })
    # chain entries are written as openai/<served-model>; profile lookup must
    # still find the measured entry.
    candidate = registry.candidate("openai/Qwen/Qwen2.5-0.5B-Instruct")
    assert candidate.quality == 0.7
    assert candidate.max_context == 2048