"""Inference layer: decision providers, policy engine, decision agent.

Public surface:
  DecisionProvider      — ABC for any System One style decision engine
  LayaDecisionProvider  — in-process open-weight Laya Router
  HeuristicDecisionProvider — deterministic always-works fallback
  DecisionAgent         — batched decisions + policy + traces
  application_policy    — deterministic decisions->action gate
"""

from hermes.inference.agent import DecisionAgent
from hermes.inference.base import DecisionProvider, ProviderUnavailable
from hermes.inference.heuristic_provider import HeuristicDecisionProvider
from hermes.inference.laya_client import LayaDecisionProvider
from hermes.inference.llm import LLMProvider
from hermes.inference.vllm_client import VLLMProvider
from hermes.inference.context import ContextPackage, build_context
from hermes.inference.router import ModelCandidate, RoutingWeights, choose_model, order_candidates, utility
from hermes.inference.reliability import CircuitBreaker, CircuitOpen, call_with_retry
from hermes.inference.metrics import DECISION_METRICS, RuntimeMetrics
from hermes.inference.verification import ClaimReference, extract_claims, verify_claims
from hermes.inference.metrics_store import MetricsStore
from hermes.inference.failures import FailureCode, classify_failure
from hermes.inference.policies import (
    APPLICATION_POLICY_VERSION,
    DEFAULT_THRESHOLDS,
    GENERATE,
    PolicyOutcome,
    PolicyThresholds,
    REVIEW,
    SKIP,
    application_policy,
)
from hermes.inference.schemas import (
    DecisionAnswer,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    DecisionTrace,
    state_hash,
)

__all__ = [
    "DecisionProvider",
    "ProviderUnavailable",
    "LayaDecisionProvider",
    "HeuristicDecisionProvider",
    "DecisionAgent",
    "application_policy",
    "PolicyOutcome",
    "PolicyThresholds",
    "DEFAULT_THRESHOLDS",
    "APPLICATION_POLICY_VERSION",
    "GENERATE",
    "REVIEW",
    "SKIP",
    "LLMProvider",
    "VLLMProvider",
    "ContextPackage",
    "build_context",
    "ModelCandidate",
    "RoutingWeights",
    "choose_model",
    "order_candidates",
    "utility",
    "CircuitBreaker",
    "CircuitOpen",
    "call_with_retry",
    "RuntimeMetrics",
    "DECISION_METRICS",
    "ClaimReference",
    "extract_claims",
    "verify_claims",
    "MetricsStore",
    "FailureCode",
    "classify_failure",
    "DecisionQuestion",
    "DecisionRequest",
    "DecisionResult",
    "DecisionAnswer",
    "DecisionTrace",
    "state_hash",
]
