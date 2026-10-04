"""Requirement extraction from a job description.

LLM-first: the model reads the full JD and returns structured requirements
(category, explicitness, aliases). Deterministic fallback derives
requirements from the cached keyword buckets so tailoring never blocks on
the extractor.

Explicitness maps to the plan's importance tiers:
    must_have 1.0 | experience 0.95 | familiarity 0.65 | knowledge 0.55
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from hermes.resume.requirements import (
    Requirement,
    RequirementCategory,
    make_requirement,
)
from hermes.utils.llm_router import LLMRouter, LLMUnavailable

logger = logging.getLogger("hermes.resume.extract")

_CATEGORIES: tuple[RequirementCategory, ...] = (
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
)

_EXPLICITNESS_TIERS = {
    "must_have": 1.0,
    "must-have": 1.0,
    "required": 1.0,
    "experience": 0.95,
    "familiarity": 0.65,
    "knowledge": 0.55,
}

# Fallback phrasing per keyword bucket: the tier comes from the phrasing,
# so each bucket lands on a defensible default importance.
_BUCKET_PHRASE = {
    "hard_skills": ("Experience with {}", "TECHNICAL_SKILL"),
    "tools": ("Experience with {}", "TOOL"),
    "domain_keywords": ("Knowledge of {}", "DOMAIN"),
    "soft_skills": ("{}", "SOFT_SKILL"),
    "certifications": ("Familiarity with {}", "CERTIFICATION"),
}

_SYSTEM = """Extract every job requirement from the job description.
Return JSON only:
{"requirements": [{"text": "<short natural phrasing>", "category":
"<one of: TECHNICAL_SKILL, TOOL, FRAMEWORK, DOMAIN, RESPONSIBILITY,
EXPERIENCE, EDUCATION, CERTIFICATION, SOFT_SKILL, TITLE>",
"explicitness": "<must_have | experience | familiarity | knowledge>",
"mandatory": <true|false>, "aliases": ["<alternate surface form>"]}]}
Rules: 8-25 requirements, most important first. "text" must be a short
requirement phrase (e.g. "Experience with FastAPI", "Own the retrieval
pipeline end to end"), not a full sentence. Use must_have only for
explicit requirements ("must have", "required")."""


def _count_occurrences(jd_text: str, term: str) -> int:
    if not jd_text or not term:
        return 1
    pattern = rf"(?<!\w){re.escape(term.strip().lower())}(?!\w)"
    return max(1, len(re.findall(pattern, jd_text.lower())))


def requirements_from_keywords(keywords: dict, jd_text: str = "") -> list[Requirement]:
    """Deterministic requirements derived from cached keyword buckets."""
    requirements: list[Requirement] = []
    seen: set[str] = set()
    for bucket, (phrase, category) in _BUCKET_PHRASE.items():
        for term in keywords.get(bucket) or []:
            term = str(term).strip()
            if not term or term.lower() in seen:
                continue
            seen.add(term.lower())
            requirements.append(
                make_requirement(
                    phrase.format(term),
                    category=category,  # type: ignore[arg-type]
                    repetitions=_count_occurrences(jd_text, term),
                )
            )
    requirements.sort(key=lambda r: r.importance, reverse=True)
    return requirements


def _parse_llm_requirements(raw: object, jd_text: str) -> list[Requirement]:
    if isinstance(raw, dict):
        items = raw.get("requirements", raw.get("items", []))
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(f"unexpected requirement payload: {type(raw).__name__}")
    if not isinstance(items, list) or not items:
        raise ValueError("empty requirements payload")

    requirements: list[Requirement] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        category = str(item.get("category", "")).strip().upper()
        if category not in _CATEGORIES:
            category = "TECHNICAL_SKILL"
        explicitness = str(item.get("explicitness", "")).strip().lower()
        tier = _EXPLICITNESS_TIERS.get(explicitness)
        mandatory = bool(item.get("mandatory")) or tier == 1.0
        if tier is None:
            tier = 1.0 if mandatory else 0.70
        aliases = [
            str(a).strip()
            for a in (item.get("aliases") or [])
            if str(a).strip()
        ]
        if category == "SOFT_SKILL":
            tier = min(tier, 0.25)  # soft skills never drive evidence selection
        requirements.append(
            make_requirement(
                text,
                category=category,  # type: ignore[arg-type]
                mandatory=mandatory,
                aliases=aliases,
                importance=min(1.0, tier * _repetition_factor(jd_text, text)),
            )
        )
    if not requirements:
        raise ValueError("no parseable requirements")
    requirements.sort(key=lambda r: r.importance, reverse=True)
    return requirements


def _repetition_factor(jd_text: str, text: str) -> float:
    """Repetition boost from the requirement's core term in the JD."""
    core = text.split()[-1].strip(".,;:()").lower() if text.split() else ""
    if len(core) < 3:
        return 1.0
    count = len(
        re.findall(rf"(?<!\w){re.escape(core)}(?!\w)", jd_text.lower())
    )
    return 1 + 0.10 * min(max(count - 1, 0), 3)


def extract_requirements(
    jd_text: str,
    keywords: dict,
    router: Optional[LLMRouter] = None,
) -> tuple[list[Requirement], str]:
    """(requirements, source) — LLM first, keyword fallback. Never raises."""
    if router is not None:
        try:
            raw = router.complete_json(
                system=_SYSTEM,
                prompt=f"Job description:\n{jd_text[:6000]}",
            )
            return _parse_llm_requirements(raw, jd_text), "llm"
        except (LLMUnavailable, ValueError, TypeError) as exc:
            logger.info("requirement extraction fallback (%s)", exc)
    return requirements_from_keywords(keywords, jd_text), "keywords"
