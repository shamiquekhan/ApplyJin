"""Claim extraction and evidence matching for generated documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]{2,}", re.IGNORECASE)
_STOPWORDS = {
    "about", "after", "been", "built", "from", "have", "into", "this",
    "using", "with", "your", "the", "and", "for", "that", "were",
}


@dataclass(frozen=True)
class ClaimReference:
    claim: str
    evidence_id: str = ""
    evidence: str = ""
    supported: bool = False


def extract_claims(text: str) -> list[str]:
    """Extract substantive bullet/sentence claims, excluding headings."""
    claims: list[str] = []
    for line in text.splitlines():
        candidate = line.strip().lstrip("-*").strip()
        if candidate.startswith("#") or len(candidate.split()) < 8:
            continue
        if candidate not in claims:
            claims.append(candidate)
    return claims


def _terms(text: str) -> set[str]:
    return {word.lower() for word in _WORD_RE.findall(text) if word.lower() not in _STOPWORDS}


def verify_claims(text: str, evidence: list[tuple[str, str]]) -> list[ClaimReference]:
    """Match each extracted claim to the strongest verified evidence chunk."""
    evidence_terms = [(identifier, source, _terms(source)) for identifier, source in evidence]
    references: list[ClaimReference] = []
    for claim in extract_claims(text):
        terms = _terms(claim)
        best: tuple[str, str, float] | None = None
        for identifier, source, source_terms in evidence_terms:
            overlap = len(terms & source_terms) / len(terms) if terms else 0.0
            if best is None or overlap > best[2]:
                best = (identifier, source, overlap)
        supported = best is not None and best[2] >= 0.35
        references.append(
            ClaimReference(
                claim=claim,
                evidence_id=best[0] if supported and best else "",
                evidence=best[1] if supported and best else "",
                supported=supported,
            )
        )
    return references