"""Web pipeline: interactive tailor flow backed by the core Hermes agents.

Reuses the hardened components — Gemini router (with model rotation),
ATS scorer, guardrailed tailor, cover letter agent, PDF generator — so the
web dashboard inherits the same safety rails and rate-limit handling as
the CLI pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from hermes.config import load_profile
from hermes.models import JobAnalysis, JobPosting, ResumeDocument
from hermes.utils.ats_scorer import ATSScorer
from hermes.utils.llm_router import LLMRouter, LLMUnavailable
from hermes.utils.resume_parser import parse_resume_text

logger = logging.getLogger("hermes.web.pipeline")

# Heuristic keyword buckets for the no-LLM path.
_TECH_LEXICON = [
    "Python", "Go", "Rust", "Java", "TypeScript", "JavaScript", "SQL", "C++",
    "PyTorch", "TensorFlow", "scikit-learn", "XGBoost", "LangChain", "LangGraph",
    "FastAPI", "Django", "Flask", "React", "Next.js", "Node.js", "GraphQL", "gRPC",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "PostgreSQL",
    "Redis", "MongoDB", "Kafka", "Spark", "Airflow", "MLflow", "LLM", "RAG",
    "NLP", "computer vision", "deep learning", "machine learning", "MLOps",
    "CI/CD", "Linux", "Git", "microservices", "ETL", "fine-tuning", "prompt engineering",
]
_TOOLS_LEXICON = [
    "Jira", "GitHub", "GitLab", "Figma", "Tableau", "Power BI", "Excel",
    "Notion", "Slack", "Datadog", "Grafana", "Prometheus", "Hugging Face",
    "Weights & Biases", "OpenAI API", "Claude API", "Gemini API", "Ollama",
]
_SOFT_LEXICON = [
    "communication", "collaboration", "leadership", "mentoring", "ownership",
    "problem-solving", "stakeholder management", "cross-functional", "agile",
    "time management", "adaptability", "teamwork", "written communication",
]


def _extract_heuristic(jd_text: str) -> dict[str, list[str]]:
    lowered = jd_text.lower()
    hard = [t for t in _TECH_LEXICON if t.lower() in lowered]
    tools = [t for t in _TOOLS_LEXICON if t.lower() in lowered]
    soft = [t for t in _SOFT_LEXICON if t.lower() in lowered]
    return {
        "hard_skills": hard, "soft_skills": soft, "tools": tools,
        "certifications": [], "domain_keywords": [],
        "extractor": "heuristic",
    }


def extract_keywords(
    jd_text: str, router: Optional[LLMRouter]
) -> dict[str, list[str]]:
    """Bucketed keyword extraction: LLM first, lexicon fallback."""
    if router is not None:
        try:
            raw = router.complete_json(
                system=(
                    "Extract keywords from a job description as JSON with keys: "
                    '"hard_skills" (3-12 concrete technical skills), '
                    '"soft_skills" (0-6), "tools" (0-8 named tools/platforms), '
                    '"certifications" (0-4), "domain_keywords" (0-8 domain/business '
                    'terms). Short noun phrases only, no sentences.'
                ),
                prompt=f"Job description:\n{jd_text[:6000]}",
            )
            result = {}
            for key in ("hard_skills", "soft_skills", "tools",
                        "certifications", "domain_keywords"):
                value = raw.get(key, [])
                result[key] = (
                    [str(v).strip() for v in value if str(v).strip()]
                    if isinstance(value, list) else []
                )
            result["extractor"] = "llm"
            if any(result[k] for k in result if k != "extractor"):
                return result
        except LLMUnavailable as exc:
            logger.info("LLM unavailable for keywords (%s) — heuristic", exc)
    return _extract_heuristic(jd_text)


def _as_resume_document(raw_text: str, profile) -> ResumeDocument:
    return parse_resume_text(raw_text, profile)


def _as_job_posting(jd_id: str, title: str, company: str, jd_text: str) -> JobPosting:
    return JobPosting(
        job_id=f"web-{jd_id}", title=title, company=company, description=jd_text,
    )


def _as_analysis(title: str, company: str, keywords: dict) -> JobAnalysis:
    return JobAnalysis(
        job_id="web", title=title, company=company,
        required_skills=keywords.get("hard_skills", []),
        must_have_keywords=keywords.get("domain_keywords", []),
        extractor=keywords.get("extractor", "heuristic"),
    )


def score_pair(resume_text: str, jd_text: str, keywords: dict) -> dict:
    """Keyword-match %, semantic %, and combined ATS % (0-100 scale).

    Keyword match uses word-boundary skill matching (skill_match) —
    substring matching inflated scores ("R" matched "React") and missed
    multi-word skills ("machine learning").
    """
    from hermes.utils.embeddings import cosine_similarity, get_embeddings
    from hermes.utils.skill_match import skill_coverage

    required = (
        keywords.get("hard_skills", [])
        + keywords.get("tools", [])
    ) or _extract_heuristic(jd_text)["hard_skills"]

    kw, _matched, _missing = skill_coverage(required, resume_text)

    emb = get_embeddings()
    sem = max(
        0.0,
        cosine_similarity(
            emb.embed(resume_text[:2000]), emb.embed(jd_text[:2000])
        ),
    )
    combined = 0.6 * kw + 0.4 * sem
    return {
        "keyword_match": round(kw * 100, 1),
        "semantic_similarity": round(sem * 100, 1),
        "overall": round(combined * 100, 1),
    }


def score_keywords_for(keywords: dict) -> list[str]:
    """The pinned keyword list used for before/after score comparison."""
    return (
        keywords.get("hard_skills", [])
        + keywords.get("tools", [])
    )


def tailor(
    resume: dict,
    jd: dict,
    selected_keywords: list[str],
    router: Optional[LLMRouter],
) -> dict:
    """Guardrailed tailoring. Returns markdown + validation report."""
    from hermes.agents.resume_tailor import ResumeTailor, validate_tailored

    profile = load_profile()
    resume_doc = _as_resume_document(resume["raw_text"], profile)
    job = _as_job_posting(str(jd["id"]), jd["title"], jd["company"], jd["content"])
    keywords = jd.get("keywords") or _extract_heuristic(jd["content"])
    analysis = _as_analysis(jd["title"], jd["company"], keywords)
    # Honor the human's keyword selection as the tailoring focus.
    analysis.required_skills = selected_keywords or analysis.required_skills

    tailor_agent = ResumeTailor(router, library=None)
    result = tailor_agent.tailor(resume_doc, job, analysis)
    return {
        "tailored_resume_md": result.markdown,
        "guardrail_violations": result.guardrail_violations,
        "validated": result.validated,
        "model_used": result.model_used,
    }


def cover_letter(
    resume: dict, jd: dict, tailored_md: str, router: Optional[LLMRouter]
) -> str:
    """Cover letter grounded in the tailored resume.

    The candidate name comes from (in order): the profile config, the first
    line of the uploaded resume ("# NAME" heading — the standard resume
    header), falling back to a generic signature.
    """
    import re as _re

    from hermes.agents.cover_letter import CoverLetterAgent
    from hermes.utils.llm_router import LLMUnavailable

    profile = load_profile()

    # Web uploads don't go through profile.yml — pull the name from the
    # resume header so the letter is signed correctly.
    if not profile.identity.name:
        first_line = next(
            (ln.strip() for ln in resume["raw_text"].splitlines() if ln.strip()),
            "",
        )
        header = _re.sub(r"^[#*\s]+", "", first_line).strip()
        if 2 < len(header) <= 60 and not any(ch.isdigit() for ch in header):
            profile.identity.name = header

    keywords = jd.get("keywords") or _extract_heuristic(jd["content"])
    analysis = _as_analysis(jd["title"], jd["company"], keywords)

    class _Tailored:
        pass

    holder = _Tailored()
    holder.source_bullets = [
        line[2:] for line in tailored_md.splitlines()
        if line.startswith("- ") and len(line) > 30
    ][:3]

    agent = CoverLetterAgent(profile, router)
    letter = agent.generate(analysis, holder).text
    return letter


def to_pdf(markdown_text: str, output_dir: Path, name: str) -> Path:
    from hermes.utils.pdf_generator import generate_pdf

    output_dir.mkdir(parents=True, exist_ok=True)
    return generate_pdf(markdown_text, output_dir / f"{name}.pdf")
