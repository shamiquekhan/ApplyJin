"""JD Analyzer: structured extraction from raw job descriptions.

LLM path uses JSON mode with the jd_analyzer prompt. Heuristic fallback
extracts skills via a curated tech-keyword lexicon, seniority/years via
regex — deterministic and useful for tests and keyless runs.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from hermes.models import JobAnalysis, JobPosting
from hermes.utils.llm_router import LLMRouter, LLMUnavailable

logger = logging.getLogger("hermes.jd_analyzer")

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "jd_analyzer.txt"

# Curated tech lexicon for the heuristic extractor.
_LEXICON = [
    "Python", "Go", "Golang", "Rust", "Java", "JavaScript", "TypeScript",
    "C++", "C#", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "SQL",
    "React", "Vue", "Angular", "Svelte", "Next.js", "Node.js", "Django",
    "Flask", "FastAPI", "Spring", "Rails", ".NET", "GraphQL", "gRPC",
    "REST", "Kubernetes", "Docker", "Terraform", "Ansible", "AWS", "GCP",
    "Azure", "CI/CD", "Jenkins", "GitHub Actions", "GitLab", "Linux",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "RabbitMQ",
    "Elasticsearch", "Spark", "Airflow", "dbt", "Snowflake", "Hadoop",
    "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "LLM",
    "NLP", "machine learning", "deep learning", "TDD", "microservices",
    "observability", "Prometheus", "Grafana", "system design", "SRE",
]

_SENIORITY_RE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|junior|jr\.?|entry[- ]level|intern)\b",
    re.IGNORECASE,
)
_YEARS_RE = re.compile(
    r"(\d+)\s*\+?\s*(?:-\s*\d+\s*\+?\s*)?years?(?:\s+of)?(?:\s+experience)?",
    re.IGNORECASE,
)

_RED_FLAG_PATTERNS = [
    "unpaid", "rockstar", "ninja", "guru", "work hard play hard",
    "fast-paced environment", "wear many hats", "family culture",
    "competitive salary", "9/6", "996",
]


def _heuristic_skills(description: str) -> tuple[list[str], list[str]]:
    lowered = description.lower()
    found = []
    for term in _LEXICON:
        pattern = re.compile(re.escape(term.lower()), re.IGNORECASE)
        if pattern.search(lowered):
            found.append(term)
    return found, []


def _heuristic_seniority(description: str, title: str) -> tuple[str, int]:
    text = f"{title} {description}"
    level = "mid"
    match = _SENIORITY_RE.search(text)
    if match:
        token = match.group(1).lower()
        if token in ("staff", "principal"):
            level = "staff"
        elif token in ("senior", "sr.", "sr", "lead"):
            level = "senior"
        elif token in ("junior", "jr.", "jr", "entry-level", "entry level", "intern"):
            level = "junior"
    years = 0
    for years_match in _YEARS_RE.finditer(text):
        years = max(years, int(years_match.group(1)))
    return level, min(years, 20)


def _heuristic_red_flags(description: str) -> list[str]:
    lowered = description.lower()
    return [flag for flag in _RED_FLAG_PATTERNS if flag in lowered]


def _heuristic_remote_policy(description: str) -> str:
    lowered = description.lower()
    if "fully remote" in lowered or "100% remote" in lowered or "work from anywhere" in lowered:
        return "fully_remote"
    if "hybrid" in lowered:
        return "hybrid"
    if "on-site" in lowered or "onsite" in lowered or "in-office" in lowered:
        return "onsite"
    return "unspecified"


def heuristic_analyze(job: JobPosting) -> JobAnalysis:
    required, preferred = _heuristic_skills(job.description)
    level, years = _heuristic_seniority(job.description, job.title)
    return JobAnalysis(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        required_skills=required,
        preferred_skills=preferred,
        seniority_level=level,
        years_experience=years,
        must_have_keywords=[s for s in required[:8]],
        company_values=[],
        red_flags=_heuristic_red_flags(job.description),
        remote_policy=_heuristic_remote_policy(job.description),
        extractor="heuristic",
    )


_ALLOWED_LEVELS = {"junior", "mid", "senior", "staff"}


def _coerce_analysis(raw: dict, job: JobPosting) -> JobAnalysis:
    """Validate LLM output; drop anything malformed, keep the rest."""
    level = str(raw.get("seniority_level", "mid")).lower()
    if level not in _ALLOWED_LEVELS:
        level = "mid"
    years = raw.get("years_experience", 0)
    years = int(years) if isinstance(years, (int, float)) else 0
    salary = raw.get("salary_range")
    parsed_salary = None
    if isinstance(salary, (list, tuple)) and len(salary) == 2:
        try:
            parsed_salary = (int(salary[0]), int(salary[1]))
        except (TypeError, ValueError):
            parsed_salary = None

    list_fields = (
        "required_skills",
        "preferred_skills",
        "must_have_keywords",
        "company_values",
        "red_flags",
    )
    cleaned: dict[str, list] = {}
    for field in list_fields:
        value = raw.get(field, [])
        cleaned[field] = (
            [str(x) for x in value if x] if isinstance(value, list) else []
        )

    policy = str(raw.get("remote_policy", "unspecified")).lower()
    if policy not in ("fully_remote", "hybrid", "onsite", "unspecified"):
        policy = "unspecified"

    return JobAnalysis(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        required_skills=cleaned["required_skills"],
        preferred_skills=cleaned["preferred_skills"],
        seniority_level=level,
        years_experience=years,
        must_have_keywords=cleaned["must_have_keywords"],
        company_values=cleaned["company_values"],
        red_flags=cleaned["red_flags"],
        remote_policy=policy,
        salary_range=parsed_salary,
        extractor="llm",
    )


class JDAnalyzer:
    """LLM-first JD extraction with deterministic fallback."""

    def __init__(self, router: Optional[LLMRouter] = None) -> None:
        self.router = router
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    def analyze(self, job: JobPosting) -> JobAnalysis:
        if self.router is not None:
            try:
                raw = self.router.complete_json(
                    system=self._system_prompt,
                    prompt=(
                        f"Job title: {job.title}\nCompany: {job.company}\n\n"
                        f"Job description:\n{job.description[:8000]}"
                    ),
                )
                analysis = _coerce_analysis(raw, job)
                logger.debug("LLM analysis for %s: %d skills", job.job_id, len(analysis.required_skills))
                return analysis
            except LLMUnavailable as exc:
                logger.warning("LLM unavailable (%s) — using heuristic analysis", exc)
        return heuristic_analyze(job)
