"""Fuzzy job deduplication: same role posted on multiple boards.

Keys on (company, title) with RapidFuzz token-set ratio — robust to
"Senior Backend Engineer" vs "Sr. Backend Engineer (Remote)" variants.
"""

from __future__ import annotations

import logging

from hermes.models import JobPosting

logger = logging.getLogger("hermes.dedup")


def _canon(text: str) -> str:
    import re

    lowered = text.lower()
    lowered = re.sub(r"\(.*?\)", "", lowered)  # drop parentheticals
    return re.sub(r"[^a-z0-9 ]", "", lowered).strip()


try:
    from rapidfuzz import fuzz

    def _similarity(a: str, b: str) -> float:
        return fuzz.token_set_ratio(_canon(a), _canon(b)) / 100.0

except ImportError:  # pragma: no cover — rapidfuzz is a hard dependency

    def _similarity(a: str, b: str) -> float:  # type: ignore[misc]
        return 1.0 if _canon(a) == _canon(b) else 0.0


def deduplicate_jobs(
    jobs: list[JobPosting], threshold: float = 0.85
) -> list[JobPosting]:
    """Keep the first-seen posting of each fuzzy (company, title) pair."""
    seen: list[tuple[str, str]] = []  # (canonical title, canonical company)
    kept: list[JobPosting] = []
    dropped = 0
    for job in jobs:
        company = _canon(job.company)
        title = _canon(job.title)
        duplicate = False
        for prev_title, prev_company in seen:
            if _similarity(company, prev_company) < threshold:
                continue
            if _similarity(title, prev_title) >= threshold:
                duplicate = True
                break
        if duplicate:
            dropped += 1
            continue
        seen.append((title, company))
        kept.append(job)
    if dropped:
        logger.info("Deduplicated %d/%d postings", dropped, len(jobs))
    return kept
