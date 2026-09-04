"""Interview Prep Agent: STAR stories + likely questions for a given job.

Given a tracked application (or raw JD), it:
  1. RAG-retrieves the candidate's most relevant experience bullets
  2. Structures them into STAR (Situation/Task/Action/Result) skeletons
     grounded in verified resume facts
  3. Generates likely interview questions from the JD analysis
  4. Produces a prep document saved next to the application artifacts

Heuristic mode works without an LLM (bullet-grounded STAR skeletons +
rule-based questions); LLM mode produces polished narratives.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from hermes.config import Profile
from hermes.models import JobAnalysis, JobPosting, ResumeDocument
from hermes.utils.experience_library import ExperienceLibrary
from hermes.utils.llm_router import LLMRouter, LLMUnavailable

logger = logging.getLogger("hermes.prep")

_METRIC_RE = re.compile(r"\d+%|\$\d[\d,.]*|\b\d+x\b|\b\d{2,}\+?\b")

_QUESTION_TEMPLATES = [
    "Tell me about a time you built something with {skill}.",
    "Walk me through how you'd design a system using {skill}.",
    "What's the most challenging bug you've fixed involving {skill}?",
    "How do you evaluate or test work done with {skill}?",
]

_BEHAVIORAL = [
    "Tell me about a project you owned end to end. What was the outcome?",
    "Describe a time you disagreed with a teammate. How did you resolve it?",
    "Tell me about a failure. What did you learn?",
    "Why this company, and why now?",
]


def _split_star(bullet: str) -> dict[str, str]:
    """Decompose a metric-bearing bullet into STAR skeleton parts."""
    metrics = _METRIC_RE.findall(bullet)
    action = bullet
    verbs = re.findall(r"^[A-Z][a-z]+", bullet)
    situation = "A project or role described in your resume"
    if verbs:
        action = bullet
    return {
        "situation": situation,
        "task": f"The role required: {bullet.split(',')[0]}" if "," in bullet else "Own this work end to end",
        "action": action,
        "result": ", ".join(metrics) if metrics else "The successful delivery described in the bullet",
        "metrics": metrics,
    }


def _heuristic_questions(analysis: JobAnalysis) -> list[str]:
    questions: list[str] = []
    for skill in analysis.required_skills[:5]:
        for template in _QUESTION_TEMPLATES[:2]:
            questions.append(template.format(skill=skill))
    questions.extend(_BEHAVIORAL[:2])
    if analysis.years_experience:
        questions.append(
            f"This role asks for {analysis.years_experience}+ years — "
            "walk me through your most relevant experience."
        )
    return questions


def build_prep_document(
    analysis: JobAnalysis,
    star_stories: list[dict],
    questions: list[str],
    company: str = "",
    llm_used: bool = False,
) -> str:
    lines = [
        f"# Interview Prep — {analysis.title}",
        f"**Company:** {company or analysis.company}",
        "",
        "## Likely questions",
        "",
    ]
    for i, question in enumerate(questions, 1):
        lines.append(f"{i}. {question}")
    lines += ["", "## STAR stories (grounded in your resume facts)", ""]
    for i, story in enumerate(star_stories, 1):
        lines.append(f"### Story {i}")
        lines.append(f"- **Situation:** {story['situation']}")
        lines.append(f"- **Task:** {story['task']}")
        lines.append(f"- **Action:** {story['action']}")
        lines.append(f"- **Result:** {story['result']}")
        if story.get("metrics"):
            lines.append(f"- **Metrics to quote:** {', '.join(story['metrics'])}")
        lines.append("")
    lines += [
        "## Tips",
        "",
        "- Quantify results with the metrics above — they are verified resume facts.",
        "- Keep each story to 90 seconds; lead with the result if asked for a summary.",
        f"- Prepared by Hermes ({'LLM' if llm_used else 'heuristic'} mode). "
        "Facts are drawn from your base resume only.",
    ]
    return "\n".join(lines)


class InterviewPrepAgent:
    def __init__(
        self,
        profile: Profile,
        router: Optional[LLMRouter] = None,
        library: Optional[ExperienceLibrary] = None,
    ) -> None:
        self.profile = profile
        self.router = router
        self.library = library

    def prepare(
        self,
        job: JobPosting,
        analysis: JobAnalysis,
        resume: ResumeDocument,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Generate prep doc; save to output_dir/interview_prep.md."""
        # 1. RAG-retrieve the most relevant verified bullets.
        query = " ".join(analysis.required_skills[:6])
        stories_bullets: list[str] = []
        if self.library is not None:
            try:
                hits = self.library.query(query, n_results=5)
                stories_bullets = [h["text"] for h in hits]
            except Exception as exc:  # noqa: BLE001
                logger.debug("Library query failed: %s", exc)
        if not stories_bullets:
            ranked = sorted(
                resume.bullets,
                key=lambda b: sum(
                    1 for s in analysis.required_skills if s.lower() in b.text.lower()
                ),
                reverse=True,
            )
            stories_bullets = [b.text for b in ranked[:5] if b.text]

        # 2. STAR skeletons + questions.
        star_stories = [_split_star(b) for b in stories_bullets[:5] if b.strip()]
        questions = _heuristic_questions(analysis)

        llm_used = False
        if self.router is not None:
            questions, star_stories = self._llm_enrich(
                job, analysis, star_stories, questions
            )
            llm_used = True

        # 3. Write the document.
        doc = build_prep_document(
            analysis, star_stories, questions,
            company=job.company, llm_used=llm_used,
        )
        if output_dir is None:
            output_dir = Path("data/prep")
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "interview_prep.md"
        out_path.write_text(doc, encoding="utf-8")
        logger.info("Interview prep written to %s", out_path)
        return out_path

    def _llm_enrich(
        self,
        job: JobPosting,
        analysis: JobAnalysis,
        star_stories: list[dict],
        questions: list[str],
    ) -> tuple[list[str], list[dict]]:
        """LLM-polish questions + STAR actions. Facts stay from the resume."""
        facts = "\n".join(
            f"- {s['action']}" for s in star_stories
        ) or "- (no bullets)"
        try:
            raw = self.router.complete_json(
                system=(
                    "You are an interview coach. Use ONLY the provided "
                    "resume facts — never invent achievements. Respond "
                    "as JSON: {\"questions\": [...], "
                    "\"star_actions\": [\"improved action text per story\"]}"
                ),
                prompt=(
                    f"Job: {job.title} at {job.company}\n"
                    f"Required skills: {', '.join(analysis.required_skills)}\n\n"
                    f"Resume facts (verified):\n{facts}\n\n"
                    "Generate 8 likely interview questions (mix technical "
                    "and behavioral) and one polished STAR 'action' "
                    "sentence per resume fact."
                ),
            )
            questions = [
                str(q) for q in raw.get("questions", []) if q
            ] or questions
            actions = [str(a) for a in raw.get("star_actions", []) if a]
            for story, action in zip(star_stories, actions):
                story["action"] = action
        except LLMUnavailable as exc:
            logger.info("LLM unavailable (%s) — heuristic prep only", exc)
        return questions, star_stories
