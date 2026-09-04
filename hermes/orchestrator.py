"""Orchestrator: runs the Phase-1 pipeline.

scout -> analyze -> score -> filter -> tailor -> cover letter
-> write artifacts to data/applications/<job>/ -> tracker (pending_review)

Human review (`hermes review`) is the final gate before anything is
considered submitted. Nothing in this module ever submits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hermes.agents.cover_letter import CoverLetterAgent
from hermes.agents.fit_scorer import FitScorer
from hermes.agents.jd_analyzer import JDAnalyzer
from hermes.agents.job_scout import scout_jobs
from hermes.agents.resume_tailor import ResumeTailor
from hermes.agents.tracker import Tracker
from hermes.config import (
    APPLICATIONS_DIR,
    Profile,
    SearchEntry,
    SearchConfigs,
    ensure_dirs,
    load_profile,
    load_search_configs,
)
from hermes.models import ApplicationRecord, JobPosting
from hermes.utils.ats_scorer import ATSScorer
from hermes.utils.experience_library import ExperienceLibrary
from hermes.utils.helpers import sha256_short, slugify
from hermes.utils.llm_router import LLMRouter
from hermes.utils.pdf_generator import generate_pdf
from hermes.utils.resume_parser import parse_resume

logger = logging.getLogger("hermes.orchestrator")

DEFAULT_RESUME_PATHS = (
    Path("data/base_resume.md"),
    Path("data/base_resume.txt"),
    Path("data/base_resume.pdf"),
)


@dataclass
class PipelineResult:
    discovered: int = 0
    analyzed: int = 0
    passed_filter: int = 0
    tailored: int = 0
    tracked: int = 0
    skipped: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


def find_base_resume(project_root: Optional[Path] = None) -> Optional[Path]:
    root = project_root or Path.cwd()
    for rel in DEFAULT_RESUME_PATHS:
        candidate = root / rel
        if candidate.exists():
            return candidate
    for pattern in ("data/*.pdf", "data/*.md", "data/*.txt"):
        matches = sorted((root / "data").glob(pattern)) if (root / "data").exists() else []
        if matches:
            return matches[0]
    return None


class Orchestrator:
    def __init__(
        self,
        profile: Optional[Profile] = None,
        router: Optional[LLMRouter] = None,
        tracker: Optional[Tracker] = None,
        base_resume_path: Optional[Path] = None,
    ) -> None:
        ensure_dirs()
        self.profile = profile or load_profile()
        self.router = router
        self.tracker = tracker or Tracker(
            Path("data/hermes.db")
        )
        self.resume_path = base_resume_path
        if self.resume_path is None and self.profile.resume_path:
            candidate = Path(self.profile.resume_path)
            if not candidate.is_absolute():
                candidate = Path("data") / candidate.name
            if candidate.exists():
                self.resume_path = candidate
        if self.resume_path is None:
            self.resume_path = find_base_resume()
        if self.resume_path is None:
            raise FileNotFoundError(
                "No base resume found. Place data/base_resume.md "
                "(or .txt/.pdf) or pass --resume."
            )
        self.resume = parse_resume(self.resume_path, self.profile)
        self.library = ExperienceLibrary()
        self.analyzer = JDAnalyzer(router)
        self.scorer = FitScorer(self.profile, self.profile.limits.min_fit_score)
        # Phase 3: inject the active learned style guide into the tailor.
        version, guide = self.tracker.active_style_guide()
        if guide:
            logger.info("Using learned style guide v%s", version)
        self.tailor = ResumeTailor(router, library=self.library, style_guide=guide)
        self.cover = CoverLetterAgent(self.profile, router)
        self.ats = ATSScorer()

    # ----------------------------------------------------------- pipeline

    def run(
        self,
        search: Optional[SearchEntry] = None,
        offline: bool = False,
        limit: Optional[int] = None,
    ) -> PipelineResult:
        result = PipelineResult()

        searches: list[SearchEntry]
        if search is not None:
            searches = [search]
        else:
            configs: SearchConfigs = load_search_configs(profile=self.profile)
            searches = configs.searches or [
                SearchEntry(
                    name="default",
                    title=(self.profile.target.titles or ["Software Engineer"])[0],
                    location=self.profile.identity.location or "Remote",
                    boards=self.profile.preferences.boards,
                    max_results=self.profile.preferences.max_results_per_board,
                    hours_old=self.profile.preferences.max_age_days * 24,
                    remote_only=self.profile.preferences.remote_only,
                )
            ]

        jobs: list[JobPosting] = []
        for entry in searches:
            try:
                jobs.extend(scout_jobs(entry, offline=offline))
            except Exception as exc:  # noqa: BLE001
                result.blocked.append(f"scout:{entry.name}: {exc}")
        jobs = _dedupe_by_id(jobs)
        result.discovered = len(jobs)

        for job in jobs[:limit] if limit else jobs:
            self._process_job(job, result)

        return result

    # ----------------------------------------------------------- helpers

    def _process_job(self, job: JobPosting, result: PipelineResult) -> None:
        tag = f"{job.company} — {job.title}"

        if self.tracker.has_job(job.job_id):
            result.skipped.append(f"{tag}: already tracked, skipping")
            return
        if job.company.lower() in [c.lower() for c in self.profile.preferences.blocked_companies]:
            result.skipped.append(f"{tag}: company blocked by preferences")
            return

        analysis = self.analyzer.analyze(job)
        result.analyzed += 1

        scored = self.scorer.score(job, analysis, self.resume)
        if not scored.passed_filter:
            result.skipped.append(f"{tag}: {scored.reject_reason}")
            return
        result.passed_filter += 1

        # Phase 3: random A/B assignment of the resume style variant.
        from hermes.agents.ab_testing import assign_variant

        variant = assign_variant()

        tailored = self.tailor.tailor(self.resume, job, analysis, variant=variant)
        letter = self.cover.generate(analysis, tailored)
        result.tailored += 1

        ats_before = round(
            self.ats.score(self.resume.raw_text, analysis.required_skills, job.description),
            3,
        )
        ats_after = round(
            self.ats.score(tailored.text, analysis.required_skills, job.description),
            3,
        )

        paths = _write_artifacts(job, tailored.markdown, letter.text)

        # Phase 2: export the tailored resume to PDF (best-effort).
        try:
            pdf_path = generate_pdf(tailored.markdown, paths["resume"].with_suffix(".pdf"))
            paths["pdf"] = pdf_path
        except Exception as exc:  # noqa: BLE001
            logger.debug("PDF export skipped for %s: %s", job.job_id, exc)

        record = ApplicationRecord(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            board=job.board,
            url=job.url,
            status="pending_review",
            fit_score=scored.fit_score,
            ats_score_before=ats_before,
            ats_score_after=ats_after,
            resume_variant_hash=sha256_short(tailored.text),
            coverletter_hash=sha256_short(letter.text),
            tailored_resume_path=str(paths["resume"]),
            coverletter_path=str(paths["letter"]),
            notes=_notes_for(scored, tailored, letter),
            variant=variant,
        )
        row_id, message = self.tracker.add_application(
            record, max_per_day=self.profile.limits.max_applications_per_day
        )
        if row_id is None:
            result.blocked.append(f"{tag}: {message}")
        else:
            result.tracked += 1
            logger.info("Queued for review: %s (fit=%.2f, ATS %.2f->%.2f)",
                        tag, scored.fit_score, ats_before, ats_after)


def _dedupe_by_id(jobs: list[JobPosting]) -> list[JobPosting]:
    seen: set[str] = set()
    unique = []
    for job in jobs:
        if job.job_id in seen:
            continue
        seen.add(job.job_id)
        unique.append(job)
    return unique


def _write_artifacts(job: JobPosting, resume_md: str, letter_text: str) -> dict[str, Path]:
    folder = APPLICATIONS_DIR / f"{job.job_id[:8]}-{slugify(f'{job.company}-{job.title}')}"
    folder.mkdir(parents=True, exist_ok=True)
    resume_path = folder / "resume.md"
    letter_path = folder / "cover_letter.md"
    meta_path = folder / "job.md"
    resume_path.write_text(resume_md, encoding="utf-8")
    letter_path.write_text(letter_text, encoding="utf-8")
    meta_path.write_text(
        f"# {job.title} — {job.company}\n\n"
        f"- Board: {job.board}\n- URL: {job.url}\n"
        f"- Location: {job.location}\n\n## Description\n\n{job.description}\n",
        encoding="utf-8",
    )
    return {"resume": resume_path, "letter": letter_path, "meta": meta_path}


def _notes_for(scored, tailored, letter) -> str:
    parts = []
    breakdown = scored.score_breakdown
    matched = breakdown.get("matched") or []
    missing = breakdown.get("missing") or []
    if matched:
        parts.append(f"matched: {', '.join(matched[:8])}")
    if missing:
        parts.append(f"missing: {', '.join(missing[:8])}")
    if tailored.guardrail_violations:
        parts.append(f"GUARDRAIL: {tailored.guardrail_violations}")
    parts.append(f"tailor_model={tailored.model_used}")
    parts.append(f"letter_model={letter.model_used}")
    return " | ".join(parts)
