"""A/B testing for resume style variants.

Random 50/50 assignment per application; chi-squared (with Yates
correction for small samples) on interview-rate differences between
variants A and B. Deterministic and dependency-free.
"""

from __future__ import annotations

import math
import random


def assign_variant(rng: random.Random | None = None) -> str:
    """Fair coin-flip variant assignment ('A' or 'B')."""
    rng = rng or random
    return "A" if rng.random() < 0.5 else "B"


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
    def winner(self) -> str:
        """'A', 'B', or 'inconclusive'."""
        if not self.significant or self.total_a == 0 or self.total_b == 0:
            return "inconclusive"
        return "A" if self.rate_a > self.rate_b else "B"

    @property
    def lift(self) -> float:
        """Relative interview-rate improvement of B over A."""
        if self.rate_a == 0:
            return 0.0
        return (self.rate_b - self.rate_a) / self.rate_a

    def summary(self) -> str:
        verdict = self.winner
        if verdict == "inconclusive":
            return (
                f"A: {self.successes_a}/{self.total_a} ({self.rate_a:.0%}) vs "
                f"B: {self.successes_b}/{self.total_b} ({self.rate_b:.0%}) "
                f"— inconclusive (chi2={self.chi2:.2f}, p={self.p_value:.3f}). "
                f"Keep collecting outcomes."
            )
        return (
            f"{verdict} WINS: {self.successes_a}/{self.total_a} ({self.rate_a:.0%}) vs "
            f"{self.successes_b}/{self.total_b} ({self.rate_b:.0%}) "
            f"(chi2={self.chi2:.2f}, p={self.p_value:.4f}, lift={self.lift:+.0%}). "
            f"Promote {verdict}'s style guide."
        )


def analyze_variants(stats: dict[str, dict[str, int]]) -> ABResult:
    """Run the A/B comparison from tracker variant_stats()."""
    chi2, p = chi_squared_yates_2x2(
        _rates(stats.get("A", {})), _rates(stats.get("B", {}))
    )
    return ABResult(stats.get("A", {}), stats.get("B", {}), chi2, p)
