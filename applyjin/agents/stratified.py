"""Stratified A/B analysis: compare variants *within* strata.

Aggregate interview-rate differences between variants are confounded:
outcomes depend on job family, seniority, source board, and candidate
fit, and variant assignment is only randomized globally. A variant that
happens to win more high-fit applications can look better overall while
losing inside every stratum (Simpson's paradox). This module slices the
outcomes by observable strata and runs the same Yates-corrected
chi-squared comparison per slice, reporting intervals instead of a bare
winner.

Deterministic and dependency-free: input is any iterable of
ApplicationRecord-like objects carrying `title`, `board`, `fit_score`,
`status`, and `variant`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from applyjin.agents.ab_testing import (
    INTERVIEW_STATUSES,
    OUTCOME_STATUSES,
    ABResult,
    analyze_variants,
)

# Minimum outcomes *per arm* before a stratum's comparison is reported.
MIN_PER_ARM = 10


# ------------------------------------------------------------- strata keys

JOB_FAMILY = "job_family"
SENIORITY = "seniority"
BOARD = "board"
FIT_BUCKET = "fit_bucket"

STRATUM_KEYS = (JOB_FAMILY, SENIORITY, BOARD, FIT_BUCKET)


_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ai_engineering", ("llm", "ai engineer", "ai engineering", "machine learning engineer", "mlops", "nlp", "prompt")),
    ("data_ml", ("data scientist", "data science", "machine learning", "research engineer", "deep learning", "analyst")),
    ("research", ("research scientist", "researcher", "research intern", "phd")),
    ("product", ("product engineer", "product manager", "technical product")),
    ("software", ("software", "backend", "frontend", "full stack", "fullstack", "devops", "platform", "infrastructure", "sre", "mobile", "android", "ios", "engineer")),
)

_SENIORITY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("intern", ("intern", "co-op", "coop")),
    ("entry", ("entry", "graduate", "junior", "jr", "associate", "new grad")),
    ("senior_plus", ("senior", "sr", "staff", "principal", "lead", "manager", "architect", "director")),
)


def _match(title: str, rules: tuple[tuple[str, tuple[str, ...]], ...], default: str) -> str:
    lowered = (title or "").lower()
    for label, keywords in rules:
        for keyword in keywords:
            if keyword in lowered:
                return label
    return default


def _fit_bucket(fit_score: Optional[float]) -> str:
    """high / medium / low on a 0–1 scale (scores >1 are treated as 0–100)."""
    if fit_score is None:
        return "unknown"
    score = fit_score / 100.0 if fit_score > 1.0 else fit_score
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def stratum_values(record) -> dict[str, str]:
    """Observable strata for one application record."""
    return {
        JOB_FAMILY: _match(getattr(record, "title", ""), _FAMILY_RULES, "other"),
        SENIORITY: _match(getattr(record, "title", ""), _SENIORITY_RULES, "mid"),
        BOARD: getattr(record, "board", "") or "unknown",
        FIT_BUCKET: _fit_bucket(getattr(record, "fit_score", None)),
    }


# --------------------------------------------------------------- analysis


@dataclass
class StratumResult:
    """Variant comparison inside one stratum value."""

    stratum: str          # which key, e.g. 'job_family'
    value: str            # which slice, e.g. 'data_ml'
    successes_a: int
    total_a: int
    successes_b: int
    total_b: int
    result: Optional[ABResult] = None   # None until both arms have data
    warnings: list[str] = field(default_factory=list)

    @property
    def rate_a(self) -> float:
        return self.successes_a / self.total_a if self.total_a else 0.0

    @property
    def rate_b(self) -> float:
        return self.successes_b / self.total_b if self.total_b else 0.0

    @property
    def verdict(self) -> str:
        if self.result is None:
            return "insufficient_data"
        return self.result.winner  # 'A' | 'B' | 'inconclusive'

    def line(self) -> str:
        label = f"{self.stratum}={self.value}"
        base = (
            f"{label}: A {self.successes_a}/{self.total_a} ({self.rate_a:.0%}) vs "
            f"B {self.successes_b}/{self.total_b} ({self.rate_b:.0%})"
        )
        if self.result is None:
            return f"{base} — insufficient data per arm (need {MIN_PER_ARM})"
        return f"{base} — {self.result.summary()}"


def _succ_total(records: list, variant: str) -> tuple[int, int]:
    rows = [r for r in records if getattr(r, "variant", "") == variant]
    successes = sum(1 for r in rows if getattr(r, "status", "") in INTERVIEW_STATUSES)
    return successes, len(rows)


def analyze_stratified(
    records: Iterable,
    min_per_arm: int = MIN_PER_ARM,
) -> list[StratumResult]:
    """Compare variants within every stratum slice that has enough data.

    Records must have post-submission statuses to carry signal; draft /
    pending rows are ignored, matching the aggregate learning loop.
    """
    outcome_rows = [
        r for r in records if getattr(r, "status", "") in OUTCOME_STATUSES
    ]

    buckets: dict[tuple[str, str], list] = {}
    for record in outcome_rows:
        for key, value in stratum_values(record).items():
            buckets.setdefault((key, value), []).append(record)

    results: list[StratumResult] = []
    for (key, value), rows in sorted(buckets.items()):
        succ_a, total_a = _succ_total(rows, "A")
        succ_b, total_b = _succ_total(rows, "B")
        entry = StratumResult(
            stratum=key, value=value,
            successes_a=succ_a, total_a=total_a,
            successes_b=succ_b, total_b=total_b,
        )
        if total_a >= min_per_arm and total_b >= min_per_arm:
            stats = {
                "A": dict.fromkeys(OUTCOME_STATUSES, 0),
                "B": dict.fromkeys(OUTCOME_STATUSES, 0),
            }
            for r in rows:
                variant = getattr(r, "variant", "")
                if variant in ("A", "B"):
                    stats[variant][getattr(r, "status", "")] = (
                        stats[variant].get(getattr(r, "status", ""), 0) + 1
                    )
            entry.result = analyze_variants(stats)
        else:
            entry.warnings.append(
                f"arm below {min_per_arm} outcomes — not interpreted"
            )
        results.append(entry)
    return results


def format_stratified_report(results: list[StratumResult]) -> str:
    """Human-readable report; slices with an interpretable verdict first."""
    if not results:
        return "No stratified slices to report (no outcome records)."
    decisive = [r for r in results if r.verdict in ("A", "B")]
    pending = [r for r in results if r.verdict == "inconclusive"]
    starved = [r for r in results if r.verdict == "insufficient_data"]

    lines: list[str] = []
    if decisive:
        lines.append("Stratified verdicts (decisive):")
        lines += [f"  {r.line()}" for r in decisive]
    if pending:
        lines.append("Inconclusive (interval spans zero — keep collecting):")
        lines += [f"  {r.line()}" for r in pending]
    if starved:
        lines.append("Insufficient data (not interpreted):")
        lines += [f"  {r.line()}" for r in starved]
    lines.append(
        "Note: outcomes are observational and heterogeneous; aggregate "
        "differences are not causal evidence. Decisions should weight "
        "strata, not totals."
    )
    return "\n".join(lines)
