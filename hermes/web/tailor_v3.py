"""Tailor v3 + email templates: build the tailored CV from the master DB.

Flow (CV Forge model, grounded by the resume-tailor skill):
  master snapshot -> selection engine -> selected content (top-3 exp,
  top-3 projects, skills intersection) -> LLM composes the tailored CV
  -> guardrail validation against MASTER FACTS (not just the base resume)

Also generates application/follow-up/thank-you email templates with
contact extraction from the JD (CV Forge's smart-contact feature).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from hermes.utils.llm_router import LLMRouter, LLMUnavailable
from hermes.utils.skill_match import skill_in_text
from hermes.web.selection import SelectionReport

logger = logging.getLogger("hermes.web.tailor_v3")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")
# Keyword part: case-insensitive, scoped so the NAME group stays
# case-sensitive Title Case ("Attn:", "Contact:", "reach out to").
_MANAGER_KEYWORD = (
    r"(?i:\b(?:reach(?:ing)?\s+out\s+to|contact|attn|attention|ask\s+for|"
    r"hiring\s+manager|recruiter)\b)[\s:is-]*"
)
_MANAGER_NAME = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
_MANAGER_PATTERNS = [re.compile(_MANAGER_KEYWORD + _MANAGER_NAME)]

# First words that signal a non-name capture ("contact us", "attn careers").
_NON_NAME_WORDS = {
    "us", "me", "them", "the", "this", "our", "careers", "hr", "a", "an",
    "any", "for", "with", "and", "to", "at", "by", "if", "or", "more",
    "info", "email",
}


def extract_contacts(jd_text: str) -> dict:
    """Emails + hiring manager name from a job description."""
    emails = list(dict.fromkeys(_EMAIL_RE.findall(jd_text)))[:5]
    manager = None
    for pattern in _MANAGER_PATTERNS:
        m = pattern.search(jd_text)
        if m:
            candidate = m.group(1).strip()
            # Reject captures whose first word is a common non-name.
            first_word = candidate.split()[0].lower()
            if first_word not in _NON_NAME_WORDS:
                manager = candidate
                break
    return {"emails": emails, "hiring_manager": manager}


# ---------------------------------------------------------------- selection -> resume


def _selection_to_facts(
    snapshot: dict, report: SelectionReport
) -> tuple[str, str]:
    """(selected-facts text for the prompt, facts for guardrail check)"""
    profile = snapshot.get("profile", {})

    def exp_lines(entry_id) -> list[str]:
        match = next(
            (e for e in snapshot["experiences"] if e["id"] == entry_id), None
        )
        if not match:
            return []
        lines = [
            f"### {match['title']} | {match.get('organization','')} | "
            f"{match.get('start_date','')} - {match.get('end_date','')}"
        ]
        if match.get("location"):
            lines[0] += f" | {match['location']}"
        if match.get("description"):
            lines.append(match["description"])
        lines += [f"- {b}" for b in match.get("bullets", [])]
        return lines

    def prj_lines(entry_id) -> list[str]:
        match = next(
            (p for p in snapshot["projects"] if p["id"] == entry_id), None
        )
        if not match:
            return []
        lines = [f"### {match['name']} — {match.get('tech','')}"]
        if match.get("description"):
            lines.append(match["description"])
        lines += [f"- {b}" for b in match.get("bullets", [])]
        if match.get("link"):
            lines.append(match["link"])
        return lines

    parts = [
        f"# {profile.get('full_name', 'Candidate')}",
        " | ".join(
            p for p in (
                profile.get("location"), profile.get("email"),
                profile.get("linkedin"), profile.get("github"),
                profile.get("website"),
            ) if p
        ),
        "",
    ]
    if profile.get("headline") or profile.get("summary"):
        parts.append("## Summary")
        parts.append(profile.get("headline", ""))
        parts.append(profile.get("summary", ""))
        parts.append("")

    parts.append("## Experience")
    for e in report.experiences:
        parts += exp_lines(e.id)
    parts.append("")
    parts.append("## Projects")
    for p in report.projects:
        parts += prj_lines(p.id)
    parts.append("")
    parts.append("## Skills")
    parts.append(", ".join(report.skills))
    parts.append("")
    if snapshot.get("education"):
        parts.append("## Education")
        for edu in snapshot["education"]:
            bits = [edu.get("degree", ""), edu.get("institution", "")]
            if edu.get("end_date"):
                bits.append(edu["end_date"])
            parts.append("- " + " | ".join(b for b in bits if b))
        parts.append("")
    if snapshot.get("certifications"):
        parts.append("## Certifications")
        parts.append(" · ".join(c.get("name", "") for c in snapshot["certifications"]))
        parts.append("")

    return "\n".join(parts), "\n".join(parts)


_TAILOR_SYSTEM = """You are an expert resume writer composing a tailored CV
from a master career database. The SELECTION below was algorithmically
chosen as the most relevant content for this job.

