"""Constrained composition: the LLM rephrases bullets inside the IR.

The model edits ONLY free-text fields (bullet text, summary, description).
Provenance fields — evidence_ids, requirement_ids, importance, space_cost —
must be copied verbatim, and no bullet, entry, or section may be added or
removed. Anything else rejects the output and the caller falls back to the
planned IR (deterministic render) or the free-markdown path.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from applyjin.inference.context import DEFAULT_CONTEXT_BUDGET
from applyjin.inference.tokens import ApproximateTokenCounter
from applyjin.resume.ir import ResumeIR
from applyjin.resume.requirements import Requirement
from applyjin.utils.llm_router import LLMRouter

logger = logging.getLogger("applyjin.resume.composer")

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")

# Fields the model may never touch. Only bullet text, summary text, and
# skills ORDER are editable — everything else is master data.
_FROZEN_ENTRY_FIELDS = (
    "id", "title", "organization", "location", "start_date", "end_date",
    "description", "name", "tech", "link",
)
_FROZEN_HEADER_FIELDS = (
    "name", "headline", "location", "email", "linkedin", "github", "website",
)

_SYSTEM = """You are editing a structured resume (a JSON object) for one
specific job description. Rephrase bullet text to mirror the job's phrasing
where truthful, and sharpen the summary. Keep every fact exactly true.

ABSOLUTE RULES (violating any rejects your output):
1. Never invent facts, numbers, dates, companies, titles, or skills
2. Copy "evidence_ids", "requirement_ids", "importance", and "space_cost"
   byte-for-byte from the input — never edit, add, or remove them
3. Never add or remove bullets, entries, or sections — same structure in,
   same structure out
4. Preserve quantified metrics exactly as written
5. Return ONLY the JSON object — no markdown fences, no commentary"""


def _strip_fences(raw: str) -> str:
    return _FENCE_RE.sub("", raw.strip()).strip()


def _provenance_errors(original: ResumeIR, edited: ResumeIR) -> list[str]:
    """Structural/provenance violations — any one rejects `edited`."""
    errors: list[str] = []

    for field in _FROZEN_HEADER_FIELDS:
        if getattr(original.header, field) != getattr(edited.header, field):
            errors.append(f"header.{field} changed")
    if original.education != edited.education:
        errors.append("education changed")
    if original.certifications != edited.certifications:
        errors.append("certifications changed")

    # Skills: same names, any order.
    flat_before = sorted(
        name
        for names in original.skills.categories.values()
        for name in names
    )
    flat_after = sorted(
        name for names in edited.skills.categories.values() for name in names
    )
    if flat_before != flat_after:
        errors.append("skills set changed")

    for attr in ("experience", "projects"):
        before = getattr(original, attr)
        after = getattr(edited, attr)
        if len(before) != len(after):
            errors.append(f"{attr} entry count changed")
            continue
        for old_entry, new_entry in zip(before, after):
            for field in _FROZEN_ENTRY_FIELDS:
                if getattr(old_entry, field, "") != getattr(new_entry, field, ""):
                    errors.append(f"{attr}.{field} changed")
            old_ids = sorted(tuple(b.evidence_ids) for b in old_entry.bullets)
            new_ids = sorted(tuple(b.evidence_ids) for b in new_entry.bullets)
            if old_ids != new_ids:
                errors.append(f"{attr} bullet evidence changed")
                continue
            old_by_key = {
                tuple(b.evidence_ids): b for b in old_entry.bullets
            }
            for bullet in new_entry.bullets:
                old = old_by_key.get(tuple(bullet.evidence_ids))
                if old is None:
                    continue
                if bullet.requirement_ids != old.requirement_ids:
                    errors.append("requirement_ids changed")
                if abs(bullet.importance - old.importance) > 1e-6:
                    errors.append("importance changed")
                if bullet.space_cost != old.space_cost:
                    errors.append("space_cost changed")
    if original.header.name and not edited.header.name:
        errors.append("header name dropped")
    return errors


def compose_ir(
    ir: ResumeIR,
    jd_text: str,
    requirements: list[Requirement],
    router: Optional[LLMRouter],
) -> tuple[Optional[ResumeIR], str]:
    """(edited IR or None, model). None means: fall back to escalation.

    Never raises — malformed output, provenance violations, and router
    failures all return (None, reason).
    """
    if router is None:
        return None, "no-router"

    counter = ApproximateTokenCounter()
    requirements_block = "\n".join(
        f"- ({r.importance:.2f}) {r.text[:100]}"
        for r in sorted(requirements, key=lambda r: -r.importance)[:15]
    )
    prompt = (
        f"JOB DESCRIPTION:\n{counter.truncate(jd_text, DEFAULT_CONTEXT_BUDGET['job'])}\n\n"
        f"JD REQUIREMENTS:\n{requirements_block or '(none)'}\n\n"
        f"RESUME JSON:\n{ir.model_dump_json()}"
    )
    context_length = counter.count(_SYSTEM) + counter.count(prompt)
    try:
        response = router.complete(
            prompt=prompt,
            system=_SYSTEM,
            task="resume_generation",
            context_length=context_length,
        )
        payload = json.loads(_strip_fences(response.text))
        edited = ResumeIR.model_validate(payload)
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        logger.info("IR compose rejected (%s: %s)", type(exc).__name__, exc)
        return None, "compose-invalid"

    errors = _provenance_errors(ir, edited)
    if errors:
        logger.info("IR compose provenance violations: %s", errors[:3])
        return None, "compose-provenance"
    return edited, response.model or "ir-composed"
