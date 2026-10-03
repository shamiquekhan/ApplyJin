"""Claim extraction and evidence matching for generated documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]{2,}", re.IGNORECASE)
_STOPWORDS = {
    "about", "after", "been", "built", "from", "have", "into", "this",
    "using", "with", "your", "the", "and", "for", "that", "were",
}
_METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?|\b\d+x\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}\b")


@dataclass(frozen=True)
class ClaimReference:
    claim: str
    claim_type: str = "GENERAL"
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


def classify_claim(claim: str) -> str:
    if _METRIC_RE.search(claim):
        return "METRIC"
    if _DATE_RE.search(claim):
        return "DATE"
    return "GENERAL"


def verify_claims(text: str, evidence: list[tuple[str, str]]) -> list[ClaimReference]:
    """Match each extracted claim to the strongest verified evidence chunk."""
    evidence_terms = [(identifier, source, _terms(source)) for identifier, source in evidence]
    references: list[ClaimReference] = []
    for claim in extract_claims(text):
        terms = _terms(claim)
        claim_type = classify_claim(claim)
        best: tuple[str, str, float] | None = None
        for identifier, source, source_terms in evidence_terms:
            overlap = len(terms & source_terms) / len(terms) if terms else 0.0
            if best is None or overlap > best[2]:
                best = (identifier, source, overlap)
        supported = best is not None and best[2] >= 0.35
        if supported and claim_type == "METRIC":
            supported = bool(_METRIC_RE.findall(claim)) and all(
                metric in best[1] for metric in _METRIC_RE.findall(claim)
            )
        if supported and claim_type == "DATE":
            supported = bool(_DATE_RE.findall(claim)) and all(
                date in best[1] for date in _DATE_RE.findall(claim)
            )
        references.append(
            ClaimReference(
                claim=claim,
                claim_type=claim_type,
                evidence_id=best[0] if supported and best else "",
                evidence=best[1] if supported and best else "",
                supported=supported,
            )
        )
    return references