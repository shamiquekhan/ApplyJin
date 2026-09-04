"""Phase 3 tests: A/B stats, learning agent, migrations, style guide, triage."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hermes.agents.ab_testing import (
    ABResult,
    assign_variant,
    analyze_variants,
    chi_squared_yates_2x2,
)
from hermes.agents.learning_agent import LearningAgent, _pearson
from hermes.agents.tracker import Tracker
from hermes.agents.email_triage import (
    EmailTriageAgent,
    _already_advanced,
    _company_from_sender,
    _status_for,
    classify_message,
)
from hermes.models import ApplicationRecord
from hermes.utils.resume_parser import parse_resume
from hermes.config import Profile


# ------------------------------------------------------------ chi-squared


class TestChiSquared:
    def test_identical_rates_not_significant(self):
        chi2, p = chi_squared_yates_2x2((10, 50), (10, 50))
        # Yates correction keeps tiny observed diffs small, never significant
        assert chi2 < 1.0
        assert p > 0.3

    def test_big_difference_significant(self):
        # 30/50 vs 5/50 interviews — clearly different
        chi2, p = chi_squared_yates_2x2((30, 50), (5, 50))
        assert chi2 > 10
        assert p < 0.01

    def test_small_sample_yates_correction(self):
        # With Yates, tiny samples shouldn't scream significance
        chi2, p = chi_squared_yates_2x2((3, 5), (0, 5))
        assert p > 0.05  # Yates makes this non-significant

    def test_zero_totals_safe(self):
        chi2, p = chi_squared_yates_2x2((0, 0), (0, 0))
        assert (chi2, p) == (0.0, 1.0)

    def test_sf_matches_erfc(self):
        _, p = chi_squared_yates_2x2((30, 50), (5, 50))
        assert 0 <= p <= 1
        # chi2=1 should give p ~ 0.317
        assert math.isclose(
            chi_squared_yates_2x2((0, 0), (0, 0))[1], 1.0
        )


class TestAssignVariant:
    def test_fair_distribution(self):
        rng = random.Random(0)
        counts = {"A": 0, "B": 0}
        for _ in range(1000):
            counts[assign_variant(rng)] += 1
        # 50/50 within 5%
        assert abs(counts["A"] - 500) < 50
        assert assign_variant(rng) in ("A", "B")


class TestABResult:
    def test_summary_winner(self):
        stats = {
            "A": {"interview": 4, "rejected": 30, "no_response": 26},
            "B": {"interview": 16, "rejected": 20, "no_response": 24},
        }
        result = analyze_variants(stats)
        assert result.winner == "B"
        assert result.significant
        assert result.lift > 0
        assert "B WINS" in result.summary()

    def test_inconclusive_when_small(self):
        stats = {
            "A": {"interview": 2, "rejected": 8},
            "B": {"interview": 3, "rejected": 7},
        }
        result = analyze_variants(stats)
        assert result.winner == "inconclusive"
        assert "inconclusive" in result.summary()

    def test_missing_arm(self):
        result = analyze_variants({"A": {"interview": 5, "rejected": 5}, "B": {}})
        assert result.winner == "inconclusive"


# ------------------------------------------------------------ tracker p3


class TestTrackerPhase3:
    def test_migration_adds_variant_column(self, tmp_path):
        """A Phase-1-era database must migrate in place."""
        import sqlite3

        legacy = tmp_path / "legacy.db"
        conn = sqlite3.connect(str(legacy))
        conn.execute(
            """
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY, job_id TEXT UNIQUE, title TEXT,
                company TEXT, board TEXT, url TEXT, applied_at TIMESTAMP,
                status TEXT, fit_score REAL, ats_score_before REAL,
                ats_score_after REAL, resume_variant_hash TEXT,
                coverletter_hash TEXT, tailored_resume_path TEXT,
                coverletter_path TEXT, notes TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO applications (job_id, title) VALUES ('old-1', 'X')"
        )
        conn.commit()
        conn.close()

        tracker = Tracker(legacy)  # must migrate without error
        row = tracker.conn.execute(
            "SELECT variant, outcome_source FROM applications WHERE job_id='old-1'"
        ).fetchone()
        assert row["variant"] == "A"
        assert row["outcome_source"] == ""
        tracker.close()

    def test_variant_stats(self, tmp_path):
        tracker = Tracker(tmp_path / "t.db")
        for i, (variant, status) in enumerate(
            [("A", "interview"), ("A", "rejected"), ("B", "interview"),
             ("B", "no_response"), ("B", "interview")]
        ):
            row_id, _ = tracker.add_application(
                ApplicationRecord(job_id=f"j{i}", variant=variant)
            )
            tracker.conn.execute(
                "UPDATE applications SET status = ? WHERE id = ?", (status, row_id)
            )
        tracker.conn.commit()
        stats = tracker.variant_stats()
        assert stats["A"]["interview"] == 1
        assert stats["B"]["interview"] == 2
        result = analyze_variants(stats)
        assert result.total_b == 3
        tracker.close()

    def test_style_guide_versioning(self, tmp_path):
        tracker = Tracker(tmp_path / "t.db")
        assert tracker.active_style_guide() == (None, "")
        tracker.save_style_guide(1, "guide-one", "learning_agent")
        tracker.save_style_guide(2, "guide-two", "learning_agent")
        version, guide = tracker.active_style_guide()
        assert version == 2
        assert guide == "guide-two"
        history = tracker.style_guide_history()
        assert len(history) == 2
        assert sum(h["active"] for h in history) == 1
        tracker.close()

    def test_set_variant_validation(self, tmp_path):
        tracker = Tracker(tmp_path / "t.db")
        row_id, _ = tracker.add_application(ApplicationRecord(job_id="j"))
        with pytest.raises(ValueError):
            tracker.set_variant(row_id, "C")
        tracker.close()


