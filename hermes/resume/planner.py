"""Deterministic planner: section order, bullet priority, page budget.

The planner owns what the LLM never may: section order (ATS-safe
standard), bullet priority (JD importance first), and the one-page line
budget. `ir_from_selection` lifts the selection engine's output into a
ResumeIR with full provenance; `plan_resume` reorders and fits it to the
page budget by dropping the lowest-importance bullets first.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from hermes.resume.coverage import requirement_covers
from hermes.resume.ir import (
    WORDS_PER_LINE,
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
from hermes.resume.requirements import Requirement

logger = logging.getLogger("hermes.resume.planner")

# One page of a standard single-column resume at normal font size.
PAGE_LINE_BUDGET = 46

# Fixed-section caps: content that must never crowd out the bullets that
# actually win interviews (a master DB with 64 certifications would
# otherwise consume the whole page).
MAX_CERTIFICATIONS = 3
MAX_EDUCATION = 2
MAX_SUMMARY_LINES = 4

SECTION_ORDER = [
    "header",
    "summary",
    "experience",
    "projects",
    "skills",
    "education",
    "certifications",
]


class ResumePlan(BaseModel):
    """Planned resume: fitted IR plus the planner's audit trail."""

    ir: ResumeIR
    section_order: list[str] = Field(default_factory=lambda: list(SECTION_ORDER))
    page_line_budget: int = PAGE_LINE_BUDGET
    estimated_lines: int = 0
    dropped: list[str] = Field(default_factory=list)
    over_budget: bool = False


def _bullets_from(entry: dict, kind: str, requirements: list[Requirement]) -> list[ResumeBullet]:
    prefix = "exp" if kind == "experience" else "prj"
    bullets: list[ResumeBullet] = []
    for index, text in enumerate(entry.get("bullets") or []):
        text = str(text).strip()
        if not text:
            continue
        covering = [r.id for r in requirements if requirement_covers(r, text)]
        importance = max(
            (r.importance for r in requirements if r.id in covering), default=0.0
        )
        bullets.append(
            ResumeBullet(
                text=text,
                evidence_ids=[f"{prefix}-{entry['id']}-b{index}"],
                requirement_ids=covering,
                importance=round(importance, 3),
                space_cost=max(1, estimate_lines(text)),
            )
        )
    return bullets


def ir_from_selection(
    snapshot: dict,
    selected_experience_ids: list[int],
    selected_project_ids: list[int],
    requirements: Optional[list[Requirement]] = None,
    skills: Optional[list[str]] = None,
) -> ResumeIR:
    """Lift master snapshot + selection into a provenance-carrying ResumeIR."""
    requirements = list(requirements or [])
    profile = snapshot.get("profile") or {}

    ir = ResumeIR(
        header=HeaderIR(
            name=profile.get("full_name", ""),
            headline=profile.get("headline", ""),
            location=profile.get("location", ""),
            email=profile.get("email", ""),
            linkedin=profile.get("linkedin", ""),
            github=profile.get("github", ""),
            website=profile.get("website", ""),
        ),
        education=[
            EducationIR(
                degree=e.get("degree", ""),
                institution=e.get("institution", ""),
                start_date=e.get("start_date", ""),
                end_date=e.get("end_date", ""),
                detail=e.get("details", ""),
            )
            for e in snapshot.get("education") or []
        ],
        certifications=[
            CertificationIR(
                name=c.get("name", ""),
                issuer=c.get("issuer", ""),
                date=c.get("year", ""),
            )
            for c in snapshot.get("certifications") or []
        ],
    )

    summary_bits = [profile.get("headline", ""), profile.get("summary", "")]
    summary_text = " — ".join(b for b in summary_bits if b) or ""
    if summary_text:
        ir.summary = SummaryIR(text=summary_text)

    # Skills grouped by master category, order preserved from selection.
    chosen = set(skills or [])
    if chosen:
        owner: dict[str, str] = {}
        for category, names in (snapshot.get("skills") or {}).items():
            for name in names:
                owner[name] = category
        categories: dict[str, list[str]] = {}
        for name in skills or []:
            if name not in chosen:
                continue
            categories.setdefault(owner.get(name, "other"), []).append(name)
        ir.skills = SkillsIR(categories=categories)

    for entry in snapshot.get("experiences") or []:
        if entry["id"] not in selected_experience_ids:
            continue
        ir.experience.append(
            ExperienceIR(
                id=str(entry["id"]),
                title=entry.get("title", ""),
                organization=entry.get("organization", ""),
                location=entry.get("location", ""),
                start_date=entry.get("start_date", ""),
                end_date=entry.get("end_date", ""),
                description=entry.get("description", ""),
                bullets=_bullets_from(entry, "experience", requirements),
            )
        )
    for entry in snapshot.get("projects") or []:
        if entry["id"] not in selected_project_ids:
            continue
        ir.projects.append(
            ProjectIR(
                id=str(entry["id"]),
                name=entry.get("name", ""),
                tech=entry.get("tech", ""),
                link=entry.get("link", ""),
                description=entry.get("description", ""),
                bullets=_bullets_from(entry, "project", requirements),
            )
        )
    return ir


