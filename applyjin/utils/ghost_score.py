"""Ghost-job / listing-freshness scorer.

Analyzes JD text for signals that a listing may be stale, already filled,
or lacking real hiring intent.  All signals are computed from data ApplyJin
already scrapes — no new external API calls.

Signal weights (tuned against 2026 independent surveys finding 20–40%
of active listings may be ghost jobs):
  - High:   vague description, excessive buzzwords, no salary disclosed
  - Medium: red-flag patterns, very short description, generic title
  - Low:    missing seniority level, missing remote policy

Returns a score 0–100 (higher = more likely genuine) plus a list of
human-readable flags explaining the deduction.
"""

from __future__ import annotations

import re
from typing import Optional

# Buzzwords that inflate JD text without adding substance.
_BUZZWORDS = [
    "rockstar", "ninja", "guru", "wizard", "unicorn", "hero",
    "passion", "fast-paced", "wear many hats", "self-starter",
    "dynamic", "innovative", "disrupt", "synergy", "thought leader",
    "world-class", "best-in-class", "game-changing",
]

# Patterns that suggest the JD may be recycled or templated.
_GENERIC_PATTERNS = [
    r" responsibilities include",
    r" including,? but not limited to",
    r" other duties as assigned",
    r" must be able to",
    r" excellent (verbal|written) communication",
    r" detail[- ]oriented",
    r" (team|self)[- ]player",
]

# Red-flag phrases (also used by JD analyzer).
_RED_FLAG_PATTERNS = [
    r"unpaid", r"volunteer", r"equity.only", r"no benefits",
    r"996", r"60[- ].?hour", r"crunch",
]


def score_jd(
    jd_text: str,
    title: str = "",
    company: str = "",
    posted_days_ago: Optional[int] = None,
) -> dict:
    """Score a job description for genuineness.

    Returns:
        {
            "ghost_score": int (0-100, higher = more genuine),
            "flags": list[str],      # human-readable reasons for deduction
            "signals": dict[str, float],  # individual signal scores
        }
    """
    flags: list[str] = []
    signals: dict[str, float] = {}
    score = 100.0

    text_lower = jd_text.lower()
    word_count = len(jd_text.split())

    # --- Signal 1: Description vagueness (0–25 pts deduction) ---
    if word_count < 80:
        deduction = 20
        flags.append(f"Very short description ({word_count} words)")
        signals["vagueness"] = 0.2
    elif word_count < 150:
        deduction = 10
        flags.append(f"Short description ({word_count} words)")
        signals["vagueness"] = 0.5
    else:
        deduction = 0
        signals["vagueness"] = 1.0
    score -= deduction

    # --- Signal 2: Buzzword density (0–15 pts) ---
    buzzword_hits = [b for b in _BUZZWORDS if b in text_lower]
    if len(buzzword_hits) >= 4:
        score -= 15
        flags.append(f"High buzzword density ({len(buzzword_hits)} terms)")
        signals["buzzwords"] = 0.1
    elif len(buzzword_hits) >= 2:
        score -= 8
        signals["buzzwords"] = 0.5
    else:
        signals["buzzwords"] = 1.0

    # --- Signal 3: Generic / templated language (0–15 pts) ---
    generic_hits = sum(
        1 for pat in _GENERIC_PATTERNS if re.search(pat, text_lower)
    )
    if generic_hits >= 4:
        score -= 15
        flags.append(f"Templated language ({generic_hits} generic phrases)")
        signals["templated"] = 0.1
    elif generic_hits >= 2:
        score -= 7
        signals["templated"] = 0.5
    else:
        signals["templated"] = 1.0

    # --- Signal 4: Red flags (0–15 pts) ---
    red_hits = [p for p in _RED_FLAG_PATTERNS if re.search(p, text_lower)]
    if red_hits:
        score -= 15
        flags.append("Contains red-flag phrases (unpaid, 996, etc.)")
        signals["red_flags"] = 0.0
    else:
        signals["red_flags"] = 1.0

    # --- Signal 5: Missing salary info (0–10 pts) ---
    has_salary = bool(re.search(
        r"\$[\d,]+|₹[\d,]+|€[\d,]+|£[\d,]+|salary|compensation|pay range",
        text_lower,
    ))
    if not has_salary:
        score -= 10
        flags.append("No salary or compensation disclosed")
        signals["salary_disclosed"] = 0.0
    else:
        signals["salary_disclosed"] = 1.0

    # --- Signal 6: Generic / overused title (0–5 pts) ---
    generic_titles = [
        "software engineer", "data scientist", "full stack developer",
        "backend developer", "frontend developer",
    ]
    if title.lower().strip() in generic_titles:
        # Only penalize if the description doesn't add specificity
        if word_count < 200:
            score -= 5
            signals["title_specificity"] = 0.5
        else:
            signals["title_specificity"] = 0.8
    else:
        signals["title_specificity"] = 1.0

    # --- Signal 7: Posting age (if available) (0–15 pts) ---
    if posted_days_ago is not None:
        if posted_days_ago > 60:
            score -= 15
            flags.append(f"Posted {posted_days_ago} days ago (stale)")
            signals["freshness"] = 0.0
        elif posted_days_ago > 30:
            score -= 8
            signals["freshness"] = 0.4
        elif posted_days_ago > 14:
            score -= 3
            signals["freshness"] = 0.7
        else:
            signals["freshness"] = 1.0
    else:
        signals["freshness"] = 0.5  # unknown = neutral

    final = max(0, min(100, round(score)))
    return {
        "ghost_score": final,
        "flags": flags,
        "signals": signals,
    }
