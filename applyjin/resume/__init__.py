"""Resume Engine — evidence-grounded, one-page resume construction.

Pipeline (structured ResumeIR fork):
    extract.py     JD -> Requirement[] (LLM first, keyword fallback)
    coverage.py    greedy marginal-coverage selection over requirements
    evidence.py    master snapshot -> Evidence pool with strength
    ir.py          ResumeIR — the structured resume flowing through
    planner.py     section order, bullet priority, one-page budget
    composer.py    LLM rephrases bullets; provenance fields frozen
    render.py      deterministic ResumeIR -> Markdown (ATS sections)
    repair.py      one-page compression hierarchy for markdown output
    gate.py        provenance + claim support + budget + coverage report
    qa.py          physical PDF check: pages, text, anchors + repair loop
"""

from applyjin.resume.composer import compose_ir
from applyjin.resume.coverage import (
    CoverageItem,
    requirement_covers,
    select_by_marginal_coverage,
)
from applyjin.resume.evidence import (
    STRENGTH_BASE,
    Evidence,
    estimate_strength,
    evidence_from_snapshot,
    extract_dates,
    extract_metrics,
)
from applyjin.resume.extract import (
    extract_requirements,
    requirements_from_keywords,
)
from applyjin.resume.gate import GateReport, coverage_ratio, gate
from applyjin.resume.ir import (
    CertificationIR,
    EducationIR,
    ExperienceIR,
    HeaderIR,
    ProjectIR,
    ResumeBullet,
    ResumeIR,
    SkillsIR,
    SummaryIR,
    estimate_lines,
)
from applyjin.resume.planner import (
    PAGE_LINE_BUDGET,
    ResumePlan,
    ir_from_selection,
    plan_resume,
)
from applyjin.resume.qa import PdfQAReport, qa_pdf, render_pdf_with_qa
from applyjin.resume.repair import compress_to_fit, repair_step
from applyjin.resume.render import estimate_md_lines, render_markdown
from applyjin.resume.requirements import (
    ImportanceWeights,
    Requirement,
    RequirementCategory,
    compute_importance,
    make_requirement,
    normalize_skill,
)

__all__ = [
    "CertificationIR",
    "CoverageItem",
    "EducationIR",
    "Evidence",
    "ExperienceIR",
    "GateReport",
    "HeaderIR",
    "ImportanceWeights",
    "PAGE_LINE_BUDGET",
    "PdfQAReport",
    "ProjectIR",
    "Requirement",
    "RequirementCategory",
    "ResumeBullet",
    "ResumeIR",
    "ResumePlan",
    "STRENGTH_BASE",
    "SkillsIR",
    "SummaryIR",
    "compose_ir",
    "compress_to_fit",
    "compute_importance",
    "coverage_ratio",
    "estimate_lines",
    "estimate_md_lines",
    "estimate_strength",
    "evidence_from_snapshot",
    "extract_dates",
    "extract_metrics",
    "extract_requirements",
    "gate",
    "ir_from_selection",
    "make_requirement",
    "normalize_skill",
    "plan_resume",
    "qa_pdf",
    "render_markdown",
    "render_pdf_with_qa",
    "repair_step",
    "requirement_covers",
    "requirements_from_keywords",
    "select_by_marginal_coverage",
]
