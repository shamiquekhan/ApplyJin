"""LaTeX generation + cover-letter name tests."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from hermes.agents.cover_letter import _scrub_placeholders
from hermes.utils.latex_generator import (
    compile_tex,
    cover_letter_to_latex,
    latex_bundle,
    latex_escape,
    markdown_to_latex,
)


SAMPLE_MD = """# SHAMIQUE KHAN

Etawah, Uttar Pradesh, India | shamique@example.com | linkedin.com/in/shamique-khan

## Professional Summary

AI Engineer with 40+ systems shipped. Python & RAG focus.

## Relevant Skills

- Agentic AI: LangGraph, LangChain, multi-agent systems
- Backend: Python, FastAPI, Docker

## Experience

### AI Engineer Intern | Suproc | Jul 2026 - Present

- Architected 4+ multi-model LLM agents in Python
- Shipped institutional applications now in active use

### Founder | Scandium Labs | May 2026 - Present

- Directed physics-informed GNN development

## Education

- B.Tech CSE | VIT Bhopal | 2025 - 2029

## Certifications

Oracle OCI Generative AI Professional
"""


class TestLatexEscape:
    def test_special_chars(self):
        assert latex_escape("100% of $5 & #3 _x~y^z") == (
            "100\\% of \\$5 \\& \\#3 \\_x\\textasciitilde{}y\\textasciicircum{}z"
        )

    def test_no_raw_slash_injection(self):
        assert latex_escape(r"\documentclass{evil}") == (
            "\\textbackslash{}documentclass\\{evil\\}"
        )


class TestMarkdownToLatex:
    def test_structure(self):
        tex = markdown_to_latex(SAMPLE_MD)
        assert "\\documentclass{resume}" in tex
        assert "\\name{SHAMIQUE KHAN}" in tex
        # Sections are rSection with uppercase titles
        assert "\\begin{rSection}{PROFESSIONAL SUMMARY}" in tex
        assert "\\begin{rSection}{EXPERIENCE}" in tex
        assert "\\begin{rSection}{EDUCATION}" in tex
        # Sub-headings become entry headers, NOT sections
        assert "AI Engineer Intern" in tex
        assert tex.count("\\begin{rSection}") == 5  # summary, skills, exp, edu, certs
        # Skills render as tabular rows
        assert "Agentic AI" in tex and "LangGraph" in tex

    def test_empty_entries_skipped(self):
        tex = markdown_to_latex(SAMPLE_MD)
        assert "\\begin{rSubsection}{}{}{}{}\n\\end{rSubsection}" not in tex

    def test_no_h3_creates_sections(self):
        tex = markdown_to_latex(SAMPLE_MD)
        import re

        titles = re.findall(r"\\begin\{rSection\}\{([^}]+)\}", tex)
        assert "AI ENGINEER INTERN" not in [t.upper() for t in titles]


class TestCompile:
    def test_compiles_sample(self, tmp_path):
        if shutil.which("pdflatex") is None:
            pytest.skip("pdflatex not installed")
        tex = markdown_to_latex(SAMPLE_MD)
        pdf = compile_tex(tex, tmp_path / "out.pdf")
        assert pdf is not None
        assert pdf.read_bytes()[:5] == b"%PDF-"
        assert pdf.stat().st_size > 5000

    def test_compiles_real_cv(self, tmp_path):
        if shutil.which("pdflatex") is None:
            pytest.skip("pdflatex not installed")
        cv = Path("data/base_resume.md")
        if not cv.exists():
            pytest.skip("base resume not present")
        tex = markdown_to_latex(cv.read_text(encoding="utf-8"))
        pdf = compile_tex(tex, tmp_path / "cv.pdf")
        assert pdf is not None
        assert pdf.read_bytes()[:5] == b"%PDF-"

    def test_bad_tex_returns_none(self, tmp_path):
        if shutil.which("pdflatex") is None:
            pytest.skip("pdflatex not installed")
        broken = "\\documentclass{resume}\n\\begin{document}\n\\undefinedmacro\n\\end{document}"
        assert compile_tex(broken, tmp_path / "bad.pdf") is None

    def test_cover_letter_compiles(self, tmp_path):
        if shutil.which("pdflatex") is None:
            pytest.skip("pdflatex not installed")
        tex = cover_letter_to_latex(
            "Dear Team,\n\nI am excited. 100% motivated.\n\nSincerely,\n\nJane",
            name="Shamique Khan",
            contact="shamique@example.com",
        )
        pdf = compile_tex(tex, tmp_path / "letter.pdf")
        assert pdf is not None and pdf.read_bytes()[:5] == b"%PDF-"


class TestCoverLetterTemplate:
    LETTER = (
        "Dear Hiring Team at AgentCorp,\n\n"
        "I am writing to express my strong interest in the AI Engineer "
        "position at AgentCorp. With a robust background in building "
        "production systems, I am excited about the opportunity.\n\n"
        "I have deployed over four production-grade AI agents leveraging "
        "multi-model LLM workflows and prompt engineering.\n\n"
        "Sincerely,\n\nShamique Khan"
    )

    def test_matches_resume_style(self):
        """Same documentclass/banner as the resume — one packet look."""
        tex = cover_letter_to_latex(
            self.LETTER, name="Shamique Khan",
            contact="Etawah, UP | email",
        )
        assert "\\documentclass{resume}" in tex
        assert "\\MakeNameHeader" in tex          # same name banner
        assert "\\name{Shamique Khan}" in tex
        assert "\\address{Etawah, UP | email}" in tex
        assert "\\hrule" in tex                   # matching rule accent
        assert "\\today" in tex                   # right-aligned date

    def test_parses_letter_parts(self):
        tex = cover_letter_to_latex(
            self.LETTER, name="Shamique Khan", contact="email"
        )
        assert "Dear Hiring Team at AgentCorp," in tex
        assert "Sincerely," in tex
        # signature comes from the letter's own sign-off (not the header arg)
        assert "{\\bfseries Shamique Khan}" in tex
        # body paragraphs kept, salutation/closing not duplicated in body
        assert tex.count("Dear Hiring Team") == 1
        assert tex.count("Sincerely") == 1

    def test_closing_variants_recognized(self):
        for closing in ("Best regards,", "Warm regards", "Yours sincerely,",
                        "Kind regards,", "Respectfully yours,"):
            letter = f"Dear Team,\n\nBody text here.\n\n{closing}\n\nJane Doe"
            tex = cover_letter_to_latex(letter, name="X", contact="c")
            assert closing.rstrip(",;:").lower().split()[0].lower() in tex.lower()
            assert "{\\bfseries Jane Doe}" in tex

    def test_signature_falls_back_to_name(self):
        """No sign-off in the letter -> signature is the passed name."""
        letter = "Dear Team,\n\nBody only, no closing."
        tex = cover_letter_to_latex(letter, name="Fallback Name", contact="c")
        assert "{\\bfseries Fallback Name}" in tex
        assert "Sincerely," in tex  # default closing

    def test_escapes_letter_content(self):
        letter = "Dear Team,\n\nI know LaTeX & 100% of Python_ basics.\n\nSincerely,\n\nJ"
        tex = cover_letter_to_latex(letter, name="J", contact="c")
        assert "\\&" in tex and "100\\%" in tex and "Python\\_" in tex
        # no raw unescaped specials survive
        assert "\\& 100" in tex

    def test_end_to_end_compile_matches_resume_look(self, tmp_path):
        if shutil.which("pdflatex") is None:
            pytest.skip("pdflatex not installed")
        resume_tex = markdown_to_latex(SAMPLE_MD)
        letter_tex = cover_letter_to_latex(
            self.LETTER, name="SHAMIQUE KHAN",
            contact="Etawah, UP | email",
        )
        # Both artifacts share the class and banner
        for tex in (resume_tex, letter_tex):
            assert "\\documentclass{resume}" in tex
        r = compile_tex(resume_tex, tmp_path / "r.pdf")
        l = compile_tex(letter_tex, tmp_path / "l.pdf")
        assert r and l
        assert r.read_bytes()[:5] == l.read_bytes()[:5] == b"%PDF-"


class TestLatexBundle:
    def test_zip_contains_cls_tex_readme(self, tmp_path):
        tex = markdown_to_latex(SAMPLE_MD)
        bundle = latex_bundle(tex, tmp_path / "src.zip")
        with zipfile.ZipFile(bundle) as zf:
            names = set(zf.namelist())
        assert {"resume.cls", "resume.tex", "README.txt"} == names
        assert "documentclass{resume}" in zipfile.ZipFile(bundle).read("resume.tex").decode()


class TestCoverLetterName:
    def test_placeholder_scrubbed(self):
        text = "Great letter.\n\nBest regards,\n[Your Name]"
        cleaned = _scrub_placeholders(text, "Shamique Khan")
        assert "Shamique Khan" in cleaned
        assert "[Your Name]" not in cleaned

    def test_variant_placeholders(self):
        for variant in ("[Name]", "[name]", "Your Name", "[YourName]"):
            cleaned = _scrub_placeholders(f"Regards,\n{variant}", "Jane")
            assert "Jane" in cleaned

    def test_no_name_no_scrub(self):
        text = "Regards, [Your Name]"
        assert _scrub_placeholders(text, "") == text

    def test_llm_letter_signed_with_name(self):
        """The LLM path must pass + scrub the name (prompt contract)."""
        from hermes.config import Identity, Profile
        from hermes.agents.cover_letter import CoverLetterAgent
        from hermes.models import JobAnalysis

        captured = {}

        class Router:
            def complete(self, prompt, system=""):
                captured["prompt"] = prompt
                from hermes.models import LLMResponse

                return LLMResponse(
                    text="Body.\n\nBest regards,\n[Your Name]",
                    model="fake", provider="fake",
                )

        profile = Profile(
            identity=Identity(name="Shamique Khan", email="x@y.z")
        )
        analysis = JobAnalysis(
            job_id="j", title="AI Engineer", company="Acme",
            required_skills=["Python"],
        )

        class Holder:
            source_bullets = ["Built RAG systems"]

        agent = CoverLetterAgent(profile, router=Router())
        letter = agent.generate(analysis, Holder())
        assert "Shamique Khan" in letter.text
        assert "[Your Name]" not in letter.text
        # the prompt carried the name (rule 7 + CANDIDATE block)
        assert "Shamique Khan" in captured["prompt"]

    def test_web_pipeline_extracts_name_from_resume_header(self):
        from hermes.web.pipeline import cover_letter as web_cover

        class Router:
            def complete(self, prompt, system=""):
                from hermes.models import LLMResponse

                return LLMResponse(
                    text="Body.\n\nBest regards,\n[Your Name]",
                    model="fake", provider="fake",
                )

        resume = {
            "raw_text": (
                "# SHAMIQUE KHAN\n\n"
                "Etawah, UP | email\n\n## Experience\n\n- Built agents"
            )
        }
        jd = {"id": "1", "title": "AI Eng", "company": "Acme",
              "content": "Python RAG role", "keywords": None}
        letter = web_cover(resume, jd, "## Experience\n\n- Built agents", Router())
        assert "Shamique Khan" in letter or "SHAMIQUE KHAN" in letter
        assert "[Your Name]" not in letter
