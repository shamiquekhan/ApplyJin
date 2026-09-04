"""Cover Letter Agent: grounded, role-specific letters.

Uses the tailored resume's top bullets as verified highlights. Falls back
to a deterministic template when no LLM is configured, so the pipeline
always produces a letter (clearly marked as a draft template). The final
text is post-processed: any "[Your Name]"-style placeholder the LLM
leaves is replaced with the candidate's real name.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from hermes.config import Profile
from hermes.models import CoverLetter, JobAnalysis, TailoredResume
from hermes.utils.llm_router import LLMRouter, LLMUnavailable

logger = logging.getLogger("hermes.cover")

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "cover_letter.txt"

_PLACEHOLDER_RE = re.compile(
    r"\[(?:your\s+name|name|full\s+name|candidate(?:'s)?\s+name|yourname)\]"
    r"|\bYour\s+Name\b",
    re.IGNORECASE,
)


def _scrub_placeholders(text: str, name: str) -> str:
    """Replace leftover [Your Name] placeholders with the real name."""
    if not name:
        return text
    cleaned = _PLACEHOLDER_RE.sub(name, text)
    if cleaned != text:
        logger.debug("Replaced name placeholder in cover letter")
    return cleaned


def _contact_line(profile: Profile) -> str:
    ident = profile.identity
    parts = [p for p in (ident.email, ident.phone, ident.linkedin) if p]
    return " | ".join(parts) if parts else "see attached resume"


def _template_letter(
    profile: Profile, analysis: JobAnalysis, highlights: list[str]
) -> str:
    highlights_text = "\n".join(f"- {h}" for h in highlights[:3]) or "- (see attached resume)"
    return (
        f"Dear {analysis.company or 'Hiring'} Team,\n\n"
        f"I'm applying for the {analysis.title or 'role'} position. "
        f"With {profile.target.years_experience} years of experience in "
        f"{', '.join(profile.all_skills[:5]) or 'software development'}, "
        "I believe my background aligns well with what you're looking for.\n\n"
        "A few highlights from my experience:\n"
        f"{highlights_text}\n\n"
        "I'd welcome the chance to discuss how my experience can contribute "
        "to your team. Thank you for your consideration.\n\n"
        "Best regards,\n"
        f"{profile.identity.name}\n"
        f"{profile.identity.email}\n"
    )


class CoverLetterAgent:
    def __init__(self, profile: Profile, router: Optional[LLMRouter] = None) -> None:
        self.profile = profile
        self.router = router
        self._prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")

    def generate(
        self, analysis: JobAnalysis, tailored: TailoredResume
    ) -> CoverLetter:
        highlights = tailored.source_bullets[:3]

        if self.router is None:
            letter = _template_letter(self.profile, analysis, highlights)
            return CoverLetter(
                job_id=analysis.job_id,
                text=letter,
                word_count=len(letter.split()),
                model_used="template",
            )

        prompt = self._prompt_template.format(
            title=analysis.title,
            company=analysis.company,
            required_skills=", ".join(analysis.required_skills) or "n/a",
            company_values=", ".join(analysis.company_values) or "n/a",
            name=self.profile.identity.name or "the candidate",
            contact=_contact_line(self.profile),
            highlights="\n".join(f"- {h}" for h in highlights) or "n/a",
        )
        try:
            response = self.router.complete(prompt=prompt)
            final = _scrub_placeholders(
                response.text.strip(), self.profile.identity.name
            )
            return CoverLetter(
                job_id=analysis.job_id,
                text=final,
                word_count=len(final.split()),
                model_used=response.model,
            )
        except LLMUnavailable as exc:
            logger.warning(
                "LLM unavailable (%s) — using template letter for %s",
                exc,
                analysis.job_id,
            )
            letter = _template_letter(self.profile, analysis, highlights)
            return CoverLetter(
                job_id=analysis.job_id,
                text=letter,
                word_count=len(letter.split()),
                model_used="template",
            )
