"""Tailor v3 + email templates: build the tailored CV from the master DB.

Flow (Resume Engine):
  master snapshot -> selection engine (marginal coverage over JD
  requirements) -> ResumeIR -> planner (section order, one-page budget)
  -> constrained LLM edits inside the IR -> deterministic render
  -> guardrail validation + quality gate (free-markdown composition
  escalates only if the IR edit fails)

Also generates application/follow-up/thank-you email templates with
contact extraction from the JD (CV Forge's smart-contact feature).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from hermes.inference.context import DEFAULT_CONTEXT_BUDGET
from hermes.inference.tokens import ApproximateTokenCounter
from hermes.inference.verification import verify_claims
from hermes.resume.composer import compose_ir
from hermes.resume.gate import gate
from hermes.resume.ir import ResumeIR
from hermes.resume.planner import ResumePlan, ir_from_selection, plan_resume
from hermes.resume.repair import compress_to_fit
from hermes.resume.render import estimate_md_lines, render_markdown
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


def _plan_for(snapshot: dict, report: SelectionReport) -> ResumePlan:
    """Selection -> ResumeIR -> one-page plan (fully deterministic)."""
    ir = ir_from_selection(
        snapshot,
        selected_experience_ids=[e.id for e in report.experiences],
        selected_project_ids=[p.id for p in report.projects],
        requirements=report.requirements,
        skills=report.skills,
    )
    return plan_resume(ir, report.requirements)


def _selection_evidence(
    report: SelectionReport, facts_text: str, ir: Optional[ResumeIR] = None
) -> list[tuple[str, str]]:
    """(id, text) pairs for claim verification: per-entry provenance,
    per-bullet provenance matching the IR evidence ids, plus the full
    rendered selection (profile, education, certifications)."""
    evidence = [(f"exp-{e.id}", e.text) for e in report.experiences if e.text]
    evidence += [(f"prj-{p.id}", p.text) for p in report.projects if p.text]
    if ir is not None:
        for bullet in ir.all_bullets():
            for evidence_id in bullet.evidence_ids:
                evidence.append((evidence_id, bullet.text))
    evidence.append(("selection", facts_text))
    return evidence


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
    """Compose the tailored CV through the Resume Engine.

    Primary path: planned ResumeIR -> constrained LLM edits (compose_ir)
    -> deterministic render. Escalation: free-markdown composition (the
    proven prompt path). Last resort: the planned render itself. Every
    path runs guardrail validation + the quality gate.
    """
    plan = _plan_for(snapshot, report)
    facts_text = render_markdown(plan.ir)
    evidence = _selection_evidence(report, facts_text, plan.ir)
    known_entities = {"SKILL": report.skills}

    def _gate(
        text: str,
        references,
        *,
        ir,
        over_budget: bool,
        estimated_lines: int,
    ) -> dict:
        return gate(
            text,
            ir,
            report.requirements,
            evidence,
            known_entities,
            over_budget=over_budget,
            estimated_lines=estimated_lines,
            page_line_budget=plan.page_line_budget,
            references=references,
        ).model_dump()

    if router is None:
        # Deterministic: the planned selection IS the resume.
        gate_report = _gate(
            facts_text,
            references=[],
            ir=plan.ir,
            over_budget=plan.over_budget,
            estimated_lines=plan.estimated_lines,
        )
        return {
            "tailored_resume_md": facts_text,
            "validated": gate_report["passed"],
            "guardrail_violations": gate_report["violations"],
            "model_used": "selection-fallback",
            "generation_path": "planned",
            "selection_summary": report.summary_lines(),
            "claim_references": [],
            "gate": gate_report,
        }

    gaps = ", ".join(report.missing_skills[:10]) or "none"
    required = ", ".join(
        keywords.get("hard_skills", []) + keywords.get("tools", [])
    ) or "n/a"
    # Budgets are tokens end-to-end (same units as the router's
    # context_length filtering), not raw character slices.
    counter = ApproximateTokenCounter()
    jd_part = counter.truncate(jd_text, DEFAULT_CONTEXT_BUDGET["job"])
    facts_part = counter.truncate(
        facts_text, DEFAULT_CONTEXT_BUDGET["candidate_evidence"]
    )
    prompt = (
        f"JOB DESCRIPTION:\n{jd_part}\n\n"
        f"REQUIRED SKILLS: {required}\n"
        f"GAPS (candidate does NOT have these): {gaps}\n\n"
        f"SELECTED CONTENT (all verified facts):\n{facts_part}"
    )
    if report.requirements:
        req_lines = [
            f"- ({r.importance:.2f}) {r.text[:100]}"
            for r in sorted(
                report.requirements, key=lambda r: -r.importance
            )[:12]
        ]
        req_block = counter.truncate(
            "\n".join(req_lines), DEFAULT_CONTEXT_BUDGET["instructions"]
        )
        prompt += (
            f"\n\nJD REQUIREMENTS by importance (mirror the ones the "
            f"selection supports; never claim the rest):\n{req_block}"
        )
    context_length = counter.count(_TAILOR_SYSTEM) + counter.count(prompt)

    text: Optional[str] = None
    model_used: Optional[str] = None
    generation_path: Optional[str] = None

    # ---- primary: constrained edits inside the structured IR
    active_plan = plan
    composed, compose_model = compose_ir(
        plan.ir, jd_text, report.requirements, router
    )
    if composed is not None:
        # The composer may lengthen bullets; the system — never the LLM —
        # owns space: re-derive every cost from the FINAL text, then
        # re-fit to the page budget (drops lowest-importance bullets,
        # re-trims an over-long summary) before rendering.
        composed.recalculate_space()
        active_plan = plan_resume(
            composed, report.requirements, plan.page_line_budget
        )
        candidate = render_markdown(active_plan.ir)
        if len(candidate.strip()) >= 200:
            text, model_used = candidate, compose_model
            generation_path = "ir-compose"
            logger.info("IR compose accepted (%s)", compose_model)
        else:
            logger.info("IR compose output too short — escalating")
    elif composed is None and compose_model != "no-router":
        logger.info("IR compose rejected (%s) — markdown escalation", compose_model)

    # ---- escalation: free-markdown composition
    if text is None:
        try:
            response = router.complete(
                prompt=prompt,
                system=_TAILOR_SYSTEM,
                task="resume_generation",
                context_length=context_length,
            )
            if len(response.text.strip()) >= 200:
                text, model_used = response.text, response.model
                generation_path = "markdown"
        except LLMUnavailable as exc:
            logger.warning("LLM unavailable (%s)", exc)

    # ---- last resort: the planned render itself
    if text is None:
        gate_report = _gate(
            facts_text,
            references=[],
            ir=plan.ir,
            over_budget=plan.over_budget,
            estimated_lines=plan.estimated_lines,
        )
        logger.warning("generation failed — planned-render fallback")
        return {
            "tailored_resume_md": facts_text,
            "validated": gate_report["passed"],
            "guardrail_violations": gate_report["violations"],
            "model_used": "selection-fallback",
            "generation_path": "planned-fallback",
            "selection_summary": report.summary_lines(),
            "claim_references": [],
            "gate": gate_report,
        }

    # Free-markdown output has no IR to re-fit — measure the actual
    # document and compress it (repair hierarchy) until it fits the
    # one-page budget, then gate on the measured line count.
    if generation_path == "markdown":
        text = compress_to_fit(
            text, estimate_md_lines, plan.page_line_budget, max_steps=12
        )
        final_lines = estimate_md_lines(text)
        final_over = final_lines > plan.page_line_budget
    else:
        final_lines = active_plan.estimated_lines
        final_over = active_plan.over_budget

    violations = _validate(text, facts_text, report)
    references = verify_claims(text, evidence, known_entities)
    unsupported = [r.claim for r in references if not r.supported]
    if unsupported:
        violations.append(f"Unsupported claims: {unsupported[:3]}")
    gate_report = _gate(
        text,
        references,
        ir=active_plan.ir,
        over_budget=final_over,
        estimated_lines=final_lines,
    )
    return {
        "tailored_resume_md": text,
        "validated": not violations,
        "guardrail_violations": violations,
        "model_used": model_used,
        "generation_path": generation_path,
        "selection_summary": report.summary_lines(),
        "claim_references": [r.__dict__ for r in references],
        "gate": gate_report,
    }


def _validate(
    tailored_text: str, master_facts: str, report: SelectionReport
) -> list[str]:
    """Tailored output may only contain master facts."""
    violations: list[str] = []

    # 1. Gap skills must never appear — unless the selected master
    # evidence itself mentions the term (then it's grounded, not invented).
    for gap in report.missing_skills:
        if skill_in_text(gap, tailored_text) and not skill_in_text(gap, master_facts):
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