def _drop_slots(ir: ResumeIR) -> list[tuple]:
    """(rank_key, section, entry_index, bullet_index, space) per bullet.

    Lowest rank first: least important, then projects before experiences
    (experience carries more weight on a resume), then later entries and
    later bullets.
    """
    slots: list[tuple] = []
    for section, entries in (("project", ir.projects), ("experience", ir.experience)):
        for entry_index, entry in enumerate(entries):
            for bullet_index, bullet in enumerate(entry.bullets):
                rank = (bullet.importance, -1 if section == "project" else 1,
                        -entry_index, -bullet_index)
                slots.append((rank, section, entry_index, bullet_index, bullet.space_cost))
    slots.sort(key=lambda s: s[0])
    return slots


def _cap_fixed_sections(
    ir: ResumeIR, requirements: list[Requirement]
) -> list[str]:
    """Trim sections that have no right to crowd out the bullets.

    Certifications: JD-covered names first, then master order, capped.
    Education: earliest entries kept. Summary: cut at a word boundary.
    """
    dropped: list[str] = []
    if len(ir.certifications) > MAX_CERTIFICATIONS:
        covered = [
            any(requirement_covers(r, cert.name) for r in requirements)
            for cert in ir.certifications
        ]
        order = sorted(
            range(len(ir.certifications)),
            key=lambda i: (not covered[i], i),
        )
        keep = sorted(order[:MAX_CERTIFICATIONS])
        for i in range(len(ir.certifications)):
            if i not in keep:
                dropped.append(f"certifications-{i}")
        ir.certifications = [ir.certifications[i] for i in keep]
    if len(ir.education) > MAX_EDUCATION:
        for i in range(MAX_EDUCATION, len(ir.education)):
            dropped.append(f"education-{i}")
        ir.education = ir.education[:MAX_EDUCATION]
    if ir.summary and ir.summary.text:
        max_words = MAX_SUMMARY_LINES * WORDS_PER_LINE
        words = ir.summary.text.split()
        if len(words) > max_words:
            ir.summary.text = " ".join(words[:max_words])
            dropped.append("summary-trimmed")
    return dropped


def plan_resume(
    ir: ResumeIR,
    requirements: Optional[list[Requirement]] = None,
    page_lines: int = PAGE_LINE_BUDGET,
) -> ResumePlan:
    """Reorder bullets by JD importance and fit everything to one page.

    Fixed sections are capped first (certifications/education/summary),
    then the lowest-importance bullets are dropped first (projects before
    experiences on ties). Header, skills, and the capped fixed sections
    are never dropped. If fixed sections alone exceed the budget the plan
    is returned flagged `over_budget` for the quality gate.
    """
    requirements = list(requirements or [])
    dropped = _cap_fixed_sections(ir, requirements)

    # Bullet priority: importance desc, original order on ties (stable).
    for entries in (ir.experience, ir.projects):
        for entry in entries:
            entry.bullets.sort(key=lambda b: -b.importance)

    # Drop bullets until the one-page budget holds.
    while ir.total_space() > page_lines:
        slots = _drop_slots(ir)
        if not slots:
            break
        _, section, entry_index, bullet_index, _ = slots[0]
        entries = ir.projects if section == "project" else ir.experience
        entry = entries[entry_index]
        bullet = entry.bullets.pop(bullet_index)
        dropped.append(f"{section}-{entry.id}:b{bullet_index}")
        if not entry.bullets:
            entries.pop(entry_index)

    estimated = ir.total_space()
    return ResumePlan(
        ir=ir,
        section_order=list(SECTION_ORDER),
        page_line_budget=page_lines,
        estimated_lines=estimated,
        dropped=dropped,
        over_budget=estimated > page_lines,
    )
