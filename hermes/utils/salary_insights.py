"""Salary insights using Adzuna free-tier API + BLS data.

Provides salary range estimation for job titles using:
1. Adzuna free-tier API (1000 calls/month, good for US/UK)
2. BLS Occupational Employment Statistics (OES) for median/percentile data
3. Heuristic fallback based on role level + location cost-of-living
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import httpx

_ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
_ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

_BLS_CACHE = Path(__file__).resolve().parent.parent.parent / "config" / "salary_cache" / "bls_oes.json"

# BLS OES 2023 median salaries for common tech roles (SOC code → salary)
# Source: BLS Occupational Employment and Wage Statistics
_BLS_SALARIES: dict[str, int] = {
    "software developer": 132270,
    "software engineer": 132270,
    "data scientist": 108020,
    "data analyst": 82360,
    "data engineer": 103560,
    "machine learning engineer": 132270,
    "devops engineer": 125560,
    "site reliability engineer": 132270,
    "cloud engineer": 125560,
    "cybersecurity analyst": 120360,
    "information security analyst": 120360,
    "network engineer": 97270,
    "systems administrator": 90520,
    "database administrator": 101340,
    "web developer": 92750,
    "front end developer": 92750,
    "back end developer": 132270,
    "full stack developer": 132270,
    "mobile developer": 132270,
    "ios developer": 132270,
    "android developer": 132270,
    "ux designer": 92750,
    "ui designer": 92750,
    "product manager": 159660,
    "project manager": 100750,
    "technical program manager": 132270,
    "engineering manager": 163290,
    "director of engineering": 180000,
    "vp of engineering": 200000,
    "cto": 200000,
    "qa engineer": 103560,
    "quality assurance engineer": 103560,
    "test engineer": 103560,
    "scrum master": 100750,
    "business analyst": 96310,
    "technical writer": 82360,
    "it support": 60050,
    "help desk": 60050,
    "sales engineer": 116190,
    "solutions architect": 132270,
    "technical architect": 132270,
    "data analyst": 82360,
}

# Location cost-of-living multipliers (relative to national average = 1.0)
_LOCATION_MULTIPLIER: dict[str, float] = {
    "san francisco": 1.79,
    "sf": 1.79,
    "bay area": 1.79,
    "new york": 1.47,
    "nyc": 1.47,
    "seattle": 1.49,
    "boston": 1.38,
    "los angeles": 1.37,
    "la": 1.37,
    "san diego": 1.29,
    "austin": 1.10,
    "chicago": 1.08,
    "denver": 1.13,
    "miami": 1.13,
    "atlanta": 1.02,
    "dallas": 1.02,
    "houston": 1.00,
    "phoenix": 0.98,
    "philadelphia": 1.04,
    "washington": 1.33,
    "dc": 1.33,
    "remote": 1.0,
    "anywhere": 1.0,
    "united states": 1.0,
    "usa": 1.0,
    "london": 1.38,
    "uk": 1.1,
    "canada": 1.05,
    "toronto": 1.15,
    "vancouver": 1.15,
    "bangalore": 0.45,
    "bengaluru": 0.45,
    "india": 0.35,
    "hyderabad": 0.4,
    "pune": 0.4,
    "mumbai": 0.5,
    "germany": 1.1,
    "berlin": 1.1,
}


def _detect_level(title: str) -> str:
    """Detect role level from title."""
    title_lower = title.lower()
    if any(w in title_lower for w in ("vp", "vice president", "chief", "head of")):
        return "executive"
    if any(w in title_lower for w in ("director", "principal", "staff")):
        return "senior"
    if any(w in title_lower for w in ("senior", "sr.", "sr ", "lead", "architect")):
        return "senior"
    if any(w in title_lower for w in ("junior", "jr.", "jr ", "intern", "entry", "associate", "assistant")):
        return "junior"
    if any(w in title_lower for w in ("mid", "intermediate")):
        return "mid"
    return "mid"  # default


def _bls_lookup(title: str) -> Optional[int]:
    """Look up salary from BLS OES data."""
    title_lower = title.lower()
    # Try exact match first
    for role, salary in _BLS_SALARIES.items():
        if role in title_lower or title_lower in role:
            return salary
    # Try partial match
    for role, salary in _BLS_SALARIES.items():
        if any(word in title_lower for word in role.split() if len(word) > 3):
            return salary
    return None


def _adzuna_search(title: str, location: str = "", country: str = "us") -> Optional[dict]:
    """Search Adzuna API for salary data."""
    if not _ADZUNA_APP_ID or not _ADZUNA_APP_KEY:
        return None
    try:
        params = {
            "app_id": _ADZUNA_APP_ID,
            "app_key": _ADZUNA_APP_KEY,
            "results_per_page": 10,
            "what": title,
            "content-type": "application/json",
        }
        if location:
            params["where"] = location

        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        resp = httpx.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        salaries = []
        for job in data.get("results", []):
            if job.get("salary_min"):
                salaries.append(job["salary_min"])
            if job.get("salary_max"):
                salaries.append(job["salary_max"])

        if salaries:
            return {
                "min": min(salaries),
                "max": max(salaries),
                "median": sorted(salaries)[len(salaries) // 2],
                "source": "adzuna",
                "sample_size": len(salaries),
            }
    except Exception:
        pass
    return None


def _heuristic_salary(title: str, location: str = "") -> dict:
    """Heuristic salary estimate based on role level + location."""
    base = _bls_lookup(title)
    if not base:
        # Default to US median for unknown roles
        base = 85000

    level = _detect_level(title)
    level_mult = {
        "junior": 0.7,
        "mid": 1.0,
        "senior": 1.35,
        "executive": 1.8,
    }.get(level, 1.0)

    # Location multiplier — sort keys longest-first to avoid false matches
    loc_mult = 1.0
    loc_lower = location.lower()
    for city in sorted(_LOCATION_MULTIPLIER, key=len, reverse=True):
        if city in loc_lower:
            loc_mult = _LOCATION_MULTIPLIER[city]
            break

    adjusted = int(base * level_mult * loc_mult)
    # Salary range: ±20% of adjusted
    return {
        "min": int(adjusted * 0.8),
        "max": int(adjusted * 1.2),
        "median": adjusted,
        "source": "bls_heuristic",
        "level": level,
        "location_multiplier": loc_mult,
        "bls_base": base,
    }


def get_salary_insights(title: str, location: str = "", company: str = "") -> dict:
    """Get salary insights for a job title.

    Tries Adzuna API first, then BLS data, then heuristic fallback.

    Returns:
        dict with min, max, median, source, and additional context
    """
    # 1. Try Adzuna API
    adzuna = _adzuna_search(title, location)
    if adzuna:
        return {**adzuna, "cached": False}

    # Location multiplier — sort keys longest-first so "los angeles" matches
    # before "la", "san francisco" before "sf", etc.
    loc_mult = 1.0
    loc_lower = location.lower()
    for city in sorted(_LOCATION_MULTIPLIER, key=len, reverse=True):
        if city in loc_lower:
            loc_mult = _LOCATION_MULTIPLIER[city]
            break

    # Apply level multiplier (works for all paths now)
    level = _detect_level(title)
    level_mult = {
        "junior": 0.7,
        "mid": 1.0,
        "senior": 1.35,
        "executive": 1.8,
    }.get(level, 1.0)

    # 2. BLS lookup
    bls_salary = _bls_lookup(title)
    if bls_salary:
        adjusted = int(bls_salary * loc_mult * level_mult)
        return {
            "min": int(adjusted * 0.8),
            "max": int(adjusted * 1.2),
            "median": adjusted,
            "source": "bls_oes",
            "bls_base": bls_salary,
            "location_multiplier": loc_mult,
            "cached": False,
        }

    # 3. Heuristic fallback
    return {**_heuristic_salary(title, location), "cached": False}
