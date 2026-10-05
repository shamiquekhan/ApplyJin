"""Claim-level adversarial grounding evaluator.

Feeds each dataset case through the production verifier (`verify_claims`)
and scores the gate verdict — ALLOW vs BLOCK — against the expected label.
Aggregates into the two headline safety numbers:

- escape rate: adversarial claims the verifier let through (false negatives)
- false-reject rate: honest claims the verifier blocked (false positives)
"""

from __future__ import annotations

from applyjin.inference.verification import verify_claims

ALLOW = "ALLOW"
BLOCK = "BLOCK"


def claim_verdict(case: dict) -> str:
    """Run one claim through the production verifier; BLOCK if unsupported."""
    evidence = [(str(identifier), str(source)) for identifier, source in case.get("evidence", [])]
    references = verify_claims(
        str(case.get("claim", "")),
        evidence,
        case.get("known_entities"),
    )
    if not references:
        return BLOCK  # nothing verifiable — fail closed
    return ALLOW if all(reference.supported for reference in references) else BLOCK


def evaluate_claim_case(case: dict) -> dict:
    expected = str(case.get("expected", BLOCK)).upper()
    actual = claim_verdict(case)
    return {
        "id": str(case.get("id", "")),
        "type": "claim",
        "category": str(case.get("category", "unknown")),
        "expected": expected,
        "actual": actual,
        "score": 1.0 if actual == expected else 0.0,
    }


def aggregate_claim_results(results: list[dict]) -> dict:
    """Escape rate (adversarial slips) and false-reject rate (honest blocked)."""
    blocked_cases = [r for r in results if r["expected"] == BLOCK]
    allowed_cases = [r for r in results if r["expected"] == ALLOW]
    escapes = [r for r in blocked_cases if r["actual"] == ALLOW]
    false_rejects = [r for r in allowed_cases if r["actual"] == BLOCK]
    by_category: dict[str, dict] = {}
    for result in results:
        bucket = by_category.setdefault(
            result["category"], {"cases": 0, "detected": 0}
        )
        bucket["cases"] += 1
        bucket["detected"] += 1 if result["score"] == 1.0 else 0
    for bucket in by_category.values():
        bucket["detection_rate"] = round(bucket["detected"] / bucket["cases"], 4)
    return {
        "cases": len(results),
        "adversarial_cases": len(blocked_cases),
        "honest_cases": len(allowed_cases),
        "escapes": len(escapes),
        "escape_ids": [r["id"] for r in escapes],
        "escape_rate": round(len(escapes) / len(blocked_cases), 4) if blocked_cases else 0.0,
        "false_rejects": len(false_rejects),
        "false_reject_ids": [r["id"] for r in false_rejects],
        "false_reject_rate": round(len(false_rejects) / len(allowed_cases), 4) if allowed_cases else 0.0,
        "by_category": by_category,
    }
