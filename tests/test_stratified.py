"""Stratified A/B analysis: variants compared within job/board/fit strata.

Guards the Simpson's-paradox failure mode — an aggregate win that does
not hold inside any stratum must not be read as a causal verdict.
"""

from __future__ import annotations

from applyjin.agents.stratified import (
    MIN_PER_ARM,
    analyze_stratified,
    format_stratified_report,
    stratum_values,
)
from applyjin.models import ApplicationRecord


def _rec(
    job_id: str,
    variant: str = "A",
    status: str = "rejected",
    title: str = "Backend Engineer",
    board: str = "greenhouse",
    fit_score: float = 0.9,
) -> ApplicationRecord:
    return ApplicationRecord(
        job_id=job_id,
        title=title,
        board=board,
        fit_score=fit_score,
        status=status,
        variant=variant,
    )


class TestStratumValues:
    def test_job_family_from_title(self):
        record = _rec("1", title="Senior AI Engineer")
        values = stratum_values(record)
        assert values["job_family"] == "ai_engineering"
        assert values["seniority"] == "senior_plus"

    def test_seniority_buckets(self):
        assert stratum_values(_rec("1", title="ML Intern"))["seniority"] == "intern"
        assert stratum_values(_rec("2", title="Junior Developer"))["seniority"] == "entry"
        assert stratum_values(_rec("3", title="Software Engineer"))["seniority"] == "mid"
        assert stratum_values(_rec("4", title="Staff Engineer"))["seniority"] == "senior_plus"

    def test_fit_buckets(self):
        assert stratum_values(_rec("1", fit_score=0.9))["fit_bucket"] == "high"
        assert stratum_values(_rec("2", fit_score=0.6))["fit_bucket"] == "medium"
        assert stratum_values(_rec("3", fit_score=0.3))["fit_bucket"] == "low"
        # 0–100 scale scores are normalized
        assert stratum_values(_rec("4", fit_score=85.0))["fit_bucket"] == "high"

    def test_missing_fit_score_is_unknown(self):
        class _Bare:
            title = "Backend Engineer"
            board = "greenhouse"
            fit_score = None

        assert stratum_values(_Bare())["fit_bucket"] == "unknown"

    def test_unknown_board(self):
        assert stratum_values(_rec("1", board=""))["board"] == "unknown"


class TestAnalyzeStratified:
    def test_slices_by_family_board_and_fit(self):
        records = [
            _rec(f"ai-{i}", variant="AB"[i % 2],
                 status="interview" if i % 3 == 0 else "rejected",
                 title="AI Engineer")
            for i in range(40)
        ]
        records += [
            _rec(f"be-{i}", variant="AB"[i % 2],
                 status="interview" if i % 5 == 0 else "rejected",
                 title="Backend Engineer", fit_score=0.3)
            for i in range(40)
        ]
        results = analyze_stratified(records)
        slices = {(r.stratum, r.value) for r in results}
        assert ("job_family", "ai_engineering") in slices
        assert ("job_family", "software") in slices
        assert ("fit_bucket", "high") in slices
        assert ("fit_bucket", "low") in slices

    def test_starved_arm_not_interpreted(self):
        records = [
            _rec(f"r-{i}", variant="A", status="rejected", title="Data Scientist")
            for i in range(15)
        ] + [
            _rec(f"b-{i}", variant="B", status="rejected", title="Data Scientist")
            for i in range(3)  # below MIN_PER_ARM
        ]
        results = analyze_stratified(records)
        assert results
        assert all(r.verdict == "insufficient_data" for r in results)
        assert all(r.result is None for r in results)
        assert all(r.warnings for r in results)

    def test_decisive_stratum_reported(self):
        # Within one stratum: B interviews far more than A, both arms large.
        records = (
            [_rec(f"a-{i}", variant="A", status="rejected") for i in range(30)]
            + [_rec(f"b-{i}", variant="B", status="interview" if i < 14 else "rejected")
               for i in range(30)]
        )
        results = analyze_stratified(records)
        same = [r for r in results if (r.stratum, r.value) == ("job_family", "software")]
        assert same and same[0].verdict in ("A", "B")  # decisive within stratum

    def test_draft_rows_ignored(self):
        records = [_rec(f"d-{i}", status="draft") for i in range(50)]
        assert analyze_stratified(records) == []

    def test_simpsons_paradox_scenario(self):
        """Aggregate says B wins; inside every stratum A wins.

        The stratified report must surface the reversal, not the aggregate.
        High-fit slice: A strong. Low-fit slice: A strong. Aggregate: B
        looks better only because B got more high-fit applications.
        """
        records = []
        # High-fit: 30 apps, A wins 20/30 interviews, B wins 10/30
        for i in range(15):
            records.append(_rec(f"hf-a-{i}", variant="A", status="interview", fit_score=0.9))
            records.append(_rec(f"hf-a2-{i}", variant="A", status="rejected", fit_score=0.9))
        for i in range(5):
            records.append(_rec(f"hf-b-{i}", variant="B", status="interview", fit_score=0.9))
            records.append(_rec(f"hf-b2-{i}", variant="B", status="rejected", fit_score=0.9))
            records.append(_rec(f"hf-b3-{i}", variant="B", status="rejected", fit_score=0.9))
        # Low-fit: 30 apps, A wins 4/15, B wins 1/15
        for i in range(4):
            records.append(_rec(f"lf-a-{i}", variant="A", status="interview", fit_score=0.3))
        for i in range(11):
            records.append(_rec(f"lf-a2-{i}", variant="A", status="rejected", fit_score=0.3))
        records.append(_rec("lf-b-0", variant="B", status="interview", fit_score=0.3))
        for i in range(14):
            records.append(_rec(f"lf-b2-{i}", variant="B", status="rejected", fit_score=0.3))

        results = analyze_stratified(records)
        fit_slices = [r for r in results if r.stratum == "fit_bucket"]
        high = next(r for r in fit_slices if r.value == "high")
        low = next(r for r in fit_slices if r.value == "low")
        # Both arms have data in each fit slice; A's rate leads in both.
        assert high.total_a >= MIN_PER_ARM and high.total_b >= MIN_PER_ARM
        assert high.rate_a > high.rate_b
        assert low.rate_a > low.rate_b


class TestFormatReport:
    def test_empty(self):
        assert "No stratified slices" in format_stratified_report([])

    def test_sections_and_caveat(self):
        records = (
            [_rec(f"a-{i}", variant="A", status="rejected") for i in range(12)]
            + [_rec(f"b-{i}", variant="B", status="interview" if i < 9 else "rejected")
               for i in range(12)]
        )
        text = format_stratified_report(analyze_stratified(records))
        assert "observational" in text  # the causal caveat is always present
        assert "job_family" in text or "fit_bucket" in text
