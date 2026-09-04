"""Learning Agent: analyze tracker outcomes, discover what works, and
generate a style guide that feeds back into the Resume Tailor prompt.

Runs offline (pure statistics over SQLite data) — no LLM required for
the core analysis. The flow (hermes_guide.md § 8.3):

    1. Collect applications with outcomes (>= min_sample_size)
    2. Compute keyword lift: which required skills appear in
       interview-getting applications vs rejected ones
    3. Compute ATS-delta correlation with interview outcomes
    4. Run the A/B test on variants if both arms have samples
    5. Generate a style guide ("winning phrases" report)
    6. Version it in the tracker; `--apply` promotes it into the
       tailor's prompt as the ACTIVE guide
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes.agents.ab_testing import ABResult, analyze_variants
from hermes.agents.tracker import Tracker
from hermes.utils.ats_scorer import missing_keywords

logger = logging.getLogger("hermes.learning")

MIN_SAMPLE_SIZE = 30
INTERVIEW_STATUSES = ("phone_screen", "interview", "offer")
# Every post-submission state is learnable signal — including silence.
_OUTCOME_STATUSES = (
    "submitted", "no_response", "rejected", "phone_screen",
    "interview", "offer", "declined",
)
_RESPONSE_STATUSES = ("rejected", "phone_screen", "interview", "offer", "declined")

_METRIC_RE = re.compile(r"\d+%|\$\d[\d,.]*|\b\d+x\b|\b\d{2,}\b", re.IGNORECASE)


@dataclass
class LearnReport:
    generated_at: datetime = field(default_factory=datetime.utcnow)
    sample_size: int = 0
    interview_count: int = 0
    response_rate: float = 0.0
    interview_rate: float = 0.0
    winning_keywords: list[tuple[str, float]] = field(default_factory=list)
    losing_keywords: list[tuple[str, float]] = field(default_factory=list)
    ats_delta_correlation: Optional[float] = None
    ab_result: Optional[ABResult] = None
    style_guide: str = ""
    sufficient_data: bool = False
    warnings: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"sample_size: {self.sample_size} "
            f"(interviews: {self.interview_count}, "
            f"response_rate: {self.response_rate:.0%}, "
            f"interview_rate: {self.interview_rate:.0%})"
        ]
        if self.ats_delta_correlation is not None:
            lines.append(
                f"ats_delta_correlation: {self.ats_delta_correlation:+.2f} "
                "(does higher ATS tailoring delta track interviews?)"
            )
        if self.winning_keywords:
            top = ", ".join(f"{k} ({l:+.1f})" for k, l in self.winning_keywords[:6])
            lines.append(f"winning_keywords: {top}")
        if self.losing_keywords:
            top = ", ".join(f"{k} ({l:+.1f})" for k, l in self.losing_keywords[:4])
            lines.append(f"losing_keywords: {top}")
        if self.ab_result:
            lines.append(f"ab_test: {self.ab_result.summary()}")
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        return lines


class LearningAgent:
    def __init__(self, tracker: Tracker, min_sample: int = MIN_SAMPLE_SIZE) -> None:
        self.tracker = tracker
        self.min_sample = min_sample

    # ----------------------------------------------------------- analysis

    def analyze(self) -> LearnReport:
        report = LearnReport()
        records = [
            r
            for r in self.tracker.list_applications()
            if r.status in _OUTCOME_STATUSES
        ]
        report.sample_size = len(records)

        if len(records) < self.min_sample:
            report.warnings.append(
                f"only {len(records)} outcome records "
                f"(need {self.min_sample}). Style guide will be marked "
                "insufficient — apply with care or keep collecting."
            )

        interviews = [r for r in records if r.status in INTERVIEW_STATUSES]
        rejected = [r for r in records if r.status == "rejected"]
        report.interview_count = len(interviews)
        if records:
            responses = sum(1 for r in records if r.status in _RESPONSE_STATUSES)
            report.response_rate = responses / len(records)
            report.interview_rate = len(interviews) / len(records)

        # Keyword lift: required skills present in the tailored resume
        # text vs the outcome. Skills whose presence correlates with
        # interviews get promoted into the style guide.
        if interviews and rejected:
            report.winning_keywords, report.losing_keywords = (
                self._keyword_lift(interviews, rejected)
            )

        # ATS delta correlation with interview outcome.
        deltas = [
            (r.ats_score_after - r.ats_score_before)
            for r in records
            if r.ats_score_before is not None and r.ats_score_after is not None
        ]
        outcomes = [
            1.0 if r.status in INTERVIEW_STATUSES else 0.0
            for r in records
            if r.ats_score_before is not None and r.ats_score_after is not None
        ]
        if len(deltas) >= 10:
            report.ats_delta_correlation = _pearson(deltas, outcomes)

        # A/B verdict if both arms have outcomes.
        stats = self.tracker.variant_stats()
        if stats.get("A") and stats.get("B"):
            report.ab_result = analyze_variants(stats)

        report.sufficient_data = (
            len(records) >= self.min_sample
            and report.interview_count >= 3
        )
        report.style_guide = self._style_guide(report)
        return report

    # ------------------------------------------------------- style guide

    def _style_guide(self, report: LearnReport) -> str:
        """Compose the style guide injected into the tailor prompt."""
        sections: list[str] = []

        sections.append(
            "STYLE GUIDE (learned from real application outcomes — "
            "follow where it does not conflict with the ABSOLUTE RULES)"
        )

        if report.sufficient_data and report.winning_keywords:
            top = [k for k, _ in report.winning_keywords[:8]]
            sections.append(
                f"- LEAD with experience in: {', '.join(top)}. These skills "
                "correlated with interview callbacks in past applications."
            )
        if report.winning_keywords:
            sections.append(
                "- Mirror the JD's exact phrasing for these skills when "
                "the base resume supports it — exact keyword matches "
                "scored better than paraphrases."
            )
        if report.losing_keywords:
            dropped = [k for k, _ in report.losing_keywords[:5]]
            sections.append(
                f"- De-emphasize when possible: {', '.join(dropped)} "
                "(correlated with rejection in past applications)."
            )
        if report.ats_delta_correlation is not None:
            corr = report.ats_delta_correlation
            if corr > 0.15:
                sections.append(
                    f"- Aggressive keyword alignment works (ATS-delta "
                    f"correlation {corr:+.2f}): front-load JD keywords."
                )
            elif corr < -0.15:
                sections.append(
                    f"- Over-optimization may hurt (ATS-delta correlation "
                    f"{corr:+.2f}): keep phrasing natural, don't stuff."
                )
        if report.ab_result and report.ab_result.winner != "inconclusive":
            sections.append(
                f"- A/B test result: {report.ab_result.summary()}"
            )

        if not report.sufficient_data:
            sections.append(
                "- NOTE: this guide is based on limited data. Treat as "
                "a hypothesis, not a law."
            )
        return "\n".join(sections)

    # ------------------------------------------------------- persistence

    def apply_style_guide(self, report: LearnReport, source: str = "learning_agent") -> int:
        """Version + activate the new style guide. Returns the version."""
        version, _ = self.tracker.active_style_guide()
        new_version = (version or 0) + 1
        self.tracker.save_style_guide(
            version=new_version,
            style_guide=report.style_guide,
            source=source,
            notes=f"sample={report.sample_size} interviews={report.interview_count}",
        )
        # Persist discovered keyword patterns for the audit trail.
        for keyword, lift in report.winning_keywords[:10]:
            self.tracker.save_pattern("keyword", keyword, lift, report.sample_size)
        return new_version

    # ------------------------------------------------------- helpers

    def _keyword_lift(
        self, interviews: list, rejected: list
    ) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
        """Skills over-represented in interview vs rejected resumes."""
        def skill_counts(records: list) -> dict[str, int]:
            counts: dict[str, int] = {}
            for record in records:
                resume_path = record.tailored_resume_path
                if not resume_path or not Path(resume_path).exists():
                    continue
                text = Path(resume_path).read_text(encoding="utf-8").lower()
                # Count distinct metric mentions as a "pattern" too.
                for skill in _extract_skills(record.notes):
                    if skill.lower() in text:
                        counts[skill] = counts.get(skill, 0) + 1
                for metric in _METRIC_RE.findall(text)[:20]:
                    counts[f"metric:{metric}"] = counts.get(f"metric:{metric}", 0) + 1
            return counts

        win_counts = skill_counts(interviews)
        rej_counts = skill_counts(rejected)
        n_win, n_rej = len(interviews), len(rejected)

        lift: list[tuple[str, float]] = []
        for key, count in win_counts.items():
            win_rate = count / n_win
            rej_rate = rej_counts.get(key, 0) / n_rej
            # Require appearances in >= 20% of winning resumes.
            if count / n_win < 0.2:
                continue
            lift.append((key, round(math.log((win_rate + 0.05) / (rej_rate + 0.05)), 3)))
        lift.sort(key=lambda kv: kv[1], reverse=True)
        winners = [(k, l) for k, l in lift if l > 0.1][:10]
        losers = [(k, l) for k, l in lift if l < -0.1][:6]
        return winners, losers


def _extract_skills(notes: str) -> list[str]:
    """Skills from the tracker notes' 'matched:' list (written by pipeline)."""
    match = re.search(r"matched:\s*([^\|]+)", notes or "")
    if not match:
        return []
    return [s.strip() for s in match.group(1).split(",") if s.strip()]


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)
