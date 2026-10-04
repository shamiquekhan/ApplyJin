"""Greedy marginal-coverage selection over requirements.

The base ranking (0.7 keyword + 0.3 semantic) picks entries that all match
the same popular keywords, leaving high-importance requirements uncovered.
The optimizer fixes that: repeatedly pick the candidate whose *newly covered*
requirement importance is highest, tie-broken by base relevance. Coverage
always dominates (minimum new weight 0.25 > any relevance-only fill of
0.05), so the selection spans the JD's actual demands while staying
deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable, Optional, Sequence

from hermes.resume.requirements import Requirement
from hermes.utils.skill_match import skill_in_text

# Relevance weight in the greedy gain: a no-coverage candidate can never
# outrank one that adds even the softest requirement (0.25 vs <= 0.05).
RELEVANCE_WEIGHT = 0.05

_STOP_WORDS = {
    "with", "and", "for", "the", "your", "have", "our", "their", "this",
    "that", "from", "will", "who", "are", "plus", "using", "work", "years",
    "year", "able", "must", "should", "into", "across", "within", "about",
    "experience", "knowledge", "familiarity", "understanding", "exposure",
    "strong", "excellent", "good", "great", "excellent", "own", "hands",
    "least", "preferred", "required", "candidate", "role", "team", "teams",
}


@dataclass(frozen=True)
class CoverageItem:
    """One selectable candidate (an experience or project entry)."""

    key: Hashable
    kind: str  # "experience" | "project"
    text: str
    base_score: float = 0.0


def _significant_words(text: str) -> list[str]:
    words = []
    for word in text.lower().split():
        word = word.strip(".,;:()/'\"")
        if len(word) >= 3 and word not in _STOP_WORDS and word.isalpha():
            words.append(word)
    return list(dict.fromkeys(words))


def requirement_matchers(requirement: Requirement) -> tuple[list[str], list[str]]:
    """(exact phrases, fuzzy words) used to test coverage against text."""
    phrases = [p for p in [requirement.normalized, *requirement.aliases] if p]
    words = _significant_words(requirement.text)
    for alias in requirement.aliases:
        words += _significant_words(alias)
    return phrases, list(dict.fromkeys(words))


def requirement_covers(requirement: Requirement, text: str) -> bool:
    """True if the entry text is evidence for this requirement.

    Exact phrase match first (word-boundary, plural tolerant); then a
    fuzzy majority of significant words for phrase-shaped requirements
    ("own the retrieval pipeline" -> "retrieval" + "pipeline").
    """
    if not text:
        return False
    phrases, words = requirement_matchers(requirement)
    if any(skill_in_text(phrase, text) for phrase in phrases):
        return True
    if not words:
        return False
    matched = sum(1 for word in words if skill_in_text(word, text))
    return matched >= max(1, math.ceil(len(words) / 2))


def select_by_marginal_coverage(
    items: Sequence[CoverageItem],
    requirements: Sequence[Requirement],
    budgets: dict[str, int],
    relevance_weight: float = RELEVANCE_WEIGHT,
) -> list[CoverageItem]:
    """Greedy max-coverage with per-kind budgets.

    Picks until every kind's budget is full (or candidates run out).
    Deterministic: gain desc, then base score desc, then kind, then key.
    With no requirements this degrades to per-kind top-by-relevance.
    """
    weight = {r.id: r.importance for r in requirements}
    matches: dict[Hashable, set[str]] = {}
    if requirements:
        for item in items:
            matches[item.key] = {
                r.id for r in requirements if requirement_covers(r, item.text)
            }

    remaining = dict(budgets)
    covered: set[str] = set()
    pool = list(items)
    selected: list[CoverageItem] = []

    while pool:
        if not any(v > 0 for v in remaining.values()):
            break
        eligible = [i for i in pool if remaining.get(i.kind, 0) > 0]
        if not eligible:
            break
        best: Optional[CoverageItem] = None
        best_rank: Optional[tuple] = None
        for item in eligible:
            new_ids = matches.get(item.key, set()) - covered
            gain = sum(weight.get(rid, 0.0) for rid in new_ids)
            gain += relevance_weight * item.base_score
            rank = (-gain, -item.base_score, item.kind, str(item.key))
            if best_rank is None or rank < best_rank:
                best, best_rank = item, rank
        if best is None:
            break
        selected.append(best)
        pool.remove(best)
        remaining[best.kind] = remaining.get(best.kind, 0) - 1
        covered |= matches.get(best.key, set())
    return selected
