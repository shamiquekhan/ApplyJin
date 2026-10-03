"""Resume Tailor v2: RAG + LLM rewriting with hard fabrication guardrails.

Flow: RAG-retrieve relevant bullets from the ChromaDB experience library
(fallback: in-memory ranking over base bullets) -> LLM rewrite (prompt
template) -> post-hoc validation against base resume facts ->
TailoredResume with violation list. If the LLM is unavailable, tailoring
is skipped (base resume used as-is) — never a hallucinated rewrite.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from hermes.models import JobAnalysis, JobPosting, ResumeDocument, TailoredResume
from hermes.utils.embeddings import cosine_similarity, get_embeddings
from hermes.utils.experience_library import ExperienceLibrary
from hermes.utils.llm_router import LLMRouter, LLMUnavailable
from hermes.inference.verification import verify_claims
from hermes.inference.context import build_context

logger = logging.getLogger("hermes.tailor")

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "resume_tailor.txt"

# Entities that must never appear unless present in the base resume.
_DATE_RE = re.compile(r"\b(19|20)\d{2}\s*[-–to]+\s*(19|20)\d{2}\b|\b(19|20)\d{2}\b")
_COMPANY_LINE_RE = re.compile(r"^#{2,4}\s+(.+?)\s*[|•—-]\s*(.+)$", re.MULTILINE)
_METRIC_RE = re.compile(r"\d+%|\$\d|\d+x\b|\b\d{2,}\b", re.IGNORECASE)
_SKILL_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{2,}")


class FabricationError(ValueError):
    pass


def _extract_dates(text: str) -> set[str]:
    return {m.group(0) for m in _DATE_RE.finditer(text)}


def _extract_skill_words(text: str) -> set[str]:
    return {w.lower() for w in _SKILL_WORD_RE.findall(text)}


def select_relevant_bullets(
    resume: ResumeDocument,
    analysis: JobAnalysis,
    top_k: int = 10,
    library: Optional[ExperienceLibrary] = None,
) -> list[str]:
    """Rank base bullets by relevance to the JD.

    v2: RAG retrieval from the ChromaDB experience library when available;
    falls back to in-memory semantic + keyword ranking over base bullets.
    """
    query = " ".join(analysis.required_skills + analysis.must_have_keywords) or (
        f"{analysis.title} {analysis.company}"
    )

    if library is not None:
        try:
            results = library.query(query, n_results=top_k)
            if results:
                return [r["text"] for r in results]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Experience library query failed (%s) — ranking locally", exc)

    if not resume.bullets:
        return []
    emb = get_embeddings()
    query_vec = emb.embed(query)

    def relevance(bullet) -> float:
        bullet_vec = emb.embed(bullet.text)
        semantic = cosine_similarity(query_vec, bullet_vec)
        lowered = bullet.text.lower()
        keyword_hits = sum(
            1 for skill in analysis.required_skills if skill.lower() in lowered
        )
        keyword_component = (
            keyword_hits / len(analysis.required_skills)
            if analysis.required_skills
            else 0.0
        )
        return 0.7 * semantic + 0.3 * keyword_component

    ranked = sorted(resume.bullets, key=relevance, reverse=True)
    return [b.text for b in ranked[:top_k]]


def validate_tailored(
    tailored_text: str, resume: ResumeDocument, analysis: JobAnalysis
) -> list[str]:
    """Return a list of fabrication violations (empty = clean)."""
    violations: list[str] = []

    base_dates = _extract_dates(resume.raw_text)
    new_dates = _extract_dates(tailored_text)
    invented_dates = new_dates - base_dates
    if invented_dates:
        violations.append(
            f"Dates not in base resume: {sorted(invented_dates)[:5]}"
        )

    base_words = _extract_skill_words(resume.raw_text)
    new_words = _extract_skill_words(tailored_text)
    original_case = set(_SKILL_WORD_RE.findall(tailored_text))
    base_original = set(_SKILL_WORD_RE.findall(resume.raw_text))
    invented_caps = [
        w for w in original_case - base_original
        if len(w) > 4 and (w[:1].isupper() or w.isupper()) and w.lower() not in base_words
    ]
    if len(invented_caps) > 15:
        violations.append(
            f"Many new capitalized terms ({len(invented_caps)}): "
            f"{sorted(invented_caps)[:10]}"
        )

    known_skills = {s.lower() for s in resume.skills}
    jd_only_skills = [
        s for s in analysis.required_skills
        if s.lower() not in known_skills
        and s.lower() in tailored_text.lower()
        and s.lower() not in resume.raw_text.lower()
    ]
    if jd_only_skills:
        violations.append(
            f"Added skills the candidate lacks: {jd_only_skills[:5]}"
        )

    return violations


class ResumeTailor:
    """RAG + LLM-powered resume tailoring with guardrails.

    Phase 3: an (optional) learned STYLE GUIDE is injected into the prompt.
    Variant A uses the active guide; variant B the experimental one —
    set via `variant` so the A/B framework can compare them.
    """

    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        library: Optional[ExperienceLibrary] = None,
        style_guide: str = "",
        experimental_style_guide: str = "",
    ) -> None:
        self.router = router
        self.library = library
        self.style_guide = style_guide
        self.experimental_style_guide = experimental_style_guide
        self._prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")

    def _guide_for(self, variant: str) -> str:
        if variant == "B" and self.experimental_style_guide:
            return self.experimental_style_guide
        return self.style_guide or "No style guide yet — use best practices."

    def tailor(
        self,
        resume: ResumeDocument,
        job: JobPosting,
        analysis: JobAnalysis,
        variant: str = "A",
    ) -> TailoredResume:
        relevant = select_relevant_bullets(
            resume, analysis, library=self.library
        )

        if self.router is None:
            logger.info(
                "No LLM configured — using base resume as-is for %s", job.job_id
            )
            return TailoredResume(
                job_id=job.job_id,
                text=resume.raw_text,
                markdown=resume.raw_text,
                source_bullets=relevant,
                validated=True,
                model_used="none-base-resume",
            )

        context = build_context(
            job=job.description,
            evidence=relevant,
            instructions=self._guide_for(variant),
        )
        prompt = self._prompt_template.format(
            style_guide=self._guide_for(variant),
            required_skills=", ".join(analysis.required_skills) or "n/a",
            must_have_keywords=", ".join(analysis.must_have_keywords) or "n/a",
            relevant_bullets=context.as_prompt(),
            base_resume=(
                "<UNTRUSTED_UPLOADED_RESUME>\n"
                + resume.raw_text[:6000]
                + "\n</UNTRUSTED_UPLOADED_RESUME>"
            ),
        )

        try:
            response = self.router.complete(
                prompt=prompt,
                task="resume_generation",
                context_length=context.input_tokens,
            )
        except LLMUnavailable as exc:
            logger.warning(
                "LLM unavailable (%s) — falling back to base resume for %s",
                exc,
                job.job_id,
            )
            return self._base_fallback(resume, job, relevant)

        if not response.text.strip() or len(response.text.strip()) < 200:
            # Provider returned an empty/blocked response — never ship that.
            logger.warning(
                "LLM returned empty response for %s (len=%d) — using base resume",
                job.job_id,
                len(response.text),
            )
            return self._base_fallback(resume, job, relevant)

        violations = validate_tailored(response.text, resume, analysis)
        evidence = [(f"bullet-{index}", bullet) for index, bullet in enumerate(relevant, 1)]
        evidence.append(("master-resume", resume.raw_text))
        claim_references = verify_claims(
            response.text,
            evidence,
            known_entities={"SKILL": resume.skills},
        )
        unsupported = [reference.claim for reference in claim_references if not reference.supported]
        if unsupported:
            violations.append(f"Unsupported claims: {unsupported[:3]}")
        if violations:
            logger.warning(
                "Tailored resume for %s failed validation: %s",
                job.job_id,
                violations,
            )

        return TailoredResume(
            job_id=job.job_id,
            text=response.text,
            markdown=response.text,
            source_bullets=relevant,
            guardrail_violations=violations,
            claim_references=[reference.__dict__ for reference in claim_references],
            validated=not violations,
            model_used=response.model,
        )

    def _base_fallback(
        self, resume: ResumeDocument, job: JobPosting, relevant: list[str]
    ) -> TailoredResume:
        return TailoredResume(
            job_id=job.job_id,
            text=resume.raw_text,
            markdown=resume.raw_text,
            source_bullets=relevant,
            validated=True,
            model_used="none-base-resume",
        )