ABSOLUTE RULES (violating any is a critical failure):
1. Use ONLY the facts in the SELECTION — never invent companies, titles,
   dates, achievements, skills, certifications, or metrics
2. NEVER change employment dates or durations
3. NEVER add skills that are not in the selection's skills list or text
4. ALWAYS preserve quantified metrics exactly (%, $, counts) — if a
   bullet has no metric, do NOT invent one
5. For JD requirements marked as GAPS: do NOT mention them at all
6. Mirror the JD's exact phrasing for skills the candidate genuinely has
7. Keep every fact intact while rephrasing — clarity edits only

WRITING QUALITY (X-Y-Z achievement formula):
- Prefer achievement bullets over duty lists: lead with the result —
  "Accomplished X, as measured by Y, by doing Z"
- Strong, specific action verbs (Architected, Shipped, Cut, Led,
  Automated) — never "Responsible for" or "Helped with"
- Reorder bullet clauses so the most JD-relevant result comes first
- Standard section names only (Summary, Experience, Projects, Skills,
  Education, Certifications) — ATS parsers depend on them
- When a JD uses an acronym, spell it out AND keep it once:
  "retrieval-augmented generation (RAG)"

Output a complete resume in markdown: # Name header, ## Summary
(2-3 lines, JD-focused), ## Experience, ## Projects, ## Skills,
## Education, ## Certifications."""


def tailor_from_master(
    snapshot: dict,
    report: SelectionReport,
    jd_text: str,
    keywords: dict,
    router: Optional[LLMRouter],
) -> dict:
    """Compose the tailored CV. LLM first; deterministic fallback if absent."""
    facts_text, guardrail_text = _selection_to_facts(snapshot, report)

    if router is None:
        # Deterministic: the selection IS the resume (already JD-ranked).
        return {
            "tailored_resume_md": facts_text,
            "validated": True,
            "guardrail_violations": [],
            "model_used": "selection-fallback",
            "selection_summary": report.summary_lines(),
        }

    gaps = ", ".join(report.missing_skills[:10]) or "none"
    required = ", ".join(
        keywords.get("hard_skills", []) + keywords.get("tools", [])
    ) or "n/a"
    prompt = (
        f"JOB DESCRIPTION:\n{jd_text[:5000]}\n\n"
        f"REQUIRED SKILLS: {required}\n"
        f"GAPS (candidate does NOT have these): {gaps}\n\n"
        f"SELECTED CONTENT (all verified facts):\n{facts_text[:8000]}"
    )
    try:
        response = router.complete(prompt=prompt, system=_TAILOR_SYSTEM)
        violations = _validate(response.text, guardrail_text, report)
        if not response.text.strip() or len(response.text.strip()) < 200:
            raise LLMUnavailable("empty LLM response")
        return {
            "tailored_resume_md": response.text,
            "validated": not violations,
            "guardrail_violations": violations,
            "model_used": response.model,
            "selection_summary": report.summary_lines(),
        }
    except LLMUnavailable as exc:
        logger.warning("LLM unavailable (%s) — selection fallback resume", exc)
        return {
            "tailored_resume_md": facts_text,
            "validated": True,
            "guardrail_violations": [],
            "model_used": "selection-fallback",
            "selection_summary": report.summary_lines(),
        }


def _validate(
    tailored_text: str, master_facts: str, report: SelectionReport
) -> list[str]:
    """Tailored output may only contain master facts."""
    violations: list[str] = []

    # 1. Gap skills must never appear
    for gap in report.missing_skills:
        if skill_in_text(gap, tailored_text):
            violations.append(f"Added a skill the candidate lacks: '{gap}'")

    # 2. No years that aren't in the master facts
    year_re = re.compile(r"\b((?:19|20)\d{2})\b")
    master_years = {m.group(1) for m in year_re.finditer(master_facts)}
    invented_years = sorted(
        {m.group(1) for m in year_re.finditer(tailored_text)} - master_years
    )
    if invented_years:
        violations.append(f"Years not in master DB: {invented_years[:5]}")

    # 3. Organizations must come from the master facts
    orgs_re = re.compile(r"^### .* \| ([A-Za-z0-9&.' -]+) \|", re.MULTILINE)
    for org in orgs_re.findall(tailored_text):
        if org.strip() and org.strip().lower() not in master_facts.lower():
            violations.append(f"Organization not in master DB: '{org.strip()}'")

    return violations[:8]


