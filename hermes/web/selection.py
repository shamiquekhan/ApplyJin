"""Selection engine: pick the best subset of the master DB for one JD.

The master CV holds everything; a tailored CV shows only the most
relevant slice. For each experience/project we score:

    keyword hits (JD hard skills + tools present in the entry text)
    + 0.5 x semantic similarity (embedding of entry vs JD)

Top-3 experiences and top-3 projects are selected; the skills section
is the intersection of master skills with JD requirements (plus the
skills used by the selected entries). This is deterministic — the same
master DB + JD always selects the same content — and it feeds the
tailor prompt with rich, full-detail source material.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from hermes.utils.embeddings import cosine_similarity, get_embeddings
from hermes.utils.skill_match import skills_in_text

logger = logging.getLogger("hermes.selection")


@dataclass
class RankedEntry:
    id: int
    kind: str  # experience | project
    title: str
    score: float
    matched_keywords: list[str] = field(default_factory=list)
    text: str = ""


@dataclass
class SelectionReport:
    experiences: list[RankedEntry]
    projects: list[RankedEntry]
    skills: list[str]
    missing_skills: list[str]
    ranked_all_experiences: list[RankedEntry] = field(default_factory=list)
    ranked_all_projects: list[RankedEntry] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = ["Selected for this application:"]
        for e in self.experiences:
            kws = ", ".join(e.matched_keywords[:5]) or "-"
            lines.append(f"  exp: {e.title} (score {e.score:.2f} | {kws})")
        for p in self.projects:
            kws = ", ".join(p.matched_keywords[:5]) or "-"
            lines.append(f"  prj: {p.title} (score {p.score:.2f} | {kws})")
        if self.skills:
            lines.append(f"  skills: {', '.join(self.skills[:10])}")
        if self.missing_skills:
            lines.append(
                "  gaps (do NOT claim): " + ", ".join(self.missing_skills[:6])
            )
        return lines


def _entry_text(entry: dict, kind: str) -> str:
    parts = []
    if kind == "experience":
        parts += [entry.get("title", ""), entry.get("organization", ""),
                  entry.get("description", "")]
    else:
        parts += [entry.get("name", ""), entry.get("tech", ""),
                  entry.get("description", "")]
    parts += entry.get("bullets") or []
    parts.append(entry.get("tags", ""))
    return " ".join(p for p in parts if p)


def _rank(
    entries: list[dict], kind: str, keywords: list[str], jd_text: str,
    top_k: int, jd_vec: Optional[list[float]] = None,
) -> tuple[list[RankedEntry], list[RankedEntry]]:
    emb = get_embeddings()
    if jd_vec is None:
        jd_vec = emb.embed(jd_text[:2000])

    ranked: list[RankedEntry] = []
    for entry in entries:
        text = _entry_text(entry, kind)
        if not text.strip():
            continue
        matched = skills_in_text(text, keywords)
        kw_score = len(matched) / len(keywords) if keywords else 0.0
        sem = cosine_similarity(emb.embed(text[:1500]), jd_vec)
        sem = max(0.0, sem)
        score = 0.7 * kw_score + 0.3 * sem
        title = (
            f"{entry.get('title', '')} @ {entry.get('organization', '')}"
            if kind == "experience" else entry.get("name", "")
        )
        ranked.append(
            RankedEntry(
                id=entry["id"], kind=kind, title=title.strip(),
                score=round(score, 4), matched_keywords=matched, text=text,
            )
        )
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked[:top_k], ranked


def select_for_jd(
    master_snapshot: dict,
    keywords: dict,
    jd_text: str,
    top_experiences: int = 3,
    top_projects: int = 3,
) -> SelectionReport:
    """Select the best master-DB slice for this job description."""
    required = list(keywords.get("hard_skills", [])) + list(keywords.get("tools", []))
    soft = list(keywords.get("soft_skills", []))

    emb = get_embeddings()
    jd_vec = emb.embed(jd_text[:2000])

    top_exp, all_exp = _rank(
        master_snapshot.get("experiences", []), "experience",
        required, jd_text, top_experiences, jd_vec,
    )
    top_prj, all_prj = _rank(
        master_snapshot.get("projects", []), "project",
        required, jd_text, top_projects, jd_vec,
    )

    # Skills section: master skills that the JD asks for, plus skills
    # actually used in the selected entries (they earned their place).
    master_skills = []
    for category, names in (master_snapshot.get("skills") or {}).items():
        master_skills += [n for n in names]
    selected_skills = sorted(set(skills_in_text(" ".join(required), master_skills)) | set(
        s for s in master_skills
        if any(s.lower() in (e.text or "").lower() for e in top_exp + top_prj)
    ))

    # Gaps: JD requirements nobody in the master DB can claim.
    everything = " ".join(
        _entry_text(e, k)
        for entries, k in (
            (master_snapshot.get("experiences", []), "experience"),
            (master_snapshot.get("projects", []), "project"),
        )
        for e in entries
    ) + " " + " ".join(master_skills)
    missing = [s for s in required if s not in selected_skills
               and s.lower() not in everything.lower()]

    return SelectionReport(
        experiences=top_exp, projects=top_prj,
        skills=selected_skills, missing_skills=missing,
        ranked_all_experiences=all_exp, ranked_all_projects=all_prj,
    )
