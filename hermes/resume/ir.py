"""ResumeIR: the structured resume the pipeline flows through.

Pipeline direction (ResumeIR fork of the upgrade plan):

    evidence -> ResumeIR -> LLM edits fields -> ResumeIR
    -> deterministic renderer -> Markdown / LaTeX

Every bullet carries provenance (evidence_ids, requirement_ids) so claim
verification, coverage matrices, and the quality gate can audit it. The
planner owns section order and budgets; the LLM never does.
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Rough words per rendered resume line at the standard LaTeX template size.
WORDS_PER_LINE = 11


def estimate_lines(text: str, words_per_line: int = WORDS_PER_LINE) -> int:
    """Space cost of a bullet in rendered lines (>=1 when non-empty)."""
    words = len(text.split())
    if not words:
        return 0
    return max(1, math.ceil(words / words_per_line))


class ResumeBullet(BaseModel):
    """One bullet with full provenance — the atomic unit of the resume."""

    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    importance: float = 0.0
    space_cost: int = 1


class HeaderIR(BaseModel):
    name: str = ""
    headline: str = ""
    location: str = ""
    email: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class SummaryIR(BaseModel):
    text: str = ""
    requirement_ids: list[str] = Field(default_factory=list)


class SkillsIR(BaseModel):
    categories: dict[str, list[str]] = Field(default_factory=dict)


class ExperienceIR(BaseModel):
    id: str = ""
    title: str = ""
    organization: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)


class ProjectIR(BaseModel):
    id: str = ""
    name: str = ""
    tech: str = ""
    link: str = ""
    description: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)


class EducationIR(BaseModel):
    degree: str = ""
    institution: str = ""
    start_date: str = ""
    end_date: str = ""
    detail: str = ""


class CertificationIR(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class ResumeIR(BaseModel):
    """The resume as data. Sections are explicit; rendering is deterministic."""

    header: HeaderIR = Field(default_factory=HeaderIR)
    summary: Optional[SummaryIR] = None
    skills: SkillsIR = Field(default_factory=SkillsIR)
    experience: list[ExperienceIR] = Field(default_factory=list)
    projects: list[ProjectIR] = Field(default_factory=list)
    education: list[EducationIR] = Field(default_factory=list)
    certifications: list[CertificationIR] = Field(default_factory=list)

    @field_validator("header", mode="before")
    @classmethod
    def _header_from_plain_string(cls, value):
        if isinstance(value, str):
            return {"name": value}
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def _summary_from_plain_string(cls, value):
        """LLMs often emit summary as a bare string — accept and wrap it."""
        if isinstance(value, str):
            return {"text": value}
        return value

    @field_validator("skills", mode="before")
    @classmethod
    def _skills_from_loose_shapes(cls, value):
        """Accept {"llm": [...]} (missing categories) or a bare list."""
        if isinstance(value, dict) and "categories" not in value:
            return {"categories": value}
        if isinstance(value, list):
            return {"categories": {"other": value}}
        return value

    def all_bullets(self) -> list[ResumeBullet]:
        return [
            bullet
            for entry in list(self.experience) + list(self.projects)
            for bullet in entry.bullets
        ]

    def evidence_ids(self) -> list[str]:
        return sorted(
            {
                evidence_id
                for bullet in self.all_bullets()
                for evidence_id in bullet.evidence_ids
            }
        )

    def bullet_space(self) -> int:
        return sum(bullet.space_cost for bullet in self.all_bullets())

    def total_space(self) -> int:
        """Bullets plus fixed section overhead (headers, meta lines)."""
        lines = self.bullet_space()
        if self.header.name:
            lines += 3  # name, contact line, rule
        if self.summary and self.summary.text:
            lines += max(1, estimate_lines(self.summary.text)) + 1
        if self.skills.categories:
            lines += len(self.skills.categories) + 1
        lines += len(self.experience) * 2
        lines += len(self.projects) * 2
        if self.education:
            lines += len(self.education) + 1
        if self.certifications:
            lines += len(self.certifications) + 1
        return lines
