from __future__ import annotations

import asyncio

import pytest

from hermes.inference.context import build_context, estimate_tokens
from hermes.inference.reliability import CircuitBreaker, CircuitOpen, call_with_retry
from hermes.inference.router import ModelCandidate, RoutingWeights, order_candidates, utility


def test_context_is_bounded_and_delimited():
    package = build_context("job " * 20, ["Python evidence", "second evidence", "third evidence"], "Use verified evidence only.", {"job": 10, "candidate_evidence": 18, "instructions": 8})
    assert estimate_tokens(package.job) <= 10
    assert package.retrieved_chunks == 3
    assert package.discarded_chunks == 0
    assert "<UNTRUSTED_JOB_DESCRIPTION>" in package.as_prompt()
    assert "<VERIFIED_CANDIDATE_EVIDENCE>" in package.as_prompt()
    assert package.input_tokens > 0
    assert estimate_tokens("Python APIs") >= 2


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