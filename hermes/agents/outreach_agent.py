"""Outreach Agent: draft LinkedIn connection notes + follow-up emails.

DRAFTS ONLY — Hermes never sends anything. Output is written to files for
the human to copy-paste. LinkedIn connection notes are capped at 300
characters per LinkedIn's limit; follow-up emails include a 7-day timing
suggestion and respect a "don't pester" cooldown (tracked in notes).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from hermes.config import Profile
from hermes.models import JobAnalysis
from hermes.utils.llm_router import LLMRouter, LLMUnavailable

logger = logging.getLogger("hermes.outreach")

LINKEDIN_NOTE_LIMIT = 300


def _trim_to_limit(text: str, limit: int = LINKEDIN_NOTE_LIMIT) -> str:
    text = text.strip().strip('"')
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # trim back to last complete sentence/punct
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1]
    trimmed = cut.rsplit(" ", 1)[0].rstrip(".,;: ")
    if not trimmed:
        trimmed = cut
    return trimmed[:limit]


def draft_linkedin_note(profile: Profile, analysis: JobAnalysis, router: Optional[LLMRouter] = None) -> str:
    """A short, human connection-request note (<=300 chars)."""
    name = analysis.company or "your team"
    top_skill = (
        analysis.required_skills[0]
        if analysis.required_skills
        else "the role"
    )
    if router is not None:
        try:
            response = router.complete(
                system=(
                    "Write a LinkedIn connection note. Under 280 characters. "
                    "Warm, specific, no flattery, no begging, no fake familiarity. "
                    f"Sign as {profile.identity.name}."
                ),
                prompt=(
                    f"I applied for the {analysis.title} role at "
                    f"{analysis.company}. The role emphasizes {top_skill}. "
                    "Write a short note to the hiring manager."
                ),
            )
            return _trim_to_limit(response.text)
        except LLMUnavailable:
            logger.info("LLM unavailable — template LinkedIn note")
    role = f"{analysis.title} role" if analysis.title else "role"
    focus = (
        f"the focus on {top_skill} matches my experience well"
        if top_skill != "the role"
        else "the role maps directly to my experience"
    )
    return _trim_to_limit(
        f"Hi — I applied for the {role} at {name}. "
        f"My background is in {top_skill} and I'd love to share how it maps "
        f"to what your team is building. — {profile.identity.name}"
        if top_skill != "the role"
        else f"Hi — I applied for the {role} at {name}. "
        f"{focus[0].upper() + focus[1:]} — I'd love to share how my work "
        f"maps to what your team is building. — {profile.identity.name}"
    )


def draft_followup_email(
    profile: Profile,
    analysis: JobAnalysis,
    applied_days_ago: int,
    router: Optional[LLMRouter] = None,
) -> str:
    """A polite follow-up email body (no headers — human copies it)."""
    first_name = profile.identity.name.split(" ")[0]
    if router is not None:
        try:
            response = router.complete(
                system=(
                    "Write a 100-word follow-up email body. Polite, confident, "
                    "one clear ask. No pressure tactics. Sign with the "
                    f"candidate's name: {profile.identity.name}."
                ),
                prompt=(
                    f"Applied for {analysis.title} at {analysis.company} "
                    f"{applied_days_ago} days ago. No response yet. "
                    "Draft a follow-up to the hiring manager."
                ),
            )
            return response.text.strip()
        except LLMUnavailable:
            logger.info("LLM unavailable — template follow-up")

    return (
        f"Hi,\n\n"
        f"I wanted to follow up on my application for the "
        f"{analysis.title} role at {analysis.company}. I applied "
        f"{applied_days_ago} days ago and remain very interested — "
        f"the focus on {(analysis.required_skills or ['the work'])[0]} "
        "matches my experience well.\n\n"
        "Would you have 15 minutes for a quick chat? Happy to work around "
        "your schedule.\n\n"
        f"Best regards,\n{profile.identity.name}\n"
        f"{profile.identity.email}\n"
        f"{_linkedin_line(first_name, profile)}\n"
    )


def _linkedin_line(first_name: str, profile: Profile) -> str:
    return profile.identity.linkedin or profile.identity.github or ""


class OutreachAgent:
    """Draft LinkedIn notes + follow-up emails to files. Never sends."""

    def __init__(self, profile: Profile, router: Optional[LLMRouter] = None) -> None:
        self.profile = profile
        self.router = router

    def draft_for(
        self,
        analysis: JobAnalysis,
        applied_days_ago: int = 7,
        output_dir: Optional[Path] = None,
    ) -> dict[str, Path]:
        note = draft_linkedin_note(self.profile, analysis, self.router)
        email = draft_followup_email(
            self.profile, analysis, applied_days_ago, self.router
        )
        if output_dir is None:
            output_dir = Path("data/outreach")
        output_dir.mkdir(parents=True, exist_ok=True)
        note_path = output_dir / "linkedin_note.txt"
        email_path = output_dir / "followup_email.txt"
        note_path.write_text(note, encoding="utf-8")
        email_path.write_text(email, encoding="utf-8")

        status = "OK" if len(note) <= LINKEDIN_NOTE_LIMIT else "OVER LIMIT"
        logger.info(
            "Outreach drafted (%d chars, %s): %s", len(note), status, note_path
        )
        return {"note": note_path, "email": email_path, "note_text": note, "email_text": email}
