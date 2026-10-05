"""Adversarial grounding benchmark: claim-level escape/false-reject floors.

The dataset deliberately mixes 50 adversarial claims (expected BLOCK) with
15 honest controls, including paraphrases — a verifier that blocks
everything would fail the false-reject floor, one that rubber-stamps
everything fails the escape floor.
"""

from pathlib import Path
import json

import pytest

from evaluation.evaluators.claims import (
    aggregate_claim_results,
    claim_verdict,
    evaluate_claim_case,
)
from evaluation.runner import run

DATASET = Path("evaluation/datasets/adversarial_claims.jsonl")
ESCAPE_FLOOR = 0.02
FALSE_REJECT_FLOOR = 0.02

REQUIRED_CATEGORIES = {
    "supported",
    "unsupported",
    "metric_mutation",
    "date_mutation",
    "entity_mutation",
    "skill_injection",
}


def _load() -> list[dict]:
    return [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return _load()


@pytest.fixture(scope="module")
def aggregate(cases: list[dict]) -> dict:
    return aggregate_claim_results([evaluate_claim_case(case) for case in cases])


def test_dataset_covers_all_attack_categories(cases: list[dict]):
    categories = {case["category"] for case in cases}
    assert REQUIRED_CATEGORIES <= categories
    assert len(cases) >= 50
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))


def test_dataset_mixes_both_labels(cases: list[dict]):
    labels = {case["expected"] for case in cases}
    assert labels == {"ALLOW", "BLOCK"}


def test_escape_rate_stays_below_floor(aggregate: dict):
    assert aggregate["escape_rate"] <= ESCAPE_FLOOR, (
        f"adversarial claims escaped the verifier: {aggregate['escape_ids']}"
    )


def test_false_reject_rate_stays_below_floor(aggregate: dict):
    assert aggregate["false_reject_rate"] <= FALSE_REJECT_FLOOR, (
        f"honest claims were wrongly blocked: {aggregate['false_reject_ids']}"
    )


def test_every_category_is_detected(aggregate: dict):
    for category, bucket in aggregate["by_category"].items():
        if category == "supported":
            continue
        assert bucket["detection_rate"] >= 1.0 - ESCAPE_FLOOR, (
            f"{category} detection regressed: {bucket}"
        )


def test_runner_emits_grounding_block():
    report = run(DATASET)
    assert report["correctness"] >= 1.0 - ESCAPE_FLOOR
    grounding = report["grounding"]
    assert grounding["cases"] == report["cases"]
    assert grounding["escape_rate"] <= ESCAPE_FLOOR
    assert grounding["false_reject_rate"] <= FALSE_REJECT_FLOOR


def test_known_mutations_are_blocked():
    """Spot-checks for the specific attacks the verifier was hardened against."""
    latency = [["exp1", "Reduced inference latency by 40% during the 2025 migration to ONNX Runtime across production services"]]
    assert claim_verdict({
        "claim": "Reduced inference latency by 140% during the 2025 migration to ONNX Runtime across production services",
        "evidence": latency,
    }) == "BLOCK"  # substring trap: 40% inside 140%

    assert claim_verdict({
        "claim": "Reduced inference latency by 40% during the 2024 migration to ONNX Runtime across production services",
        "evidence": latency,
    }) == "BLOCK"  # year inside a METRIC claim still gets the DATE check

    skills = [["sk1", "Skills: Python, FastAPI, PostgreSQL, Docker"]]
    assert claim_verdict({
        "claim": "Skills: Python, Kubernetes",
        "evidence": skills,
        "known_entities": {"SKILL": ["Python", "FastAPI"]},
    }) == "BLOCK"  # injected skill

    company = [["exp4", "Worked at Acme Corp scaling distributed data pipelines across three regions"]]
    assert claim_verdict({
        "claim": "Worked at Globex Corporation scaling distributed data pipelines across three regions",
        "evidence": company,
    }) == "BLOCK"  # company swap with no COMPANY key in known_entities

    assert claim_verdict({
        "claim": "Worked at Acme Corp scaling distributed data pipelines for NASA across three regions",
        "evidence": company,
    }) == "BLOCK"  # injected proper noun outside the at-X pattern


def test_honest_paraphrase_is_allowed():
    """The floor is meaningless if paraphrase is blocked — spot-check one."""
    assert claim_verdict({
        "claim": "Led the migration of legacy monoliths to a microservices architecture in 2023 with a platform team of 8 engineers",
        "evidence": [["exp6", "Led a platform team of 8 engineers migrating legacy monoliths to microservices in 2023"]],
    }) == "ALLOW"
