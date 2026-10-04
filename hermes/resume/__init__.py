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

from hermes.resume.composer import compose_ir
from hermes.resume.coverage import (
    CoverageItem,
    requirement_covers,
    select_by_marginal_coverage,
)
from hermes.resume.evidence import (
    STRENGTH_BASE,
    Evidence,
    estimate_strength,
    evidence_from_snapshot,
    extract_dates,
    extract_metrics,
)
from hermes.resume.extract import (
    extract_requirements,
    requirements_from_keywords,
)
from hermes.resume.gate import GateReport, coverage_ratio, gate
from hermes.resume.ir import (
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
from hermes.resume.planner import (
    PAGE_LINE_BUDGET,
    ResumePlan,
    ir_from_selection,
    plan_resume,
)
from hermes.resume.qa import PdfQAReport, qa_pdf, render_pdf_with_qa
from hermes.resume.repair import compress_to_fit, repair_step
from hermes.resume.render import estimate_md_lines, render_markdown
from hermes.resume.requirements import (
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
