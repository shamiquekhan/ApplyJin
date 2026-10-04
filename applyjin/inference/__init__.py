"""Inference layer: decision providers, policy engine, decision agent.

Public surface:
  DecisionProvider      — ABC for any System One style decision engine
  LayaDecisionProvider  — in-process open-weight Laya Router
  HeuristicDecisionProvider — deterministic always-works fallback
  DecisionAgent         — batched decisions + policy + traces
  application_policy    — deterministic decisions->action gate
"""

from applyjin.inference.agent import DecisionAgent
from applyjin.inference.base import DecisionProvider, ProviderUnavailable
from applyjin.inference.heuristic_provider import HeuristicDecisionProvider
from applyjin.inference.laya_client import LayaDecisionProvider
from applyjin.inference.llm import LLMProvider, run_provider
from applyjin.inference.vllm_client import VLLMProvider
from applyjin.inference.context import ContextPackage, build_context, estimate_tokens
from applyjin.inference.tokens import ApproximateTokenCounter, TokenCounter, counter_for_model
from applyjin.inference.router import ModelCandidate, RoutingWeights, choose_model, order_candidates, utility
from applyjin.inference.reliability import CircuitBreaker, CircuitOpen, call_with_retry
from applyjin.inference.metrics import DECISION_METRICS, INFERENCE_METRICS, GenerationObservation, RuntimeMetrics
from applyjin.inference.verification import ClaimReference, classify_claim, extract_claims, verify_claims
from applyjin.inference.metrics_store import MetricsStore
from applyjin.inference.failures import FailureCode, classify_failure
from applyjin.inference.model_registry import ModelRegistry
from applyjin.inference.litellm_client import LiteLLMProvider, RouterProvider
from applyjin.inference.policies import (
    APPLICATION_POLICY_VERSION,
    DEFAULT_THRESHOLDS,
    GENERATE,
    PolicyOutcome,
    PolicyThresholds,
    REVIEW,
    SKIP,
    application_policy,
    confidence_from_answers,
    outcome_from_result,
)
from applyjin.inference.schemas import (
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
    "confidence_from_answers",
    "outcome_from_result",
    "PolicyOutcome",
    "PolicyThresholds",
    "DEFAULT_THRESHOLDS",
    "APPLICATION_POLICY_VERSION",
    "GENERATE",
    "REVIEW",
    "SKIP",
    "LLMProvider",
    "run_provider",
    "VLLMProvider",
    "ContextPackage",
    "build_context",
    "estimate_tokens",
    "TokenCounter",
    "ApproximateTokenCounter",
    "counter_for_model",
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
    "INFERENCE_METRICS",
    "GenerationObservation",
    "ClaimReference",
    "extract_claims",
    "classify_claim",
    "verify_claims",
    "MetricsStore",
    "FailureCode",
    "classify_failure",
    "ModelRegistry",
    "LiteLLMProvider",
    "RouterProvider",
    "DecisionQuestion",
    "DecisionRequest",
    "DecisionResult",
    "DecisionAnswer",
    "DecisionTrace",
    "state_hash",
]
