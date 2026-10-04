"""Resume Engine — evidence-grounded, one-page resume construction.

Pipeline (structured ResumeIR fork):
    extract.py     JD -> Requirement[] (LLM first, keyword fallback)
    coverage.py    greedy marginal-coverage selection over requirements
    evidence.py    master snapshot -> Evidence pool with strength
    ir.py          ResumeIR — the structured resume flowing through
    planner.py     section order, bullet priority, one-page budget
    composer.py    LLM rephrases bullets; provenance fields frozen
    render.py      deterministic ResumeIR -> Markdown (ATS sections)
    gate.py        provenance + claim support + budget + coverage report
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
from hermes.resume.render import render_markdown
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
    "compute_importance",
    "coverage_ratio",
    "estimate_lines",
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
    "render_markdown",
    "requirement_covers",
    "requirements_from_keywords",
    "select_by_marginal_coverage",
]
