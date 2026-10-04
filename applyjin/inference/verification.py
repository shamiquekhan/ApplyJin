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
_CERTIFICATION_RE = re.compile(r"\b(certified|certification|certificate|badge)\b", re.IGNORECASE)
_EDUCATION_RE = re.compile(r"\b(bachelor|master|phd|doctorate|university|college|degree)\b", re.IGNORECASE)
_SKILL_RE = re.compile(r"\b(skills?|technologies|proficient|expertise)\b", re.IGNORECASE)
_COMPANY_RE = re.compile(r"\b(?:at|@)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})")
_TITLE_RE = re.compile(r"\b(?:worked as|served as|role as|title was)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3})")
_LABEL_RE = re.compile(r"^(?:skills?|technologies|tools|certifications?|certificates|education)\s*:", re.IGNORECASE)


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
        if candidate.startswith("#"):
            continue
        # Short labelled lines ("Skills: Python and Rust") are typed claims too.
        if len(candidate.split()) < 8 and not (
            _LABEL_RE.match(candidate) and len(candidate.split()) >= 2
        ):
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
    if _CERTIFICATION_RE.search(claim):
        return "CERTIFICATION"
    if _EDUCATION_RE.search(claim):
        return "EDUCATION"
    if _SKILL_RE.search(claim):
        return "SKILL"
    if _COMPANY_RE.search(claim):
        return "COMPANY"
    if _TITLE_RE.search(claim):
        return "TITLE"
    return "GENERAL"


def verify_claims(
    text: str,
    evidence: list[tuple[str, str]],
    known_entities: dict[str, list[str]] | None = None,
) -> list[ClaimReference]:
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
        entities = [entity.lower() for entity in (known_entities or {}).get(claim_type, [])]
        if supported and entities:
            supported = any(entity in claim.lower() and entity in best[1].lower() for entity in entities)
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