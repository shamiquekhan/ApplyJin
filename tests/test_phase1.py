"""Unit tests for guardrails, scoring, dedup, tracker, and parsing."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hermes.config import Profile, TargetProfile
from hermes.models import ApplicationRecord, Bullet, JobPosting, ResumeDocument
from hermes.agents.jd_analyzer import heuristic_analyze
from hermes.agents.fit_scorer import FitScorer
from hermes.agents.resume_tailor import select_relevant_bullets, validate_tailored
from hermes.agents.tracker import Tracker
from hermes.utils.ats_scorer import (
    keyword_match_score,
    missing_keywords,
    seniority_match,
    experience_match,
)
from hermes.utils.deduplicator import deduplicate_jobs


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def profile() -> Profile:
    return Profile(
        target=TargetProfile(seniority="mid", years_experience=5),
        skills={
            "languages": ["Python", "Go", "SQL"],
            "infra": ["Docker", "Kubernetes", "AWS", "PostgreSQL", "Redis"],
            "practices": ["CI/CD", "TDD", "observability"],
        },
        limits=__import__("hermes.config", fromlist=["Limits"]).Limits(
            max_applications_per_day=3
        ),
    )


@pytest.fixture
def resume(profile: Profile) -> ResumeDocument:
    return ResumeDocument(
        name="Jane Doe",
        summary="Backend engineer building Python services and cloud infrastructure.",
        skills=profile.all_skills,
        bullets=[
            Bullet(id="b1", text="Built FastAPI microservices handling 2M requests/day"),
            Bullet(id="b2", text="Migrated monolith to Kubernetes on AWS"),
            Bullet(id="b3", text="Designed PostgreSQL schema with 99.95% uptime"),
        ],
        seniority="mid",
        years_experience=5,
        raw_text=(
            "Jane Doe — Backend engineer. Python, Go, Docker, Kubernetes, AWS, "
            "PostgreSQL, Redis, CI/CD, TDD, FastAPI. 2020 - 2025 Streamline Inc."
        ),
    )


@pytest.fixture
def backend_job() -> JobPosting:
    return JobPosting(
        job_id="j1",
        title="Senior Backend Engineer",
        company="Acme",
        description=(
            "Senior Backend Engineer. 5+ years experience. Python, FastAPI, "
            "PostgreSQL, Docker, Kubernetes, AWS, CI/CD. gRPC. Fully remote."
        ),
    )


# ------------------------------------------------------------ ats scorer


class TestATSScorer:
    def test_keyword_match_full(self):
        score = keyword_match_score(
            ["Python", "Docker", "Kubernetes"], ["Python", "Docker", "Kubernetes"]
        )
        assert score == 1.0

    def test_keyword_match_partial(self):
        score = keyword_match_score(["Python", "Redis"], ["Python", "Kubernetes"])
        assert score == pytest.approx(0.5)

    def test_keyword_match_fuzzy(self):
        # kubernetes vs kubermetes-style typos and case variants
        assert keyword_match_score(["python"], ["Python"]) == 1.0
        assert keyword_match_score(["CI/CD pipelines"], ["ci/cd"]) >= 0.5

    def test_missing_keywords(self):
        missing = missing_keywords(
            ["Python"], ["Python", "Rust", "Terraform"]
        )
        assert "Rust" in missing and "Python" not in missing

    def test_seniority_match_aligned(self):
        assert seniority_match("mid", "mid") == 1.0
        assert seniority_match("senior", "senior") == 1.0

    def test_seniority_match_distance(self):
        assert seniority_match("junior", "staff") < seniority_match("mid", "senior")

    def test_experience_match(self):
        assert experience_match(6, 5) == 1.0
        assert experience_match(4, 5) == 0.75  # within one year
        assert experience_match(1, 5) == 0.4


# ---------------------------------------------------------------- dedup


class TestDeduplicator:
    def test_removes_cross_board_duplicates(self):
        jobs = [
            JobPosting(job_id="a", title="Senior Backend Engineer", company="Acme", board="indeed"),
            JobPosting(job_id="b", title="Sr. Backend Engineer (Remote)", company="Acme Corp", board="glassdoor"),
            JobPosting(job_id="c", title="Frontend Developer", company="Acme", board="google"),
        ]
        result = deduplicate_jobs(jobs)
        assert len(result) == 2
        assert result[0].job_id == "a"

    def test_different_companies_kept(self):
        jobs = [
            JobPosting(job_id="a", title="Backend Engineer", company="Acme"),
            JobPosting(job_id="b", title="Backend Engineer", company="Widget"),
        ]
        assert len(deduplicate_jobs(jobs)) == 2


# ------------------------------------------------------------ jd analyzer


class TestHeuristicAnalyzer:
    def test_extracts_lexicon_skills(self, backend_job):
        analysis = heuristic_analyze(backend_job)
        for skill in ("Python", "FastAPI", "PostgreSQL", "Kubernetes", "AWS"):
            assert skill in analysis.required_skills
        assert analysis.extractor == "heuristic"

    def test_seniority_and_years(self, backend_job):
        analysis = heuristic_analyze(backend_job)
        assert analysis.seniority_level == "senior"
        assert analysis.years_experience == 5

    def test_remote_policy(self, backend_job):
        assert heuristic_analyze(backend_job).remote_policy == "fully_remote"

    def test_red_flags(self):
        job = JobPosting(
            job_id="x",
            title="Rockstar Developer",
            company="StartupCo",
            description="Fast-paced environment, wear many hats, work hard play hard.",
        )
        analysis = heuristic_analyze(job)
        assert "fast-paced environment" in analysis.red_flags


# ---------------------------------------------------------------- fit scorer


class TestFitScorer:
    def test_good_match_passes(self, profile, resume, backend_job):
        analysis = heuristic_analyze(backend_job)
        scored = FitScorer(profile, min_fit_score=0.5).score(backend_job, analysis, resume)
        assert scored.passed_filter
        assert scored.fit_score > 0.5
        assert "keyword" in scored.score_breakdown

    def test_poor_match_rejected_with_reason(self, profile, resume):
        job = JobPosting(
            job_id="ml",
            title="ML Engineer",
            company="DataWorks",
            description=(
                "PyTorch, TensorFlow, deep learning, NLP, LLM, Spark, Airflow. "
                "PhD. 7+ years experience. On-site."
            ),
        )
        analysis = heuristic_analyze(job)
        scored = FitScorer(profile, min_fit_score=0.65).score(job, analysis, resume)
        assert not scored.passed_filter
        assert "fit" in scored.reject_reason


# ---------------------------------------------------------------- tailor


class TestTailorGuardrails:
    def test_clean_rewrite_passes(self, resume, backend_job):
        analysis = heuristic_analyze(backend_job)
        # Same facts, rephrased — should validate clean.
        clean = resume.raw_text.replace("Backend engineer", "Backend software engineer")
        assert validate_tailored(clean, resume, analysis) == []

    def test_invented_dates_flagged(self, resume, backend_job):
        analysis = heuristic_analyze(backend_job)
        dirty = resume.raw_text + " Previously at FakeCorp 1999 - 2004."
        violations = validate_tailored(dirty, resume, analysis)
        assert any("Dates" in v for v in violations)

    def test_missing_skill_injection_flagged(self, resume):
        analysis = heuristic_analyze(backend_job := JobPosting(
            job_id="j", title="BE", company="A",
            description="Rust, Python, Docker.",
        ))
        # 'Rust' is required by the JD, absent from base resume — injected = violation.
        dirty = resume.raw_text + " Expert in Rust systems programming."
        violations = validate_tailored(dirty, resume, analysis)
        assert any("skills the candidate lacks" in v for v in violations)

    def test_relevant_bullet_ranking(self, resume, backend_job):
        analysis = heuristic_analyze(backend_job)
        ranked = select_relevant_bullets(resume, analysis, top_k=2)
        assert len(ranked) == 2
        assert ranked[0] in [b.text for b in resume.bullets]

    def test_empty_llm_response_falls_back(self, resume, backend_job):
        """A provider returning empty text must never produce an empty file."""
        from hermes.agents.resume_tailor import ResumeTailor
        from hermes.models import JobAnalysis

        class EmptyRouter:
            def complete(self, prompt, **_):
                from hermes.models import LLMResponse

                return LLMResponse(text="", model="empty", provider="empty")

        analysis = JobAnalysis(job_id="j", required_skills=["Python"])
        tailor = ResumeTailor(router=EmptyRouter())
        result = tailor.tailor(resume, backend_job, analysis)
        assert result.model_used == "none-base-resume"
        assert result.text == resume.raw_text  # base resume, not empty


# ---------------------------------------------------------------- tracker


class TestTracker:
    def test_add_and_duplicate_block(self, tmp_path: Path):
        tracker = Tracker(tmp_path / "test.db")
        record = ApplicationRecord(job_id="job-1", title="BE", company="Acme")
        row_id, msg = tracker.add_application(record)
        assert row_id is not None

        dup_id, dup_msg = tracker.add_application(record)
        assert dup_id is None
        assert "Duplicate" in dup_msg
        tracker.close()

    def test_daily_rate_limit(self, tmp_path: Path):
        tracker = Tracker(tmp_path / "test.db")
        for i in range(3):
            tracker.add_application(ApplicationRecord(job_id=f"job-{i}"))
        blocked_id, msg = tracker.add_application(
            ApplicationRecord(job_id="job-overflow"), max_per_day=3
        )
        assert blocked_id is None
        assert "Daily limit" in msg
        tracker.close()

    def test_status_lifecycle(self, tmp_path: Path):
        tracker = Tracker(tmp_path / "test.db")
        row_id, _ = tracker.add_application(ApplicationRecord(job_id="job-1"))
        assert tracker.update_status(row_id, "submitted")
        record = tracker.get(row_id)
        assert record.status == "submitted"
        with pytest.raises(ValueError):
            tracker.update_status(row_id, "invalid-status")
        tracker.close()

    def test_stats_window(self, tmp_path: Path):
        tracker = Tracker(tmp_path / "test.db")
        r1_id, _ = tracker.add_application(ApplicationRecord(job_id="a"))
        r2_id, _ = tracker.add_application(ApplicationRecord(job_id="b"))
        tracker.update_status(r1_id, "interview")
        tracker.update_status(r2_id, "rejected")
        stats = tracker.stats(days=1)
        assert stats["total"] == 2
        assert stats["interviews"] == 1
        # both interview + rejected count as responses -> 100% response rate
        assert stats["responses"] == 2
        assert stats["response_rate"] == 1.0
        tracker.close()


# ---------------------------------------------------------------- embeddings


class TestEmbeddings:
    def test_hashed_fallback_deterministic(self):
        from hermes.utils.embeddings import HashedEmbeddings, cosine_similarity

        emb = HashedEmbeddings()
        a = emb.embed("python kubernetes docker")
        b = emb.embed("python kubernetes docker")
        c = emb.embed("quilting patterns and embroidery")
        assert a == b
        assert cosine_similarity(a, b) == 1.0
        assert cosine_similarity(a, c) < 0.5

    def test_norm(self):
        from hermes.utils.embeddings import HashedEmbeddings

        vec = HashedEmbeddings().embed("some text here")
        assert abs(sum(x * x for x in vec) - 1.0) < 1e-6
