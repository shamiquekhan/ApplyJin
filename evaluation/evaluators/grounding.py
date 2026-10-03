"""Evidence-supported claim checks used by the offline harness."""

from __future__ import annotations


def evaluate_grounding(output: str, allowed_evidence: list[str]) -> dict[str, float]:
    if not output.strip():
        return {"groundedness": 1.0}
    evidence = " ".join(allowed_evidence).lower()
    words = {word for word in output.lower().split() if len(word) > 3}
    supported = sum(word in evidence for word in words)
    return {"groundedness": round(supported / len(words), 4) if words else 1.0}
