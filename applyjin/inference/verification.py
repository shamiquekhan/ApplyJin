"""Claim extraction and evidence matching for generated documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]{2,}", re.IGNORECASE)
_STOPWORDS = {
    "about", "after", "been", "built", "from", "have", "into", "this",
    "using", "with", "your", "the", "and", "for", "that", "were",
}
# Metrics: %, currency, Nx multipliers, and bare quantities ("2 million").
# Standalone 4-digit years are excluded here — they belong to _DATE_RE.
_METRIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?|\b\d+x\b|\b\d+(?:\.\d+)?[KMB]\b"
    r"|(?<![\d,.])\d{1,3}(?:,\d{3})*(?:\.\d+)?(?!\d)(?!(?:19|20)\d{2})",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_CERTIFICATION_RE = re.compile(r"\b(certified|certification|certificate|badge)\b", re.IGNORECASE)
_EDUCATION_RE = re.compile(r"\b(bachelor|master|phd|doctorate|university|college|degree)\b", re.IGNORECASE)
_SKILL_RE = re.compile(r"\b(skills?|technologies|proficient|expertise)\b", re.IGNORECASE)
_COMPANY_RE = re.compile(r"\b(?:[Aa]t|@)\s+(?:(?:a|an|the)\s+)?([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})")
_TITLE_RE = re.compile(r"\b(?:[Ww]orked as|[Ss]erved as|[Rr]ole as|[Tt]itle was)\s+(?:(?:a|an|the)\s+)?([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,3})")
_LABEL_RE = re.compile(r"^(?:skills?|technologies|tools|certifications?|certificates|education)\s*:", re.IGNORECASE)
# Mid-sentence capitalized tokens — proper nouns that must trace to evidence.
_PROPER_RE = re.compile(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b")
# Generic connectives that legitimately appear in skill lines but are not
# themselves skills — excluded from the skill-token traceability check.
_SKILL_GENERIC = {
    "skills", "skill", "technologies", "technology", "tools", "tooling",
    "expertise", "proficient", "proficiency", "skilled", "experienced",
    "stack", "stacks", "frameworks", "framework", "libraries", "library",
    "platforms", "platform", "including", "such", "strong", "hands",
    "production", "plus", "familiar", "known", "used", "working",
    "experience", "knowledge", "level", "levels", "years", "across",
}


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


def _contains_boundary(haystack: str, needle: str) -> bool:
    """Whole-token containment: '40%' must not pass against evidence '140%'."""
    start = 0
    needle_lower = needle.lower()
    while True:
        index = haystack.lower().find(needle_lower, start)
        if index < 0:
            return False
        before = haystack[index - 1] if index > 0 else ""
        after_index = index + len(needle_lower)
        after = haystack[after_index] if after_index < len(haystack) else ""
        if not (before.isalnum() or after.isalnum()):
            return True
        start = index + 1


def _entity_provenance_ok(claim: str, evidence: str) -> bool:
    """Every company/title the claim names must appear verbatim in evidence."""
    for matcher in (_COMPANY_RE, _TITLE_RE):
        for name in matcher.findall(claim):
            if not _contains_boundary(evidence, name):
                return False
    return True


def _proper_nouns_traceable(
    claim: str, evidence: str, known_values: list[str]
) -> bool:
    """Mid-sentence proper nouns (Stanford, Google, NASA…) must trace to
    evidence or a known entity — catches entity swaps the at-X/title
    patterns miss."""
    for match in _PROPER_RE.finditer(claim):
        index = match.start()
        if index == 0:
            continue  # sentence-initial word is capitalised by convention
        previous = claim[index - 1]
        if previous in ".!?" or (
            previous == " " and index >= 2 and claim[index - 2] in ".!?"
        ):
            continue  # start of a new sentence
        token = match.group(0)
        if _contains_boundary(evidence, token):
            continue
        if any(token.lower() in known.lower() for known in known_values):
            continue
        return False
    return True


def _skill_tokens_traceable(
    claim: str, evidence: str, known_skills: list[str]
) -> bool:
    """Every content token of a SKILL claim must trace to a known candidate
    skill or appear verbatim in the evidence — blocks injected skills."""
    haystack = evidence.lower()
    known_lower = [skill.lower() for skill in known_skills]
    for token in _WORD_RE.findall(claim):
        word = token.lower()
        if len(word) < 3 or word in _STOPWORDS or word in _SKILL_GENERIC:
            continue
        if any(word in known for known in known_lower):
            continue
        if _contains_boundary(haystack, word):
            continue
        return False
    return True


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
        # Content-driven provenance: any number, date, company or title that
        # appears in the claim must appear verbatim in the evidence — even
        # when the claim's dominant type is something else (e.g. a year
        # inside a METRIC claim would otherwise skip the DATE check).
        if supported and _METRIC_RE.search(claim):
            supported = all(
                _contains_boundary(best[1], metric)
                for metric in _METRIC_RE.findall(claim)
            )
        if supported and _DATE_RE.search(claim):
            supported = all(
                _contains_boundary(best[1], date) for date in _DATE_RE.findall(claim)
            )
        if supported and (_COMPANY_RE.search(claim) or _TITLE_RE.search(claim)):
            supported = _entity_provenance_ok(claim, best[1])
        if supported:
            known_values = [
                value
                for values in (known_entities or {}).values()
                for value in values
            ]
            supported = _proper_nouns_traceable(claim, best[1], known_values)
        if supported and claim_type == "SKILL":
            supported = _skill_tokens_traceable(
                claim, best[1], (known_entities or {}).get("SKILL", [])
            )
        entities = [entity.lower() for entity in (known_entities or {}).get(claim_type, [])]
        if supported and entities:
            supported = any(
                entity in claim.lower() and _contains_boundary(best[1], entity)
                for entity in entities
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