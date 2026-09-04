"""JobScout: discover postings via JobSpy, with an offline fallback loader.

Primary path uses python-jobspy (LinkedIn, Indeed, Glassdoor, Google,
ZipRecruiter, Naukri, Bayt, BDJobs). When jobspy is not installed or the
network fails, falls back to data/sample_jobs.jsonl so the rest of the
pipeline (analysis, scoring, tailoring, tracking) remains testable offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from hermes.config import SearchEntry
from hermes.models import JobPosting
from hermes.utils.deduplicator import deduplicate_jobs

logger = logging.getLogger("hermes.scout")

_BOARD_ALIASES = {
    "linkedin": "linkedin",
    "indeed": "indeed",
    "glassdoor": "glassdoor",
    "google": "google",
    "zip_recruiter": "zip_recruiter",
    "ziprecruiter": "zip_recruiter",
    "naukri": "naukri",
    "bayt": "bayt",
    "bdjobs": "bdjobs",
}

_FALLBACK_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sample_jobs.jsonl"


def _row_to_posting(row, board: str) -> JobPosting:
    def _dt(value):
        if value is None:
            return None
        try:
            import pandas as pd

            return pd.Timestamp(value).to_pydatetime()
        except Exception:  # noqa: BLE001
            return None

    return JobPosting(
        job_id=str(row.get("id") or f"{board}-{row.get('title', '')[:40]}"),
        title=str(row.get("title") or ""),
        company=str(row.get("company") or ""),
        location=str(row.get("location") or ""),
        board=board,
        url=str(row.get("job_url") or row.get("job_url_direct") or ""),
        description=str(row.get("description") or ""),
        date_posted=_dt(row.get("date_posted")),
        is_remote=bool(row.get("is_remote") or False),
        salary_min=row.get("min_amount"),
        salary_max=row.get("max_amount"),
    )


def scout_with_jobspy(entry: SearchEntry) -> list[JobPosting]:
    from jobspy import scrape_jobs

    boards = [
        _BOARD_ALIASES.get(b.lower(), b.lower())
        for b in (entry.boards or ["indeed", "glassdoor", "google"])
    ]
    df = scrape_jobs(
        site_name=boards,
        search_term=entry.title,
        location=entry.location,
        results_wanted=entry.max_results,
        hours_old=entry.hours_old,
        is_remote=entry.remote_only,
    )
    postings = []
    for board, group in df.groupby("site", dropna=False):
        for _, row in group.iterrows():
            postings.append(_row_to_posting(row, str(board)))
    return postings


def _load_fallback(path: Optional[Path] = None) -> list[JobPosting]:
    source = path or _FALLBACK_PATH
    if not source.exists():
        return []
    postings = []
    with open(source, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record.setdefault("board", "offline")
            postings.append(JobPosting(**record))
    return postings


def scout_jobs(entry: SearchEntry, offline: bool = False) -> list[JobPosting]:
    """Run one search entry through JobSpy (or fallback), dedup, return."""
    postings: list[JobPosting] = []
    if offline:
        postings = _load_fallback()
    else:
        try:
            postings = scout_with_jobspy(entry)
        except Exception as exc:  # noqa: BLE001 — jobspy raises many types
            logger.warning(
                "JobSpy failed (%s). Falling back to sample jobs. "
                "Tip: pip install -e '.[scrape]' and check network.",
                exc,
            )
            postings = _load_fallback()

    postings = deduplicate_jobs(postings)
    logger.info(
        "Scout '%s' returned %d unique postings", entry.name, len(postings)
    )
    return postings
