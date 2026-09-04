"""Fit Scorer: how well does the base profile match this job?

Weighted combination (hermes_guide.md § 6.3):
  0.35 keyword overlap + 0.35 semantic similarity
  + 0.15 seniority alignment + 0.15 experience threshold
Jobs below the configurable threshold are rejected with a reason.
"""

from __future__ import annotations

import logging

from hermes.config import Profile
from hermes.models import JobAnalysis, JobPosting, ResumeDocument, ScoredJob
from hermes.utils.ats_scorer import (
    keyword_match_score,
    matched_keywords,
    missing_keywords,
    seniority_match,
    semantic_similarity,
)
from hermes.utils.ats_scorer import experience_match as _experience_match
from hermes.utils.skill_match import skill_coverage, skills_in_text

logger = logging.getLogger("hermes.fit_scorer")


class FitScorer:
    def __init__(self, profile: Profile, min_fit_score: float = 0.65) -> None:
        self.profile = profile
        self.min_fit_score = min_fit_score

    def score(
        self,
        job: JobPosting,
        analysis: JobAnalysis,
        resume: ResumeDocument,
    ) -> ScoredJob:
        # Keyword coverage: skill tags + full resume text, word-boundary
        # matched (fixes 'R' substring-matching 'React' and missed
        # multi-word skills).
        corpus = ", ".join(resume.skills) + " " + resume.raw_text
        kw_score, kw_matched, kw_missing = skill_coverage(
            analysis.required_skills, corpus
        )
        keyword_score = kw_score
        semantic_score = max(
            0.0,
            semantic_similarity(resume.summary or resume.raw_text[:2000],
                                job.description[:2000]),
        )
        seniority_score = seniority_match(resume.seniority, analysis.seniority_level)
        exp_score = _experience_match(
            resume.years_experience, analysis.years_experience
        )

        final = (
            0.35 * keyword_score
            + 0.35 * semantic_score
            + 0.15 * seniority_score
            + 0.15 * exp_score
        )

        breakdown = {
            "keyword": round(keyword_score, 3),
            "semantic": round(semantic_score, 3),
            "seniority": round(seniority_score, 3),
            "experience": round(exp_score, 3),
            "matched": kw_matched,
            "missing": kw_missing,
        }

        passed = final >= self.min_fit_score
        if not passed:
            breakdown["reject_reason"] = _reject_reason(breakdown, final, self.min_fit_score)

        return ScoredJob(
            job=job,
            analysis=analysis,
            fit_score=round(final, 3),
            score_breakdown=breakdown,
            passed_filter=passed,
            reject_reason=breakdown.get("reject_reason", ""),
        )


def _reject_reason(breakdown: dict, score: float, threshold: float) -> str:
    missing = breakdown.get("missing") or []
    if missing:
        return f"fit {score:.3f} < {threshold}; missing: {', '.join(missing[:5])}"
    return f"fit {score:.3f} < {threshold}"
