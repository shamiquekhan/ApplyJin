from __future__ import annotations

from evaluation.compare import compare
from evaluation.runner import run


def test_offline_evaluation_dataset_runs():
    report = run(__import__("pathlib").Path("evaluation/datasets/regression.jsonl"))
    assert report["cases"] == 7
    assert report["correctness"] == 1.0


def test_regression_gate_detects_quality_drop():
    result = compare({"correctness": 0.95, "p95_latency_ms": 10}, {"correctness": 0.90, "p95_latency_ms": 10})
    assert not result["passed"]