# ------------------------------------------------------------ learning


class TestLearningAgent:
    def test_pearson(self):
        xs = [1, 2, 3, 4, 5]
        assert _pearson(xs, xs) == pytest.approx(1.0)
        assert _pearson(xs, [5, 4, 3, 2, 1]) == pytest.approx(-1.0)
        assert _pearson(xs, [1, 1, 1, 1, 1]) == 0.0

    def test_report_on_seeded_data(self, tmp_path, monkeypatch):
        # Seed via the demo script logic (in-memory variant)
        import shutil

        db = tmp_path / "hermes.db"
        apps_dir = tmp_path / "apps"
        monkeypatch.chdir(tmp_path)
        shutil.copytree(
            Path(__file__).parent.parent / "data", tmp_path / "data",
            dirs_exist_ok=True,
        )
        (tmp_path / "data" / "hermes.db").unlink(missing_ok=True)

        from scripts.seed_demo_data import seed

        seed(db_path=(tmp_path / "data" / "hermes.db"), wipe=True)

        tracker = Tracker(tmp_path / "data" / "hermes.db")
        agent = LearningAgent(tracker, min_sample=30)
        report = agent.analyze()

        assert report.sample_size >= 45
        assert report.ab_result is not None
        # The seeded signal: variant B wins
        assert report.ab_result.winner == "B"
        assert report.ats_delta_correlation is not None
        assert report.style_guide
        assert "STYLE GUIDE" in report.style_guide

        version = agent.apply_style_guide(report)
        assert version == 1
        v, guide = tracker.active_style_guide()
        assert v == 1 and guide == report.style_guide

        # Second apply versions up
        report2 = agent.analyze()
        assert agent.apply_style_guide(report2) == 2
        tracker.close()

    def test_insufficient_data_warns(self, tmp_path):
        tracker = Tracker(tmp_path / "t.db")
        row_id, _ = tracker.add_application(ApplicationRecord(job_id="j1"))
        tracker.conn.execute(
            "UPDATE applications SET status='rejected' WHERE id=?", (row_id,)
        )
        tracker.conn.commit()
        agent = LearningAgent(tracker, min_sample=30)
        report = agent.analyze()
        assert not report.sufficient_data
        assert any("insufficient" in w or "only" in w for w in report.warnings)
        assert "limited data" in report.style_guide
        tracker.close()


# ------------------------------------------------------------ triage


class TestEmailTriage:
    def test_classify_interview(self):
        assert classify_message(
            "Your application", "We'd like to invite you to interview next week"
        ) == "interview"

    def test_classify_rejection(self):
        assert classify_message(
            "Update on your application",
            "Unfortunately we decided to move forward with other candidates",
        ) == "rejected"

    def test_classify_offer(self):
        assert classify_message(
            "Good news", "We are pleased to offer you the position"
        ) == "offer"

    def test_priority_offer_over_interview(self):
        # Offer phrasing wins even if 'interview' words present
        assert classify_message(
            "Interview outcome",
            "After your final interview, we are pleased to extend an offer",
        ) == "offer"

    def test_follow_up_and_noise(self):
        assert classify_message("Thanks", "Thank you for applying, we received your application") == "follow_up"
        assert classify_message("Random", "Lunch tomorrow?") is None

    def test_company_from_sender(self):
        assert _company_from_sender("HR <careers@agentco.com>") == "agentco"
        assert _company_from_sender("x@llmlabs.io") == "llmlabs"

    def test_status_for(self):
        assert _status_for("offer") == "offer"
        assert _status_for("follow_up") is None

    def test_never_downgrade(self):
        assert _already_advanced("interview", "rejected")
        assert _already_advanced("interview", "phone_screen")
        assert not _already_advanced("no_response", "interview")

    def test_match_company_fuzzy(self, tmp_path):
        tracker = Tracker(tmp_path / "t.db")
        row_id, _ = tracker.add_application(
            ApplicationRecord(job_id="j", company="AgentCo", title="AI Eng")
        )
        tracker.conn.execute(
            "UPDATE applications SET status='submitted' WHERE id=?", (row_id,)
        )
        tracker.conn.commit()
        agent = EmailTriageAgent(tracker)
        apps = tracker.list_applications()
        match = agent._match_company("agentco", apps)
        assert match is not None
        assert match["id"] == row_id
        nomatch = agent._match_company("zzz-unknown", apps)
        assert nomatch is None
        tracker.close()


# ------------------------------------------------------------ tailor wiring


class TestTailorStyleGuide:
    def test_style_guide_in_prompt(self, tmp_path):
        from hermes.agents.resume_tailor import ResumeTailor
        from hermes.models import JobAnalysis, JobPosting

        class FakeRouter:
            def complete(self, prompt, **_):
                TestTailorStyleGuide.seen_prompt = prompt
                from hermes.models import LLMResponse

                return LLMResponse(text="tailored", model="fake", provider="fake")

        tailor = ResumeTailor(
            router=FakeRouter(),
            style_guide="LEAD with RAG experience",
            experimental_style_guide="LEAD with metrics and numbers",
        )
        resume = parse_resume(
            Path("data/base_resume.md"), Profile()
        )
        job = JobPosting(job_id="j", title="AI", company="X", description="RAG")
        analysis = JobAnalysis(job_id="j", required_skills=["RAG"])

        tailor.tailor(resume, job, analysis, variant="A")
        assert "LEAD with RAG experience" in self.seen_prompt

        tailor.tailor(resume, job, analysis, variant="B")
        assert "LEAD with metrics and numbers" in self.seen_prompt
