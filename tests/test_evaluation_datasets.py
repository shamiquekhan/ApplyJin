"""Regression gates over the labelled decision and security seed datasets.

The floors sit below the currently measured scores (decision 0.846,
security 0.750 against the heuristic baseline) so normal noise passes but a
quality drop fails CI. Improvements should ratchet the floors upward.
"""

from __future__ import annotations

from pathlib import Path

from evaluation.runner import run

DATASETS = Path("evaluation/datasets")


def test_decision_dataset_meets_its_regression_floor():
    report = run(DATASETS / "decision.jsonl")
    assert report["cases"] >= 26
    assert report["correctness"] >= 0.75, report["correctness"]
    assert report["p95_latency_ms"] < 50


def test_security_dataset_meets_its_injection_floor():
    report = run(DATASETS / "security.jsonl")
    assert report["cases"] >= 20
    assert report["safety"] >= 0.65, report["safety"]


def test_seed_datasets_keep_their_ids_unique():
    for name in ("decision.jsonl", "security.jsonl", "regression.jsonl"):
        lines = [
            line for line in (DATASETS / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        ids = [__import__("json").loads(line)["id"] for line in lines]
        assert len(ids) == len(set(ids)), f"duplicate ids in {name}"
