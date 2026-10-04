"""Exact skill matching for scoring — fixes the ratio bugs.

Old bugs:
  - substring matching: required skill "R" matched "React"; "C" matched
    "CI/CD" — inflated scores
  - missed multi-word phrases: "machine learning" never matched when the
    resume only had the skill listed as a profile tag, and vice versa

skill_match: word-boundary, case-insensitive, plural/inflection tolerant,
handles '/', '+' and '.'-joined compounds (CI/CD, Node.js, C++).
"""

from __future__ import annotations

import re

_SPECIALS = {"c++", "c#", "node.js", "ci/cd", "r&d", "nlp", "llm", "rag", "gpt-4", "next.js"}


def _patterns_for(skill: str) -> list[re.Pattern]:
    lowered = skill.strip().lower()
    if not lowered:
        return []
    escaped = re.escape(lowered)
    # Plural tolerance: "pipeline(s)", "system(s)" — allow an optional s
    escaped_plural = escaped + r"s?"
    # Optional space before '+', '#', '.' variants (e.g. "node js" == node.js)
    escaped_loose = re.sub(r"\\[+.#]", r"[ .]?", escaped)
    patterns = [
        re.compile(rf"(?<![\w/+-]){escaped}(?![\w/+-])"),        # exact
        re.compile(rf"(?<![\w/+-]){escaped_plural}(?![\w/+-])"), # plural
    ]
    if escaped_loose != escaped:
        patterns.append(
            re.compile(rf"(?<![\w/+-]){escaped_loose}s?(?![\w/+-])")
        )
    return patterns


def skill_in_text(skill: str, text: str) -> bool:
    """True if the skill appears in text as a whole term.

    Plural tolerance works in BOTH directions: a plural skill matches a
    singular text mention and vice versa ("systems" == "system").
    """
    if not skill or not text:
        return False
    lowered = text.lower()
    skill_l = skill.strip().lower()
    if skill_l in _SPECIALS:
        return re.search(
            rf"(?<![\w/+-]){re.escape(skill_l)}(?![\w/+-])",
            lowered,
        ) is not None
    for pattern in _patterns_for(skill_l):
        if pattern.search(lowered):
            return True
    # reverse plural: strip a trailing 's' from the skill and retry
    if skill_l.endswith("s") and len(skill_l) > 3:
        singular = skill_l[:-1]
        return any(p.search(lowered) for p in _patterns_for(singular))
    return False


def skill_coverage(skills: list[str], text: str) -> tuple[float, list[str], list[str]]:
    """(coverage fraction, matched, missing) of skills in a text."""
    if not skills:
        return 1.0, [], []
    matched = [s for s in skills if skill_in_text(s, text)]
    missing = [s for s in skills if s not in matched]
    return (len(matched) / len(skills), matched, missing)


def skills_in_text(text: str, known_skills: list[str]) -> list[str]:
    """Which of the known skills appear in the text (word-boundary)."""
    return [s for s in known_skills if skill_in_text(s, text)]
