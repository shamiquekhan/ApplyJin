"""ATS-style keyword matching and semantic fit scoring.

Implements the two-layer score from hermes_guide.md § 6.3/§ 6.4:
keyword overlap (exact + fuzzy) and vector similarity (semantic),
plus seniority and experience alignment.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from hermes.utils.embeddings import cosine_similarity, get_embeddings

_STEM_SUFFIXES = ("s", "es", "ing", "ed", "er", "ers")


def _normalize(skill: str) -> str:
    return skill.strip().lower()


def _stem(token: str) -> str:
    for suffix in _STEM_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _tokenize(skill: str) -> set[str]:
    return {_stem(t) for t in _normalize(skill).replace("-", " ").split()}


def _fuzzy_member(candidate: str, skills: Iterable[str], threshold: float = 0.90) -> bool:
    """Case-insensitive, substring, or near-identical string membership check."""
    cand = _normalize(candidate)
    cand_tokens = _tokenize(candidate)
    for skill in skills:
        other = _normalize(skill)
        if cand == other:
            return True
        # Substring containment either way (e.g. "ci/cd" in "ci/cd pipelines")
        if len(cand) >= 3 and len(other) >= 3 and (cand in other or other in cand):
            return True
        if cand_tokens and cand_tokens == _tokenize(skill):
            return True
        ratio = SequenceMatcher(None, cand, other).ratio()
        if ratio >= threshold:
            return True
    return False


def keyword_match_score(resume_skills: list[str], required_skills: list[str]) -> float:
    """Fraction of required skills present in resume skills (fuzzy)."""
    if not required_skills:
        return 1.0
    matched = sum(
        1 for skill in required_skills if _fuzzy_member(skill, resume_skills)
    )
    return matched / len(required_skills)


def matched_keywords(resume_skills: list[str], required_skills: list[str]) -> list[str]:
    return [s for s in required_skills if _fuzzy_member(s, resume_skills)]


def missing_keywords(resume_skills: list[str], required_skills: list[str]) -> list[str]:
    return [s for s in required_skills if not _fuzzy_member(s, resume_skills)]


_SENIORITY_ORDER = {"junior": 0, "mid": 1, "senior": 2, "staff": 3}


def seniority_match(candidate_level: str, job_level: str) -> float:
    """1.0 when aligned; decays with distance; stretch roles still get credit."""
    cand = _SENIORITY_ORDER.get(candidate_level.lower(), 1)
    job = _SENIORITY_ORDER.get(job_level.lower(), 1)
    distance = abs(cand - job)
    return (1.0, 0.7, 0.4, 0.15)[min(distance, 3)]


def experience_match(years_have: int, years_required: int) -> float:
    if years_required <= 0 or years_have >= years_required:
        return 1.0
    if years_have >= years_required - 1:
        return 0.75  # within one year — usually fine
    return 0.4


def semantic_similarity(text_a: str, text_b: str) -> float:
    emb = get_embeddings()
    return cosine_similarity(emb.embed(text_a), emb.embed(text_b))


class ATSScorer:
    """Computes before/after ATS-style match scores for tailored resumes."""

    def __init__(self) -> None:
        self._emb = get_embeddings()

    def score(self, resume_text: str, required_skills: list[str], jd_text: str) -> float:
        """0-1 score: 60% keyword coverage, 40% semantic similarity."""
        resume_lower = resume_text.lower()
        covered = sum(
            1
            for skill in required_skills
            if _normalize(skill) in resume_lower
            or _fuzzy_member(skill, [resume_lower])
        )
        keyword_component = (
            covered / len(required_skills) if required_skills else 1.0
        )
        semantic_component = cosine_similarity(
            self._emb.embed(resume_text), self._emb.embed(jd_text)
        )
        semantic_component = max(0.0, semantic_component)
        return 0.6 * keyword_component + 0.4 * semantic_component
