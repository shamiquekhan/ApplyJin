"""PDF QA: page count, extractability, anchors, and the repair loop."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hermes.resume.qa import PdfQAReport, qa_pdf, render_pdf_with_qa

GOOD_MD = """# Jane Doe
jane@example.com | linkedin.com/in/jane

## Summary
AI engineer building RAG pipelines with Python.

## Experience
### SWE | Acme | 2020 - Present
- Built ranking models improving accuracy 15%

## Skills
Python, FastAPI
"""

_NEEDS_PDFLATEX = shutil.which("pdflatex") is None


class TestPdfQAReport:
    def test_header_json_round_trips(self):
        report = PdfQAReport(
            pages=1, passed=True, repairs=2, missing=[], issues=[]
        )
        data = json.loads(report.header_json())
        assert data == {
            "pages": 1, "passed": True, "repairs": 2,
            "missing": [], "issues": [],
        }
        assert " " not in report.header_json()  # header-safe separators

    def test_missing_pdf_fails_cleanly(self, tmp_path: Path):
        report = qa_pdf(tmp_path / "nope.pdf")
        assert report.passed is False
        assert "PDF not found" in report.issues


@pytest.mark.skipif(_NEEDS_PDFLATEX, reason="pdflatex not installed")
class TestQaPdfReal:
    def test_good_resume_passes(self, tmp_path: Path):
        from hermes.utils.latex_generator import compile_tex, markdown_to_latex

        pdf = compile_tex(markdown_to_latex(GOOD_MD), tmp_path / "good.pdf")
        assert pdf is not None
        report = qa_pdf(pdf, name="Jane Doe", email="jane@example.com")
        assert report.pages == 1
        assert report.extractable is True
        assert report.missing == []
        assert report.passed is True, report.issues

    def test_two_page_resume_fails(self, tmp_path: Path):
        from hermes.utils.latex_generator import compile_tex, markdown_to_latex

        bullets = "\n".join(
            f"- Architected and shipped metric-{i} improvements across the platform"
            for i in range(80)
        )
        md = (
            "# Jane Doe\njane@example.com\n\n"
            "## Experience\n### SWE | Acme | 2020 - Present\n" + bullets + "\n"
        )
        pdf = compile_tex(markdown_to_latex(md), tmp_path / "long.pdf")
        assert pdf is not None
        report = qa_pdf(pdf, name="Jane Doe", email="jane@example.com")
        assert report.pages >= 2
        assert report.passed is False
        assert any("page count" in issue for issue in report.issues)

    def test_missing_anchors_reported(self, tmp_path: Path):
        from hermes.utils.latex_generator import compile_tex, markdown_to_latex

        pdf = compile_tex(markdown_to_latex(GOOD_MD), tmp_path / "anchors.pdf")
        assert pdf is not None
        report = qa_pdf(
            pdf, name="Someone Else", email="other@x.co",
            sections=("Summary", "Experience", "Skills", "Projects"),
        )
        assert "name" in report.missing
        assert "email" in report.missing
        assert "section:Projects" in report.missing
        assert report.passed is False

    def test_profile_name_suffix_still_matches(self, tmp_path: Path):
        # Profile names can carry import suffixes ("Jane Doe — MASTER CV");
        # a clean rendering of the real name must still count as present.
        from hermes.utils.latex_generator import compile_tex, markdown_to_latex

        pdf = compile_tex(markdown_to_latex(GOOD_MD), tmp_path / "suffix.pdf")
        assert pdf is not None
        report = qa_pdf(
            pdf, name="Jane Doe — MASTER CV", email="jane@example.com"
        )
        assert "name" not in report.missing
        assert report.passed is True, (report.missing, report.issues)


class TestRenderPdfWithQa:
    def test_repairs_until_pass(self, tmp_path: Path, monkeypatch):
        import hermes.resume.qa as qa_mod
        import hermes.utils.latex_generator as lg

        captured: dict = {}

        def fake_compile(tex, out_path, cls_source=None):
            captured["tex"] = tex
            out = Path(out_path)
            out.write_bytes(b"%PDF-1.4 fake")
            return out

        def fake_qa(path, *, name="", email="", sections=()):
            markers = captured.get("tex", "").count("MARKERBULLET")
            ok = markers <= 5
            return PdfQAReport(
                pages=1 if ok else 2,
                extractable=True,
                passed=ok,
                issues=[] if ok else ["page count 2 != 1"],
            )

        monkeypatch.setattr(lg, "compile_tex", fake_compile)
        monkeypatch.setattr(qa_mod, "qa_pdf", fake_qa)

        bullets = "\n".join(
            f"- MARKERBULLET detail number {i}" for i in range(10)
        )
        md = (
            "# Jane Doe\njane@example.com\n\n"
            "## Experience\n### SWE | Acme | 2020 - Present\n" + bullets + "\n"
        )
        pdf, report, final_md = render_pdf_with_qa(
            md, tmp_path / "loop.pdf", max_repairs=12
        )
        assert pdf is not None
        assert report.passed is True
        assert report.repairs == 5  # one bullet dropped per step
        assert final_md.count("MARKERBULLET") == 5
        assert final_md.count("MARKERBULLET") < md.count("MARKERBULLET")

    def test_compile_failure_returns_none(self, tmp_path: Path, monkeypatch):
        import hermes.utils.latex_generator as lg

        monkeypatch.setattr(lg, "compile_tex", lambda *a, **k: None)
        pdf, report, final_md = render_pdf_with_qa(
            GOOD_MD, tmp_path / "fail.pdf"
        )
        assert pdf is None
        assert report.passed is False
        assert "LaTeX compile failed" in report.issues
        assert final_md == GOOD_MD  # nothing mutated

    def test_exhausted_repairs_returns_best_effort(self, tmp_path: Path, monkeypatch):
        import hermes.resume.qa as qa_mod
        import hermes.utils.latex_generator as lg

        def fake_compile(tex, out, cls=None):
            path = Path(out)
            path.write_bytes(b"%PDF")
            return path

        monkeypatch.setattr(lg, "compile_tex", fake_compile)
        # QA never passes: one huge resume, repairs capped at 2.
        monkeypatch.setattr(
            qa_mod, "qa_pdf",
            lambda *a, **k: PdfQAReport(pages=2, extractable=True, passed=False,
                                        issues=["page count 2 != 1"]),
        )
        bullets = "\n".join(f"- bullet {i} here" for i in range(30))
        md = (
            "# Jane Doe\n\n## Experience\n### SWE | Acme\n" + bullets + "\n"
        )
        pdf, report, final_md = render_pdf_with_qa(
            md, tmp_path / "best.pdf", max_repairs=2
        )
        assert pdf is not None          # best effort, not None
        assert report.passed is False   # failure is surfaced, not hidden
        assert report.repairs == 2
        assert final_md != md           # repairs were applied
