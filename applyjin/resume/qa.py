"""PDF QA: the physical one-page gate.

The planner's line budget is an estimate; this module checks the actual
compiled PDF — page count, extractable text, and identity/section
anchors — and drives the markdown repair loop until the PDF passes (or
the compression hierarchy is exhausted). Never shrinks fonts, never
blocks silently: callers receive the full report either way.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger("applyjin.resume.qa")

# Sections every tailored resume must expose to an ATS parser.
DEFAULT_REQUIRED_SECTIONS = ("Summary", "Experience", "Skills")

# Extracted text shorter than this is not a usable resume.
MIN_EXTRACTABLE_CHARS = 40


class PdfQAReport(BaseModel):
    """Result of checking one compiled resume PDF."""

    pages: int = 0
    extractable: bool = False
    text_chars: int = 0
    missing: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    repairs: int = 0
    passed: bool = False

    def header_json(self) -> str:
        """Compact JSON for the X-Resume-QA response header."""
        return json.dumps(
            {
                "pages": self.pages,
                "passed": self.passed,
                "repairs": self.repairs,
                "missing": self.missing,
                "issues": self.issues,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )


def qa_pdf(
    pdf_path: Path | str,
    *,
    name: str = "",
    email: str = "",
    sections: Sequence[str] = DEFAULT_REQUIRED_SECTIONS,
) -> PdfQAReport:
    """Check a compiled PDF: one page, extractable text, anchors present."""
    report = PdfQAReport()
    path = Path(pdf_path)
    if not path.exists():
        report.issues.append("PDF not found")
        return report

    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            report.pages = len(pdf.pages)
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:  # unreadable/corrupt PDF
        report.issues.append(f"PDF unreadable: {exc}")
        return report

    report.text_chars = len(text.strip())
    report.extractable = report.text_chars >= MIN_EXTRACTABLE_CHARS
    # Whitespace-normalized so wrapped names still match.
    flat = " ".join(text.split())
    lowered = flat.lower()

    if report.pages != 1:
        report.issues.append(f"page count {report.pages} != 1")
    if not report.extractable:
        report.issues.append("no extractable text")

    if name:
        # A profile name may carry an import suffix ("NAME — MASTER CV")
        # or a title after a dash/pipe; match on any segment so a clean
        # rendering of the real name still counts.
        candidates = [name] + re.split(r"\s*[—–|]\s*|\s+-\s+", name)
        if not any(
            len(segment.strip()) >= 3 and segment.strip().lower() in lowered
            for segment in candidates
        ):
            report.missing.append("name")
    if email and email.strip().lower() not in lowered:
        report.missing.append("email")
    for section in sections:
        if section.strip().lower() not in lowered:
            report.missing.append(f"section:{section.strip()}")

    report.passed = (
        report.pages == 1
        and report.extractable
        and not report.missing
        and not report.issues
    )
    return report


def render_pdf_with_qa(
    markdown_text: str,
    out_path: Path | str,
    *,
    name: str = "",
    email: str = "",
    sections: Sequence[str] = DEFAULT_REQUIRED_SECTIONS,
    max_repairs: int = 12,
) -> tuple[Optional[Path], PdfQAReport, str]:
    """Compile -> QA -> repair -> recompile until the PDF passes.

    Returns (pdf_path | None, report, final_markdown). `pdf_path` is None
    only when LaTeX compilation failed outright; otherwise the best PDF
    produced is returned together with its report (which may be a failure
    if repairs were exhausted — callers surface that, they don't hide it).
    """
    from applyjin.resume.repair import repair_step
    from applyjin.utils.latex_generator import compile_tex, markdown_to_latex

    current_md = markdown_text
    for attempt in range(max_repairs + 1):
        pdf_path = compile_tex(markdown_to_latex(current_md), Path(out_path))
        if pdf_path is None:
            return None, PdfQAReport(issues=["LaTeX compile failed"]), current_md
        report = qa_pdf(pdf_path, name=name, email=email, sections=sections)
        report.repairs = attempt
        if report.passed:
            return pdf_path, report, current_md
        if report.pages == 1:
            # Remaining failures (missing anchors, extractability) are not
            # fixable by dropping content — stop wasting compiles.
            return pdf_path, report, current_md
        if attempt == max_repairs:
            break
        new_md, changed = repair_step(current_md)
        if not changed:
            return pdf_path, report, current_md
        logger.info(
            "PDF QA failed (%s) — repair step %d",
            "; ".join(report.issues + report.missing),
            attempt + 1,
        )
        current_md = new_md
    logger.warning("PDF QA: repairs exhausted without a passing PDF")
    return Path(out_path), report, current_md
