"""Deterministic policy engine: decisions in, actions out.

The decision model never executes actions. Model outputs are typed
evidence; this module — plain, testable Python — decides what the
application does. Policy versions are explicit so traces can record
exactly which thresholds produced an action.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from hermes.inference.schemas import DecisionResult

logger = logging.getLogger("hermes.inference.policies")

APPLICATION_POLICY_VERSION = "application_policy_v1"

# Action names (stable strings; agents/UI match on these).
GENERATE = "GENERATE"
REVIEW = "REVIEW"
SKIP = "SKIP"


@dataclass
class PolicyThresholds:
    """Configurable gates. Lives in config, not in prompts."""

    # Below this fit score (0..5): not worth generating.
    min_fit_score: float = 3.0
    # Below this P(core requirements met): needs human eyes.
    min_requirement_probability: float = 0.70
    # Above this probability of prompt injection: hard skip.
    max_injection_probability: float = 0.50
    # P(requirements) between these two: REVIEW band.
    review_band_low: float = 0.70
    review_band_high: float = 0.85


DEFAULT_THRESHOLDS = PolicyThresholds()


@dataclass
class PolicyOutcome:
    """What the policy decided and why (for traces and review UI)."""

    action: str
    reasons: list[str] = field(default_factory=list)
    policy_version: str = APPLICATION_POLICY_VERSION


def application_policy(
    technical_fit: float,
    requirement_probability: float,
    injection_probability: float = 0.0,
    thresholds: PolicyThresholds = DEFAULT_THRESHOLDS,
) -> PolicyOutcome:
    """Gate an application decision on typed decision outputs.

    Order matters: injection -> hard skip, fit -> skip, uncertainty
    -> review, else generate.
    """
    outcome = PolicyOutcome(action=GENERATE)
    t = thresholds

    if injection_probability >= t.max_injection_probability:
        outcome.action = SKIP
        outcome.reasons.append(
            f"prompt-injection probability "
            f"{injection_probability:.2f} >= {t.max_injection_probability:.2f}"
        )
        return outcome

    if technical_fit < t.min_fit_score:
        outcome.action = SKIP
        outcome.reasons.append(
            f"technical fit {technical_fit:.1f} < {t.min_fit_score:.1f}"
        )
        return outcome

    if requirement_probability < t.review_band_low:
        outcome.action = REVIEW
        outcome.reasons.append(
            f"requirement probability {requirement_probability:.2f} "
            f"< {t.review_band_low:.2f}"
        )
        return outcome

    if requirement_probability < t.review_band_high:
        outcome.action = REVIEW
        outcome.reasons.append(
            f"requirement probability {requirement_probability:.2f} "
            f"in review band "
            f"[{t.review_band_low:.2f}, {t.review_band_high:.2f})"
        )
        return outcome

    return outcome


def outcome_from_result(
    result: DecisionResult,
    thresholds: PolicyThresholds = DEFAULT_THRESHOLDS,
) -> PolicyOutcome:
    """Convenience: run the policy over a batched DecisionResult.

    Expects questions named: technical_fit (score), meets_core_requirements
    (noul), prompt_injection (noul, optional).
    """
    answers = result.answers

    def _prob(name: str, default: float) -> float:
        ans = answers.get(name)
        if ans is None or ans.probability is None:
            return default
        return float(ans.probability)

    fit = _prob("technical_fit", 0.0) * 5.0
    req = _prob("meets_core_requirements", 0.0)
    inj = _prob("prompt_injection", 0.0)

    return application_policy(fit, req, inj, thresholds)
