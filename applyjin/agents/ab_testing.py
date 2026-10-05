"""A/B testing for resume style variants.

Random 50/50 assignment per application; chi-squared (with Yates
correction for small samples) on interview-rate differences between
variants A and B. Deterministic and dependency-free.

Reporting follows a measure-don't-declare policy: variant rates and the
lift carry Wilson score intervals (95% by default) and a verdict is only
"decisive" when the effect AND its uncertainty both clear the bar — a
winner whose lift interval spans zero is reported as inconclusive, not
promoted.
"""

from __future__ import annotations

import math
import random


# Post-submission statuses that carry learning signal; the ones that
# count as "reached an interview stage" for outcome statistics.
OUTCOME_STATUSES = (
    "submitted", "no_response", "rejected", "phone_screen",
    "interview", "offer", "declined",
)
INTERVIEW_STATUSES = ("phone_screen", "interview", "offer")


def assign_variant(rng: random.Random | None = None) -> str:
    """Fair coin-flip variant assignment ('A' or 'B')."""
    rng = rng or random
    return "A" if rng.random() < 0.5 else "B"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation at small n: the bounds stay
    inside [0, 1] and never produce negative widths for small samples.
    Returns (low, high); (0.0, 1.0) when there is no data.
    """
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    half = (z / denom) * math.sqrt(
        p * (1 - p) / total + z2 / (4 * total * total)
    )
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rates(counts: dict[str, int]) -> tuple[int, int]:
    """(successes, total) where success = any interview-stage outcome."""
    successes = sum(
        counts.get(s, 0) for s in ("phone_screen", "interview", "offer")
    )
    total = sum(counts.values())
    return successes, total


def chi_squared_yates_2x2(a: tuple[int, int], b: tuple[int, int]) -> tuple[float, float]:
    """Chi-squared with Yates continuity correction on a 2x2 table.

    a, b: (successes, total) for each variant.
    Returns (chi2, p) — p from the chi-squared(1df) survival function.
    """
    a_succ, a_total = a
    b_succ, b_total = b
    a_fail, b_fail = a_total - a_succ, b_total - b_succ
    n = a_total + b_total
    if n == 0 or a_total == 0 or b_total == 0:
        return 0.0, 1.0

    row1, row2 = a_succ + b_succ, a_fail + b_fail
    expected = [
        (a_total * row1) / n, (a_total * row2) / n,
        (b_total * row1) / n, (b_total * row2) / n,
    ]
    observed = [a_succ, a_fail, b_succ, b_fail]
    if expected[0] == 0 or expected[1] == 0:
        return 0.0, 1.0

    chi2 = sum(
        (abs(o - e) - 0.5) ** 2 / e
        for o, e in zip(observed, expected)
        if e > 0
    )
    chi2 = max(0.0, chi2)
    return chi2, _chi2_sf_1df(chi2)


def _chi2_sf_1df(x: float) -> float:
    """Survival function of chi-squared with 1 df = erfc(sqrt(x/2))."""
    return math.erfc(math.sqrt(x / 2.0))


class ABResult:
    """Verdict on one A/B comparison."""

    def __init__(
        self,
        variant_a: dict[str, int],
        variant_b: dict[str, int],
        chi2: float,
        p_value: float,
    ) -> None:
        self.counts_a = variant_a
        self.counts_b = variant_b
        self.successes_a, self.total_a = _rates(variant_a)
        self.successes_b, self.total_b = _rates(variant_b)
        self.chi2 = chi2
        self.p_value = p_value

        self.rate_a = self.successes_a / self.total_a if self.total_a else 0.0
        self.rate_b = self.successes_b / self.total_b if self.total_b else 0.0

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    @property
    def lift(self) -> float:
        """Relative interview-rate improvement of B over A."""
        if self.rate_a == 0:
            return 0.0
        return (self.rate_b - self.rate_a) / self.rate_a

    @property
    def lift_pp(self) -> float:
        """Lift in percentage points (B rate − A rate)."""
        return self.rate_b - self.rate_a

    @property
    def ci_a(self) -> tuple[float, float]:
        return wilson_interval(self.successes_a, self.total_a)

    @property
    def ci_b(self) -> tuple[float, float]:
        return wilson_interval(self.successes_b, self.total_b)

    @property
    def lift_ci(self) -> tuple[float, float]:
        """Interval for the lift in percentage points via Newcombe's
        method (interval for the difference of two independent
        proportions from the Wilson intervals)."""
        lo_a, hi_a = self.ci_a
        lo_b, hi_b = self.ci_b
        return (lo_b - hi_a, hi_b - lo_a)

    @property
    def decisive(self) -> bool:
        """True only when the effect AND its uncertainty clear the bar:
        p < 0.05 AND the lift interval excludes zero. An interval that
        spans zero means the data cannot yet distinguish the variants —
        that is 'inconclusive', no matter how small the p-value.
        """
        if not self.significant or self.total_a == 0 or self.total_b == 0:
            return False
        lo, hi = self.lift_ci
        return lo > 0 or hi < 0

    @property
    def winner(self) -> str:
        """'A', 'B', or 'inconclusive' (decisive only)."""
        if not self.decisive:
            return "inconclusive"
        return "A" if self.rate_a > self.rate_b else "B"

    def summary(self) -> str:
        a_ci = self.ci_a
        b_ci = self.ci_b
        lift_ci = self.lift_ci
        header = (
            f"A: {self.successes_a}/{self.total_a} ({self.rate_a:.1%}, "
            f"95% CI {a_ci[0]:.1%}–{a_ci[1]:.1%}) vs "
            f"B: {self.successes_b}/{self.total_b} ({self.rate_b:.1%}, "
            f"95% CI {b_ci[0]:.1%}–{b_ci[1]:.1%})"
        )
        stats_line = (
            f"lift {self.lift_pp:+.1%} (95% CI {lift_ci[0]:+.1%} to {lift_ci[1]:+.1%}), "
            f"chi2={self.chi2:.2f}, p={self.p_value:.3f}"
        )
        if not self.decisive:
            return f"{header} — inconclusive ({stats_line}). Keep collecting outcomes."
        return (
            f"{self.winner} WINS: {header} — {stats_line}. "
            f"Promote {self.winner}'s style guide."
        )


def analyze_variants(stats: dict[str, dict[str, int]]) -> ABResult:
    """Run the A/B comparison from tracker variant_stats()."""
    chi2, p = chi_squared_yates_2x2(
        _rates(stats.get("A", {})), _rates(stats.get("B", {}))
    )
    return ABResult(stats.get("A", {}), stats.get("B", {}), chi2, p)
