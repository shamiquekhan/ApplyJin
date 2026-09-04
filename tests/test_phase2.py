"""Phase 2 tests: RAG library, DOCX parsing, application agent, PDF, CLI wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes.config import Profile, Identity, TargetProfile, Limits
from hermes.models import JobPosting
from hermes.agents.application_agent import FillResult, detect_ats
from hermes.agents.jd_analyzer import heuristic_analyze
from hermes.utils.experience_library import ExperienceLibrary
from hermes.utils.resume_parser import parse_resume


@pytest.fixture
def profile() -> Profile:
    return Profile(
        identity=Identity(
            name="Shamique Khan",
            email="shamique@example.com",
            linkedin="linkedin.com/in/shamique-khan",
            github="github.com/shamiquekhan",
            website="shamique-khan.vercel.app",
        ),
        target=TargetProfile(seniority="junior", years_experience=1),
        skills={"llm": ["LangGraph", "RAG", "PyTorch", "FastAPI"]},
        limits=Limits(min_fit_score=0.3),
    )


@pytest.fixture
def resume_md(tmp_path: Path, profile: Profile):
    path = tmp_path / "base_resume.md"
    path.write_text(
        "# Shamique Khan\n\n"
        "AI Engineer building LLM systems.\n\n"
        "## Experience\n\n"
        "### AI Engineer | Suproc | 2026\n\n"
        "- Architected and deployed 4+ multi-model LLM agents in Python\n"
        "- Built a gradient-boosted ranking model with XGBoost\n\n"
        "## Projects\n\n"
        "### ARAMS\n\n"
        "- Built a six-agent research assistant with a LangGraph state machine\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------- experience library


class TestExperienceLibrary:
    def test_index_and_query(self, resume_md, profile):
        parsed = parse_resume(resume_md, profile)
        lib = ExperienceLibrary(use_chroma=False)
        count = lib.index_resume(parsed)
        assert count == 3

        hits = lib.query("LLM agents multi-model Python", n_results=2)
        assert len(hits) == 2
        assert any("multi-model LLM agents" in h["text"] for h in hits)

    def test_query_ranks_relevant_first(self, resume_md, profile):
        parsed = parse_resume(resume_md, profile)
        lib = ExperienceLibrary(use_chroma=False)
        lib.index_resume(parsed)
        hits = lib.query("gradient boosting XGBoost ranking model", n_results=3)
        assert "XGBoost" in hits[0]["text"]

    def test_empty_query(self, resume_md, profile):
        lib = ExperienceLibrary(use_chroma=False)
        assert lib.query("   ") == []

    def test_chroma_backend(self, resume_md, profile):
        pytest.importorskip("chromadb")
        parsed = parse_resume(resume_md, profile)
        lib = ExperienceLibrary(use_chroma=True)
        assert lib.backend == "chromadb"
        count = lib.index_resume(parsed)
        assert count == 3
        hits = lib.query("LangGraph agents", n_results=1)
        assert hits and "LangGraph" in hits[0]["text"]


# --------------------------------------------------------- DOCX parsing


class TestDocxParsing:
    def test_docx_resume_parses(self, profile):
        cv_path = (
            Path(__file__).resolve().parent.parent
            / "Shamique_Khan_AI_Engineer_CV (5).docx"
        )
        if not cv_path.exists():
            pytest.skip("CV docx not present")
        parsed = parse_resume(cv_path, profile)
        assert "shamique khan" in parsed.raw_text.lower()
        assert "PIGNet" in parsed.raw_text or "battery" in parsed.raw_text.lower()
        assert len(parsed.bullets) >= 20  # rich CV: many bullets
        # LangGraph bullets must carry skill tags detected from profile
        langgraph_bullets = [b for b in parsed.bullets if "LangGraph" in b.text]
        assert langgraph_bullets
        assert "LangGraph" in langgraph_bullets[0].skills


# --------------------------------------------------------- tailor v2 RAG


class TestTailorV2:
    def test_rag_bullet_selection(self, resume_md, profile):
        from hermes.agents.resume_tailor import select_relevant_bullets

        parsed = parse_resume(resume_md, profile)
        lib = ExperienceLibrary(use_chroma=False)
        lib.index_resume(parsed)

        job = JobPosting(
            job_id="j",
            title="LLM Engineer",
            company="X",
            description="Build multi-model LLM agents and RAG systems.",
        )
        analysis = heuristic_analyze(job)
        selected = select_relevant_bullets(parsed, analysis, library=lib)
        assert selected, "RAG selection returned nothing"
        assert selected[0] in [b.text for b in parsed.bullets]

    def test_fallback_without_library(self, resume_md, profile):
        from hermes.agents.resume_tailor import select_relevant_bullets

        parsed = parse_resume(resume_md, profile)
        job = JobPosting(
            job_id="j",
            title="ML Engineer",
            company="X",
            description="XGBoost ranking models and gradient boosting.",
        )
        analysis = heuristic_analyze(job)
        selected = select_relevant_bullets(parsed, analysis, library=None)
        assert "XGBoost" in selected[0]


# --------------------------------------------------------- application agent


class TestApplicationAgent:
    def test_detect_ats_from_url(self):
        assert detect_ats("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"
        assert detect_ats("https://jobs.lever.co/acme/abc") == "lever"
        assert detect_ats("https://acme.wd1.myworkdayjobs.com/careers") == "workday"
        assert detect_ats("https://jobs.ashbyhq.com/acme/123") == "ashby"
        assert detect_ats("https://example.com/careers/123") == "unknown"

    def test_fill_result_never_submitted(self):
        result = FillResult(job_id="j", url="https://x")
        assert result.submitted is False  # hard invariant

    def test_profile_answers(self, profile):
        from hermes.agents.application_agent import _profile_answer

        assert _profile_answer(profile, "first_name") == "Shamique"
        assert _profile_answer(profile, "last_name") == "Khan"
        assert _profile_answer(profile, "email") == "shamique@example.com"
        assert _profile_answer(profile, "github") == "github.com/shamiquekhan"


# --------------------------------------------------------- PDF generation


class TestPDFGenerator:
    def test_markdown_to_html(self):
        from hermes.utils.pdf_generator import markdown_to_html

        html = markdown_to_html(
            "# Jane Doe\n\njane@x.com\n\n## Experience\n\n- Built things\n"
        )
        assert "<h1>Jane Doe</h1>" in html
        assert "<h2>Experience</h2>" in html
        assert "<li>Built things</li>" in html

    def test_generate_pdf_file(self, tmp_path):
        from hermes.utils.pdf_generator import generate_pdf

        out = generate_pdf("# Test Resume\n\nHello world\n", tmp_path / "r.pdf")
        assert out.exists()
        if out.suffix == ".pdf":
            assert out.read_bytes()[:5] == b"%PDF-"

    def test_weasyprint_available(self):
        try:
            import weasyprint  # noqa: F401
        except Exception as exc:  # noqa: BLE001 — may fail on OS libs
            pytest.skip(f"WeasyPrint import failed on this system: {exc}")


# --------------------------------------------------------- full pipeline e2e


class TestPipelineEndToEnd:
    def test_offline_run_with_rag(self, tmp_path, monkeypatch, resume_md, profile):
        """Full pipeline: parse -> index -> analyze -> score -> tailor -> artifacts."""
        from hermes.agents.cover_letter import CoverLetterAgent
        from hermes.agents.fit_scorer import FitScorer
        from hermes.agents.resume_tailor import ResumeTailor

        parsed = parse_resume(resume_md, profile)
        lib = ExperienceLibrary(use_chroma=False)
        lib.index_resume(parsed)

        job = JobPosting(
            job_id="e2e-1",
            title="LLM Engineer",
            company="AgentCo",
            description=(
                "Build LLM agents and RAG pipelines. Python, LangGraph, "
                "FastAPI required. Multi-agent systems. Remote."
            ),
        )
        analysis = heuristic_analyze(job)
        scored = FitScorer(profile, min_fit_score=0.2).score(job, analysis, parsed)
        assert scored.fit_score > 0

        tailored = ResumeTailor(router=None, library=lib).tailor(parsed, job, analysis)
        assert tailored.validated  # base-resume passthrough is always clean
        letter = CoverLetterAgent(profile, router=None).generate(analysis, tailored)
        assert "AgentCo" in letter.text or "Hiring" in letter.text
