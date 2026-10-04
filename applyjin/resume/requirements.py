"""JD requirement schema, normalization, and importance weighting.

A requirement is a competency the job demands — richer than a keyword.
"Python" is a surface form; "Build production ML pipelines in Python" is a
requirement with evidence behind it. Normalization maps surface forms and
aliases onto one concept ("retrieval-augmented generation" -> "rag") so
coverage math compares like with like.

Importance is a configurable product of explicitness, repetition, and
responsibility alignment — starting values only; learn them from outcomes.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

RequirementCategory = Literal[
    "TECHNICAL_SKILL",
    "TOOL",
    "FRAMEWORK",
    "DOMAIN",
    "RESPONSIBILITY",
    "EXPERIENCE",
    "EDUCATION",
    "CERTIFICATION",
    "SOFT_SKILL",
    "TITLE",
]

# Surface forms that denote the same concept.
_SKILL_ALIASES = {
    "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag",
    "large language model": "llm",
    "large language models": "llm",
    "llms": "llm",
    "artificial intelligence": "ai",
    "machine learning": "ml",
    "ci/cd": "cicd",
    "continuous integration": "cicd",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "tf": "tensorflow",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "node": "nodejs",
    "node.js": "nodejs",
    "react.js": "react",
    "reactjs": "react",
    "next.js": "nextjs",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "amazon web services": "aws",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
}


# Leading phrasing wrappers stripped before concept matching.
_WRAPPER_PHRASES = [
    "must have", "must-have", "required to have", "good to have",
    "nice to have", "strong experience with", "proven experience with",
    "hands-on experience with", "hands on experience with",
    "experience with", "experience in", "experience building",
    "experience designing", "experience developing", "familiarity with",
    "working knowledge of", "knowledge of", "exposure to",
    "understanding of", "proficiency in", "expertise in",
    "background in", "preferably", "preferred", "required",
    "essential", "strong", "bonus", "must",
]

# Words that may surround a concept inside wrapper phrasing (the substring
# branch returns the alias concept only when everything else is a wrapper).
_WRAPPER_WORDS = {
    w
    for phrase in _WRAPPER_PHRASES
    for w in phrase.split()
} | {
    "with", "in", "of", "to", "for", "and", "or", "a", "an", "the",
    "experience", "knowledge", "understanding", "exposure", "proficiency",
    "expertise", "familiarity", "background", "working", "level",
}

# Generic trailing nouns that never change the concept.
_GENERIC_NOUNS = {
    "systems", "system", "skills", "skill", "technologies", "technology",
    "tools", "tool", "tooling", "pipelines", "pipeline", "platform",
    "platforms", "development", "programming", "stack", "domain",
    "experience", "knowledge", "background", "expertise",
}


def _cleanup(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = re.sub(r"\s+", " ", value).strip(" .:,;()[]{}")
    return value


def _strip_wrappers(value: str) -> str:
    changed = True
    while changed:
        changed = False
        for phrase in _WRAPPER_PHRASES:
            if value.startswith(phrase + " "):
                value = value[len(phrase):].lstrip()
                changed = True
    return value


def _strip_generic_nouns(value: str) -> str:
    words = value.split()
    while words and words[-1] in _GENERIC_NOUNS:
        words.pop()
    return " ".join(words)


def normalize_skill(text: str) -> str:
    """Canonical concept id for a skill/requirement surface form.

    Handles exact aliases ("LLMs" -> "llm"), requirement phrasing
    ("Experience with retrieval-augmented generation" -> "rag"), and
    case/punctuation cleanup ("PyTorch" -> "pytorch").
    """
    value = _cleanup(text)
    if not value:
        return ""
    if value in _SKILL_ALIASES:
        return _SKILL_ALIASES[value]
    # An alias concept embedded in wrapper phrasing: the remainder must be
    # entirely wrapper words (guards against substrings like "rag" in
    # "storage").
    for key, canonical in _SKILL_ALIASES.items():
        if re.search(r"(?<![\w#])" + re.escape(key) + r"(?![\w-])", value):
            remainder_words = [
                w.strip(".,;():")
                for w in value.replace(key, " ").split()
            ]
            if all(not w or w in _WRAPPER_WORDS for w in remainder_words):
                return canonical
    stripped = _strip_wrappers(value)
    if stripped in _SKILL_ALIASES:
        return _SKILL_ALIASES[stripped]
    trimmed = _strip_wrappers(_strip_generic_nouns(stripped))
    if trimmed in _SKILL_ALIASES:
        return _SKILL_ALIASES[trimmed]
    return trimmed or stripped


class Requirement(BaseModel):
    """One thing the job demands, with provenance and weight."""

    id: str
    text: str
    normalized: str = ""
    category: RequirementCategory = "TECHNICAL_SKILL"
    importance: float = 0.5
    mandatory: bool = False
    aliases: list[str] = Field(default_factory=list)
    evidence_required: bool = False


class ImportanceWeights(BaseModel):
    """Configurable scoring model for requirement importance."""

    mandatory: float = 1.0
    preferred: float = 0.95
    familiar: float = 0.65
    knowledge: float = 0.55
    default_tier: float = 0.70
    soft_skill_cap: float = 0.25
    repetition_gain: float = 0.10
    max_extra_repetitions: int = 3
    responsibility_alignment: float = 0.10


_MUST_HAVE = re.compile(r"\b(must[- ]have|required|essential|non-negotiable)\b", re.I)
_EXPERIENCE = re.compile(r"\b(experience with|hands[- ]on|proven|expertise in|strong)\b", re.I)
_FAMILIAR = re.compile(r"\b(familiar\w*)\b", re.I)
_KNOWLEDGE = re.compile(r"\b(knowledge of|exposure to|understanding of|good to have|nice to have|bonus)\b", re.I)


def _explicitness_tier(text: str, weights: ImportanceWeights) -> float:
    if _MUST_HAVE.search(text):
        return weights.mandatory
    if _EXPERIENCE.search(text):
        return weights.preferred
    if _FAMILIAR.search(text):
        return weights.familiar
    if _KNOWLEDGE.search(text):
        return weights.knowledge
    return weights.default_tier


def compute_importance(
    requirement: Requirement,
    *,
    repetitions: int = 1,
    in_responsibilities: bool = False,
    weights: Optional[ImportanceWeights] = None,
) -> float:
    """importance = explicitness x repetition x responsibility alignment,
    capped at 1.0. Soft skills are capped much lower — they never drive
    evidence selection."""
    w = weights or ImportanceWeights()
    tier = _explicitness_tier(requirement.text, w)
    if requirement.category == "SOFT_SKILL":
        tier = min(tier, w.soft_skill_cap)
    extra = min(max(repetitions - 1, 0), w.max_extra_repetitions)
    repetition = 1 + w.repetition_gain * extra
    alignment = 1 + (w.responsibility_alignment if in_responsibilities else 0)
    value = tier * repetition * alignment
    if requirement.mandatory:
        value = max(value, w.mandatory)
    return round(min(1.0, value), 3)


def make_requirement(
    text: str,
    *,
    id: str = "",
    category: RequirementCategory = "TECHNICAL_SKILL",
    mandatory: bool = False,
    aliases: Optional[list[str]] = None,
    evidence_required: Optional[bool] = None,
    repetitions: int = 1,
    in_responsibilities: bool = False,
    weights: Optional[ImportanceWeights] = None,
    importance: Optional[float] = None,
) -> Requirement:
    """Build a Requirement with normalized forms and computed importance."""
    normalized = normalize_skill(text)
    slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")[:24] or "req"
    digest = hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:6]
    requirement = Requirement(
        id=id or f"req_{slug}_{digest}",
        text=text.strip(),
        normalized=normalized,
        category=category,
        mandatory=mandatory,
        aliases=[normalize_skill(a) for a in aliases or []],
        evidence_required=mandatory if evidence_required is None else evidence_required,
    )
    requirement.importance = (
        importance
        if importance is not None
        else compute_importance(
            requirement,
            repetitions=repetitions,
            in_responsibilities=in_responsibilities,
            weights=weights,
        )
    )
    return requirement