# ---------------------------------------------------------------- email templates


def generate_email_template(
    profile: dict,
    jd: dict,
    template_type: str = "application",
    hiring_manager: Optional[str] = None,
    router: Optional[LLMRouter] = None,
) -> str:
    """Application / follow-up / thank-you email drafts (never sent)."""
    contacts = extract_contacts(jd.get("content", ""))
    manager = hiring_manager or contacts.get("hiring_manager")
    recipient = contacts["emails"][0] if contacts["emails"] else None
    greeting = f"Dear {manager}," if manager else "Dear Hiring Team,"

    keywords = jd.get("keywords") or {}
    required = ", ".join(
        keywords.get("hard_skills", [])[:4]
    ) or "the role's core requirements"

    subject_map = {
        "application": f"Application for {jd.get('title', 'the role')} — {profile.get('full_name', '')}".strip(" —"),
        "follow_up": f"Following up — {jd.get('title', 'the role')} application",
        "thank_you": f"Thank you — {jd.get('title', 'the role')} interview",
        "inquiry": f"Question about the {jd.get('title', 'the role')} opening",
    }

    if router is not None:
        try:
            tone = {
                "application": "a concise application email (120-170 words)",
                "follow_up": "a polite follow-up (90-130 words) on an application sent a week ago",
                "thank_you": "a post-interview thank-you (90-130 words)",
                "inquiry": "a short inquiry about the role (80-120 words)",
            }[template_type]
            response = router.complete(
                system=(
                    "Write a professional job-application email. Plain text, "
                    "no markdown. Sign with the candidate's exact name. "
                    "Never invent qualifications."
                ),
                prompt=(
                    f"Candidate: {profile.get('full_name','')} "
                    f"({profile.get('email','')}), skills include {required}.\n"
                    f"Role: {jd.get('title','')} at {jd.get('company','')}.\n"
                    f"Address it to: {greeting}\n"
                    f"Write {tone}."
                ),
            )
            header = (
                f"To: {recipient or '[recruiter email]'}\n"
                f"Subject: {subject_map.get(template_type, subject_map['application'])}\n\n"
            )
            return header + response.text.strip() + "\n"
        except LLMUnavailable:
            logger.info("LLM unavailable — template email")

    # Deterministic templates
    if template_type == "follow_up":
        body = (
            f"{greeting}\n\n"
            f"I wanted to follow up on my application for the "
            f"{jd.get('title', '')} role at {jd.get('company', '')}, submitted last week. "
            f"My background in {required} matches what the role needs, and I would be glad "
            "to share more in a short call.\n\n"
            "Thank you for your time.\n\n"
            f"Best regards,\n{profile.get('full_name', '')}\n{profile.get('email', '')}\n"
        )
    elif template_type == "thank_you":
        body = (
            f"{greeting}\n\n"
            f"Thank you for the conversation about the {jd.get('title', '')} role at "
            f"{jd.get('company', '')} today. Hearing about the team's work on {required} "
            "made the opportunity even more compelling, and I'm happy to answer any "
            "follow-up questions.\n\n"
            f"Best regards,\n{profile.get('full_name', '')}\n{profile.get('email', '')}\n"
        )
    else:  # application / inquiry
        body = (
            f"{greeting}\n\n"
            f"I'm applying for the {jd.get('title', '')} position at {jd.get('company', '')}. "
            f"My experience covers {required}, and I've attached a resume tailored to the role.\n\n"
            "I'd welcome the chance to discuss how I can contribute.\n\n"
            f"Best regards,\n{profile.get('full_name', '')}\n{profile.get('email', '')}\n"
            + (f"{profile.get('linkedin', '')}\n" if profile.get("linkedin") else "")
        )

    header = (
        f"To: {recipient or '[recruiter email]'}\n"
        f"Subject: {subject_map.get(template_type, subject_map['application'])}\n\n"
    )
    return header + body
