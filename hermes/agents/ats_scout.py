"""ATS board scout: pull postings straight from Greenhouse/Lever public APIs.

Company career pages on these ATS platforms expose JSON endpoints:
  Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
  Lever:      https://api.lever.co/v0/postings/{company}?mode=json

Advantages vs scraping: ToS-friendly public endpoints, no bot detection,
structured data with full JD text. The company slug is the same one in
their careers URL (boards.greenhouse.io/{company}).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

from hermes.models import JobPosting

logger = logging.getLogger("hermes.ats_scout")

_TIMEOUT = 20
_UA = "Mozilla/5.0 (X11; Linux x86_64) hermes-agent/0.4"


def _http_get_json(url: str) -> Optional[dict]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("GET %s failed: %s", url, exc)
        return None


def _gh_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def scrape_greenhouse(company: str, keywords: Optional[str] = None) -> list[JobPosting]:
    """Pull all postings from a company's public Greenhouse board."""
    slug = _slugify(company)
    data = _http_get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    )
    if not data or "jobs" not in data:
        return []
    postings = []
    for job in data["jobs"]:
        title = job.get("title", "")
        if keywords and not _matches(title, keywords):
            continue
        postings.append(
            JobPosting(
                job_id=f"greenhouse-{job.get('id')}",
                title=title,
                company=job.get("company", {}).get("name", company) or company,
                location=job.get("location", {}).get("name", "") if isinstance(job.get("location"), dict) else "",
                board="greenhouse",
                url=job.get("absolute_url", ""),
                description=job.get("content") or "",
                date_posted=_gh_date(job.get("updated_at") or job.get("first_published")),
                is_remote=_looks_remote(title, job.get("location", {}).get("name", "") if isinstance(job.get("location"), dict) else ""),
            )
        )
    return postings


def scrape_lever(company: str, keywords: Optional[str] = None) -> list[JobPosting]:
    """Pull all postings from a company's public Lever board."""
    slug = _slugify(company)
    data = _http_get_json(
        f"https://api.lever.co/v0/postings/{slug}?mode=json"
    )
    if not isinstance(data, list):
        return []
    postings = []
    for job in data:
        title = job.get("text", "")
        if keywords and not _matches(title, keywords):
            continue
        categories = job.get("categories", {}) or {}
        location = categories.get("location", "") or ""
        postings.append(
            JobPosting(
                job_id=f"lever-{job.get('id')}",
                title=title,
                company=job.get("categories", {}).get("team", company) or company,
                location=location,
                board="lever",
                url=job.get("hostedUrl", ""),
                description=job.get("description", {}).get("plain", "") if isinstance(job.get("description"), dict) else (job.get("description") or ""),
                date_posted=_epoch_to_dt(job.get("createdAt")),
                is_remote=_looks_remote(title, location),
            )
        )
    return postings


def scrape_at_boards(
    companies: list[str], keywords: Optional[str] = None
) -> list[JobPosting]:
    """Try Greenhouse then Lever for each company; return everything found."""
    postings: list[JobPosting] = []
    for company in companies:
        gh = scrape_greenhouse(company, keywords)
        if gh:
            postings.extend(gh)
            continue
        lv = scrape_lever(company, keywords)
        if lv:
            postings.extend(lv)
    logger.info("ATS board scout found %d postings for %d companies",
                len(postings), len(companies))
    return postings


# ---------------------------------------------------------------- helpers


def _slugify(name: str) -> str:
    lowered = name.lower().strip()
    slug = re.sub(r"[^a-z0-9-]+", "-", lowered).strip("-")
    return slug or lowered


def _matches(title: str, keywords: str) -> bool:
    return keywords.lower() in title.lower()


def _looks_remote(title: str, location: str) -> bool:
    text = f"{title} {location}".lower()
    return "remote" in text or "anywhere" in text


def _epoch_to_dt(value) -> Optional[datetime]:
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value / 1000)
    return None


def guess_slug_from_url(url: str) -> Optional[str]:
    """Extract the company slug from a careers URL.

    e.g. https://boards.greenhouse.io/acme/jobs/123 -> 'acme'
         https://jobs.lever.co/acme/abc -> 'acme'
    """
    match = re.search(
        r"(?:boards?\.greenhouse\.io|jobs\.lever\.co)/([a-z0-9-]+)/", url or ""
    )
    return match.group(1) if match else None
