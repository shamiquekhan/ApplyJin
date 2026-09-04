"""Phase 4 tests: profiles, ATS scout, prep, outreach, dashboard, web."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hermes.agents.ats_scout import (
    _looks_remote,
    _matches,
    _slugify,
    guess_slug_from_url,
    scrape_greenhouse,
    scrape_lever,
)
from hermes.agents.dashboard import render
from hermes.agents.interview_prep import (
    InterviewPrepAgent,
    _split_star,
    build_prep_document,
)
from hermes.agents.outreach_agent import (
    LINKEDIN_NOTE_LIMIT,
    OutreachAgent,
    _trim_to_limit,
    draft_linkedin_note,
    draft_followup_email,
)
from hermes.agents.tracker import Tracker
from hermes.config import Profile, Identity, TargetProfile, load_profile, list_profiles
from hermes.models import ApplicationRecord, JobAnalysis, JobPosting, ResumeDocument


@pytest.fixture
def profile() -> Profile:
    return Profile(
        identity=Identity(
            name="Shamique Khan", email="shamique@example.com",
            linkedin="linkedin.com/in/shamique-khan",
        ),
        target=TargetProfile(seniority="junior", years_experience=1),
        skills={"llm": ["RAG", "LangGraph", "PyTorch"]},
    )


# --------------------------------------------------------------- profiles


class TestProfiles:
    def test_default_profile_loads(self):
        prof = load_profile(name="default")
        assert prof.name == "default"

    def test_named_profile_resolution(self, tmp_path, monkeypatch):
        from hermes import config as cfg

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "ml-research.yml").write_text(
            "identity:\n  name: 'Test User'\ntarget:\n  titles: ['ML Engineer']\n"
            "resume_path: 'data/base_resume.md'\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(cfg, "PROFILE_DIR", profiles_dir)
        prof = load_profile(name="ml-research")
        assert prof.name == "ml-research"
        assert prof.identity.name == "Test User"
        assert prof.resume_path == "data/base_resume.md"

    def test_missing_profile_raises(self, tmp_path, monkeypatch):
        from hermes import config as cfg

        monkeypatch.setattr(cfg, "PROFILE_DIR", tmp_path / "profiles")
        with pytest.raises(FileNotFoundError, match="not found"):
            load_profile(name="ghost")

    def test_list_profiles(self, tmp_path, monkeypatch):
        from hermes import config as cfg

        d = tmp_path / "profiles"
        d.mkdir()
        (d / "b.yml").write_text("identity:\n  name: 'B'\n", encoding="utf-8")
        (d / "a.yml").write_text("identity:\n  name: 'A'\n", encoding="utf-8")
        monkeypatch.setattr(cfg, "PROFILE_DIR", d)
        assert list_profiles() == ["default", "a", "b"]


# ---------------------------------------------------------------- ATS scout


class TestATSScout:
    def test_slugify(self):
        assert _slugify("Stripe, Inc.") == "stripe-inc"
        assert _slugify("Anthropic") == "anthropic"

    def test_guess_slug_from_url(self):
        assert guess_slug_from_url("https://boards.greenhouse.io/acme/jobs/1") == "acme"
        assert guess_slug_from_url("https://jobs.lever.co/acme/xyz") == "acme"
        assert guess_slug_from_url("https://example.com") is None

    def test_matches_and_remote(self):
        assert _matches("Senior AI Engineer", "ai engineer")
        assert not _matches("Frontend Dev", "ai engineer")
        assert _looks_remote("AI Engineer", "Remote — Global")
        assert not _looks_remote("AI Engineer", "New York, NY")

    def test_scrape_greenhouse_mock(self, monkeypatch):
        payload = {
            "jobs": [
                {
                    "id": 123, "title": "AI Engineer",
                    "company": {"name": "Acme"},
                    "location": {"name": "Remote"},
                    "absolute_url": "https://boards.greenhouse.io/acme/123",
                    "content": "<p>Build LLM agents</p>",
                    "updated_at": "2026-09-01T00:00:00Z",
                }
            ]
        }
        monkeypatch.setattr(
            "hermes.agents.ats_scout._http_get_json", lambda url: payload
        )
        jobs = scrape_greenhouse("acme", keywords="AI")
        assert len(jobs) == 1
        assert jobs[0].job_id == "greenhouse-123"
        assert jobs[0].board == "greenhouse"
        assert jobs[0].is_remote

    def test_scrape_greenhouse_no_board(self, monkeypatch):
        monkeypatch.setattr(
            "hermes.agents.ats_scout._http_get_json", lambda url: None
        )
        assert scrape_greenhouse("no-such-company-xyz") == []

    def test_scrape_lever_mock(self, monkeypatch):
        payload = [
            {
                "id": "abc", "text": "ML Engineer",
                "categories": {"location": "Remote", "team": "Data"},
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "description": {"plain": "Train models"},
                "createdAt": 1756000000000,
            }
        ]
        monkeypatch.setattr(
            "hermes.agents.ats_scout._http_get_json", lambda url: payload
        )
        jobs = scrape_lever("acme")
        assert len(jobs) == 1
        assert jobs[0].job_id == "lever-abc"
        assert jobs[0].is_remote


# ---------------------------------------------------------------- prep


class TestInterviewPrep:
    def test_split_star_extracts_metrics(self):
        story = _split_star(
            "Built FastAPI services handling 2M requests/day, cutting latency 30%"
        )
        assert "30%" in story["metrics"]
        assert story["result"]

    def test_heuristic_prep_document(self, tmp_path, profile):
        analysis = JobAnalysis(
            job_id="j", title="AI Engineer", company="Acme",
            required_skills=["RAG", "LangGraph"], years_experience=1,
        )
        job = JobPosting(job_id="j", title="AI Engineer", company="Acme")
        resume = ResumeDocument(
            raw_text="x",
            bullets=[
                __import__("hermes.models", fromlist=["Bullet"]).Bullet(
                    id="b1", text="Built RAG pipeline with LangGraph, +40% recall"
                )
            ],
        )
        agent = InterviewPrepAgent(profile, router=None, library=None)
        out = agent.prepare(job, analysis, resume, output_dir=tmp_path)
        text = out.read_text(encoding="utf-8")
        assert "STAR" in text
        assert "RAG" in text
        assert "Tell me about a time" in text or "walk me through" in text.lower()
        assert out.exists()

    def test_llm_enrichment_path(self, profile):
        class FakeRouter:
            def complete_json(self, system, prompt):
                return {
                    "questions": ["Why Acme?"],
                    "star_actions": ["Polished action sentence"],
                }

        agent = InterviewPrepAgent(profile, router=FakeRouter())
        analysis = JobAnalysis(job_id="j", required_skills=["PyTorch"])
        stories = [{"situation": "s", "task": "t", "action": "raw", "result": "r", "metrics": []}]
        questions, stories = agent._llm_enrich(
            JobPosting(job_id="j", title="T", company="C"),
            analysis, stories, ["old question"],
        )
        assert questions == ["Why Acme?"]
        assert stories[0]["action"] == "Polished action sentence"


# ---------------------------------------------------------------- outreach


class TestOutreach:
    def test_linkedin_note_under_limit(self, profile):
        analysis = JobAnalysis(
            job_id="j", title="AI Engineer", company="Acme",
            required_skills=["RAG"],
        )
        note = draft_linkedin_note(profile, analysis)
        assert len(note) <= LINKEDIN_NOTE_LIMIT
        assert "Acme" in note

    def test_trim_to_limit(self):
        long_text = "word " * 200
        trimmed = _trim_to_limit(long_text)
        assert len(trimmed) <= LINKEDIN_NOTE_LIMIT
        # Sentence-terminated text keeps its last full sentence
        sentences = "This is a full sentence. " * 40
        trimmed2 = _trim_to_limit(sentences)
        assert len(trimmed2) <= LINKEDIN_NOTE_LIMIT
        assert trimmed2.endswith(". ") or trimmed2.endswith(".")

    def test_llm_note_trimmed(self, profile):
        class WordyRouter:
            def complete(self, system, prompt):
                from hermes.models import LLMResponse

                return LLMResponse(
                    text="x" * 500, model="fake", provider="fake"
                )

        analysis = JobAnalysis(job_id="j", title="T", company="C", required_skills=["X"])
        note = draft_linkedin_note(profile, analysis, router=WordyRouter())
        assert len(note) <= LINKEDIN_NOTE_LIMIT

    def test_followup_email_template(self, profile):
        analysis = JobAnalysis(
            job_id="j", title="AI Engineer", company="Acme", required_skills=["RAG"]
        )
        email = draft_followup_email(profile, analysis, applied_days_ago=10)
        assert "Acme" in email
        assert "10 days" in email

    def test_outreach_agent_writes_files(self, tmp_path, profile):
        analysis = JobAnalysis(
            job_id="j", title="AI Eng", company="Acme", required_skills=["RAG"]
        )
        agent = OutreachAgent(profile)
        drafts = agent.draft_for(analysis, output_dir=tmp_path)
        assert drafts["note"].exists()
        assert drafts["email"].exists()
        assert len(drafts["note_text"]) <= LINKEDIN_NOTE_LIMIT


# ---------------------------------------------------------------- dashboard


class TestDashboard:
    def test_render_empty(self, tmp_path, capsys):
        render(tmp_path / "empty.db")
        out = capsys.readouterr().out
        assert "No applications" in out

    def test_render_with_data(self, tmp_path, capsys):
        tracker = Tracker(tmp_path / "t.db")
        for i, status in enumerate(
            ["pending_review", "submitted", "interview", "rejected"]
        ):
            row_id, _ = tracker.add_application(
                ApplicationRecord(
                    job_id=f"j{i}", title="AI Engineer",
                    company=f"Co{i}", status="pending_review",
                )
            )
            tracker.conn.execute(
                "UPDATE applications SET status=?, applied_at=? WHERE id=?",
                (status, datetime.utcnow() - timedelta(days=i), row_id),
            )
        tracker.conn.commit()
        tracker.close()

        render(tmp_path / "t.db", learning=False)
        out = capsys.readouterr().out
        assert "Hermes Dashboard" in out
        assert "Pipeline Funnel" in out
        assert "Review Queue" in out


# ---------------------------------------------------------------- web


class TestWebDashboard:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        fastapi_test = pytest.importorskip("fastapi.testclient")
        from hermes.web import app as web_module

        monkeypatch.setattr(web_module, "DB_PATH", tmp_path / "web.db")
        monkeypatch.setattr(web_module, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(web_module, "PDF_DIR", tmp_path / "pdfs")
        # Never hit Gemini from tests — heuristic mode everywhere.
        monkeypatch.setattr(web_module, "_router", lambda: None)
        return fastapi_test.TestClient(web_module.app)

    def test_index_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        # React build when present, legacy dashboard page otherwise
        assert "Hermes Dashboard" in resp.text or "ApplyJin" in resp.text

    def test_dashboard_route(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        # React Console when the frontend is built; legacy workbench otherwise
        assert "ApplyJin" in resp.text or "Hermes Dashboard" in resp.text

    def test_public_stats(self, client):
        resp = client.get("/api/public/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["applications"] >= 0
        assert data["waitlist"] >= 0
        assert data["boards_supported"] == 8
        assert data["agents"] == 7

    def test_waitlist_flow(self, client):
        # valid signup
        resp = client.post(
            "/api/public/waitlist",
            data={"email": "shamique@example.com", "source": "test"},
        ).json()
        assert resp["ok"] is True
        assert resp["duplicate"] is False

        # duplicate returns friendly message
        resp = client.post(
            "/api/public/waitlist", data={"email": "SHAMIQUE@example.com"}
        ).json()
        assert resp["ok"] is True
        assert resp["duplicate"] is True

        # invalid email rejected
        assert (
            client.post("/api/public/waitlist", data={"email": "not-an-email"}).status_code
            == 400
        )

        # count is public
        stats = client.get("/api/public/stats").json()
        assert stats["waitlist"] >= 1

    def test_resume_paste_and_list(self, client):
        resp = client.post(
            "/api/resumes/create",
            data={"name": "Test Resume", "content": "# Jane\n\n## Experience\n\n- Built RAG systems with Python"},
        )
        assert resp.status_code == 200
        rid = resp.json()["id"]

        listed = client.get("/api/resumes").json()
        assert len(listed) == 1
        assert listed[0]["name"] == "Test Resume"

        detail = client.get(f"/api/resumes/{rid}").json()
        assert "RAG systems" in detail["content_md"]

    def test_resume_upload_docx(self, client):
        cv_path = (
            Path(__file__).resolve().parent.parent
            / "Shamique_Khan_AI_Engineer_CV (5).docx"
        )
        if not cv_path.exists():
            pytest.skip("CV docx not present")
        with open(cv_path, "rb") as fh:
            resp = client.post(
                "/api/resumes/upload",
                files={"file": ("cv.docx", fh, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"name": "Shamique CV"},
            )
        assert resp.status_code == 200
        assert resp.json()["bullets"] >= 15

    def test_jd_and_keyword_extraction(self, client):
        jd_id = client.post(
            "/api/job-descriptions",
            data={
                "title": "AI Engineer",
                "company": "Acme",
                "content": (
                    "We need an AI engineer with Python, LangChain, RAG, Docker, "
                    "Kubernetes experience. Strong communication and collaboration. "
                    "You will build LLM systems and work cross-functionally."
                ),
            },
        ).json()["id"]

        kws = client.post(f"/api/job-descriptions/{jd_id}/extract-keywords").json()
        assert "Python" in kws["hard_skills"]
        assert "LangChain" in kws["hard_skills"]
        assert any("communication" in s for s in kws["soft_skills"])

        # keywords cached on the JD row
        jd = client.get(f"/api/job-descriptions/{jd_id}").json()
        assert jd["keywords"]["hard_skills"]

    def test_full_tailor_flow_with_scores(self, client):
        rid = client.post(
            "/api/resumes/create",
            data={
                "name": "Engineer",
                "content": (
                    "# Jane\n\n## Experience\n\n### SWE | Acme\n\n"
                    "- Built Python RAG pipelines and Docker deployments\n"
                    "- Led LLM evaluation with LangChain"
                ),
            },
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={
                "title": "AI Engineer", "company": "Acme",
                "content": "Python, RAG, LangChain, Docker, LLM evaluation required.",
            },
        ).json()["id"]

        app_resp = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()
        app_id = app_resp["id"]
        assert app_resp["scores_before"]["keyword_match"] > 0
        assert 0 <= app_resp["scores_before"]["overall"] <= 100

        tailored = client.post(
            f"/api/applications/{app_id}/tailor",
            data={"selected_keywords": '["Python", "RAG", "Docker"]'},
        ).json()
        assert tailored["tailored_resume_md"]
        assert "validated" in tailored
        assert tailored["scores_after"]["overall"] >= 0
        assert "delta" in tailored

        letter = client.post(
            f"/api/applications/{app_id}/cover-letter"
        ).json()
        assert len(letter["cover_letter_md"]) > 50

        # history row
        apps = client.get("/api/applications").json()
        assert len(apps) == 1
        assert apps[0]["status"] == "ready"

    def test_pdf_download(self, client):
        rid = client.post(
            "/api/resumes/create",
            data={"name": "R", "content": "# Jane\n\n- Built things"},
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "T", "company": "C", "content": "Python role with Docker and RAG systems required."},
        ).json()["id"]
        app_id = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()["id"]
        client.post(
            f"/api/applications/{app_id}/tailor",
            data={"selected_keywords": '["Python"]'},
        )

        pdf = client.get(f"/api/applications/{app_id}/download-resume")
        # PDF via Playwright in this env; HTML fallback also acceptable
        assert pdf.status_code in (200, 503)
        if pdf.status_code == 200:
            assert pdf.content[:5] == b"%PDF-"

    def test_download_before_tailor_404s(self, client):
        rid = client.post(
            "/api/resumes/create", data={"name": "R", "content": "# X\n\n- stuff"}
        ).json()["id"]
        jid = client.post(
            "/api/job-descriptions",
            data={"title": "T", "company": "C", "content": "Python role requiring RAG and Docker skills."},
        ).json()["id"]
        app_id = client.post(
            "/api/applications", data={"resume_id": rid, "jd_id": jid}
        ).json()["id"]
        assert client.get(f"/api/applications/{app_id}/download-resume").status_code == 404

    def test_score_endpoint(self, client):
        resp = client.post(
            "/api/score",
            data={
                "resume_text": "Python engineer with RAG and Docker",
                "jd_text": "Need Python, RAG, Docker, Kubernetes skills",
            },
        ).json()
        assert 0 <= resp["overall"] <= 100

    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_validation_errors(self, client):
        # empty content rejected
        resp = client.post(
            "/api/resumes/create", data={"name": "x", "content": " "}
        )
        assert resp.status_code == 400
        # short JD rejected
        resp = client.post(
            "/api/job-descriptions", data={"title": "t", "company": "c", "content": "short"}
        )
        assert resp.status_code == 400
        # unknown ids 404
        assert client.get("/api/resumes/999").status_code == 404
        assert client.get("/api/job-descriptions/999").status_code == 404
