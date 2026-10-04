"""Candidate evidence: schema, extraction from the master snapshot, strength.

Evidence is an atomic, provenance-carrying fact from the Master CV — a
bullet, a skills line, an education row. Every tailored bullet will point
back at evidence ids so verification and the coverage matrix can check it.

Strength encodes the evidence hierarchy (plan section 7/10):

    skill list mention            0.25
    certification mention         0.35
    project use                   0.55
    implemented feature           0.70
    deployed system          0.70+0.10 -> 0.80
    measured outcome         0.70+0.20 -> 0.90
    verified production outcome    1.00   (set by the verification layer)

Starting values, configurable via STRENGTH_BASE.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from applyjin.utils.skill_match import skill_in_text

EvidenceSourceType = Literal[
    "experience", "project", "skill_list", "education", "certification", "profile"
]

STRENGTH_BASE: dict[str, float] = {
    "skill_list": 0.25,
    "certification": 0.35,
    "education": 0.55,
    "project": 0.55,
    "experience": 0.70,
    "profile": 0.40,
}

_DEPLOYMENT_MARKERS = (
    "production", "deployed", "deploy", "shipped", "launched",
    "scaled", "served", "live",
)

_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?|\b\d+x\b|\b\d{1,3}\+|\b\d{1,3}(?:,\d{3})+\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


class Evidence(BaseModel):
    """One provenance-carrying fact from the Master CV."""

    id: str
    source_id: str
    source_type: EvidenceSourceType
    text: str
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    company: Optional[str] = None
    role: Optional[str] = None
    strength: float = 0.5


def extract_metrics(text: str) -> list[str]:
    """Quantified outcomes in the text (years excluded)."""
    return list(dict.fromkeys(_METRIC_RE.findall(text)))


def extract_dates(text: str) -> list[str]:
    return list(dict.fromkeys(_YEAR_RE.findall(text)))


def estimate_strength(source_type: str, text: str) -> float:
    """Base tier for the source, promoted by deployed/measured signals."""
    base = STRENGTH_BASE.get(source_type, 0.5)
    lowered = text.lower()
    if extract_metrics(text):
        base += 0.20
    elif any(marker in lowered for marker in _DEPLOYMENT_MARKERS):
        base += 0.10
    return round(min(1.0, base), 2)


def _split_tags(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [t.strip() for t in re.split(r"[,;]", raw) if t.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []


def _skills_in(text: str, master_skills: list[str]) -> list[str]:
    return [s for s in master_skills if skill_in_text(s, text)]


def _bullet_evidence(
    prefix: str,
    source_id: str,
    source_type: str,
    bullets: list[str],
    master_skills: list[str],
    tools: list[str],
    company: Optional[str] = None,
    role: Optional[str] = None,
) -> list[Evidence]:
    out: list[Evidence] = []
    for index, bullet in enumerate(bullets):
        text = str(bullet).strip()
        if not text:
            continue
        out.append(
            Evidence(
                id=f"{prefix}-b{index}",
                source_id=source_id,
                source_type=source_type,  # type: ignore[arg-type]
                text=text,
                skills=_skills_in(text, master_skills),
                tools=tools,
                metrics=extract_metrics(text),
                dates=extract_dates(text),
                company=company,
                role=role,
                strength=estimate_strength(source_type, text),
            )
        )
    return out


def evidence_from_snapshot(snapshot: dict) -> list[Evidence]:
    """Flatten a master snapshot into evidence items.

    Covers experiences, projects, skill categories, education, and
    certifications — the pool the evidence optimizer will select from.
    """
    skills_by_category = snapshot.get("skills") or {}
    master_skills = [name for names in skills_by_category.values() for name in names]

    evidence: list[Evidence] = []

    for entry in snapshot.get("experiences") or []:
        source_id = f"exp-{entry['id']}"
        company = entry.get("organization") or None
        role = entry.get("title") or None
        tools = _split_tags(entry.get("tags", ""))
        if entry.get("description"):
            text = str(entry["description"]).strip()
            evidence.append(
                Evidence(
                    id=f"{source_id}-desc",
                    source_id=source_id,
                    source_type="experience",
                    text=text,
                    skills=_skills_in(text, master_skills),
                    tools=tools,
                    metrics=extract_metrics(text),
                    dates=extract_dates(text),
                    company=company,
                    role=role,
                    strength=estimate_strength("experience", text),
                )
            )
        evidence += _bullet_evidence(
            source_id, source_id, "experience",
            [str(b) for b in entry.get("bullets") or []],
            master_skills, tools, company=company, role=role,
        )

    for entry in snapshot.get("projects") or []:
        source_id = f"prj-{entry['id']}"
        tools = _split_tags(entry.get("tech", ""))
        if entry.get("description"):
            text = str(entry["description"]).strip()
            evidence.append(
                Evidence(
                    id=f"{source_id}-desc",
                    source_id=source_id,
                    source_type="project",
                    text=text,
                    skills=_skills_in(text, master_skills),
                    tools=tools,
                    metrics=extract_metrics(text),
                    dates=extract_dates(text),
                    strength=estimate_strength("project", text),
                )
            )
        evidence += _bullet_evidence(
            source_id, source_id, "project",
            [str(b) for b in entry.get("bullets") or []],
            master_skills, tools,
        )

    for category, names in skills_by_category.items():
        names = [str(n) for n in names]
        if not names:
            continue
        text = ", ".join(names)
        evidence.append(
            Evidence(
                id=f"skills-{category}",
                source_id="skills",
                source_type="skill_list",
                text=text,
                skills=names,
                strength=STRENGTH_BASE["skill_list"],
            )
        )

    for index, entry in enumerate(snapshot.get("education") or []):
        bits = [entry.get("degree", ""), entry.get("institution", "")]
        if entry.get("details"):
            bits.append(entry["details"])
        text = " | ".join(str(b) for b in bits if b)
        evidence.append(
            Evidence(
                id=f"edu-{index}",
                source_id="education",
                source_type="education",
                text=text,
                dates=extract_dates(
                    f"{entry.get('start_date','')} {entry.get('end_date','')}"
                ),
                strength=STRENGTH_BASE["education"],
            )
        )

    for index, entry in enumerate(snapshot.get("certifications") or []):
        text = " ".join(
            str(entry.get(k, ""))
            for k in ("name", "issuer", "year")
            if entry.get(k)
        ).strip()
        if not text:
            continue
        evidence.append(
            Evidence(
                id=f"cert-{index}",
                source_id="certifications",
                source_type="certification",
                text=text,
                dates=extract_dates(text),
                strength=estimate_strength("certification", text),
            )
        )

    profile = snapshot.get("profile") or {}
    if profile.get("summary") or profile.get("headline"):
        text = " ".join(
            str(profile.get(k, "")) for k in ("headline", "summary") if profile.get(k)
        ).strip()
        evidence.append(
            Evidence(
                id="profile-summary",
                source_id="profile",
                source_type="profile",
                text=text,
                skills=_skills_in(text, master_skills),
                strength=estimate_strength("profile", text),
            )
        )

    return evidence
