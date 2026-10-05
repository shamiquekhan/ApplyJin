"""Evaluator registry: case type -> evaluator function.

Each evaluator takes a golden case plus a system callable and returns
per-case results that the runner aggregates into metrics.
"""

from __future__ import annotations

from evaluation.evaluators.correctness import evaluate_classification, evaluate_gating
from evaluation.evaluators.grounding import evaluate_grounding
from evaluation.evaluators.retrieval import evaluate_retrieval
from evaluation.evaluators.safety import evaluate_adversarial
from evaluation.evaluators.performance import percentile as percentile  # re-export
from evaluation.evaluators.trajectory import evaluate_trajectory

EVALUATORS = {
    "classification": evaluate_classification,
    "gating": evaluate_gating,
    "grounding": evaluate_grounding,
    "retrieval": evaluate_retrieval,
    "adversarial": evaluate_adversarial,
    "trajectory": evaluate_trajectory,
}
