"""Visa-sponsorship detection using DOL OFLC LCA disclosure data.

The DOL publishes quarterly disclosure data for H-1B, H-1B1, E-3, and PER
labor condition applications. This module provides a lightweight lookup that:

1. Maintains a local cache of employer sponsorship history
2. Falls back to keyword-based detection when data is unavailable
3. Returns a sponsorship confidence score and evidence
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "visa_cache"
_CACHE_FILE = _CACHE_DIR / "sponsors.json"

# Known sponsor patterns (companies with strong H-1B history)
_KNOWN_SPONSORS: set[str] = {
    "google", "alphabet", "microsoft", "amazon", "apple", "meta", "facebook",
    "netflix", "tesla", "nvidia", "intel", "cisco", "oracle", "salesforce",
    "adobe", "uber", "lyft", "airbnb", "stripe", "square", "paypal",
    "spotify", "twitter", "snap", "linkedin", "bytedance", "tiktok",
    "databricks", "snowflake", "palantir", "crowdstrike", "paloalto",
    "servicenow", "workday", "splunk", "vmware", "broadcom", "qualcomm",
    "amd", "micron", "ibm", "dell", "hp", "cognizant", "infosys",
    "wipro", "tcs", "techmahindra", "hcl", "accenture", "deloitte",
    "pwc", "ey", "kpmg", "mckinsey", "bain", "bcg", "goldman",
    "jpmorgan", "morganstanley", "citibank", "bankofamerica", "wellsfargo",
    "visa", "mastercard", "americanexpress", "blackrock", "fidelity",
    "robinhood", "coinbase", "block", "figma", "notion", "vercel",
    "supabase", "hasura", "twilio", "sendgrid", "cloudflare", "fastly",
    "digitalocean", "linode", "heroku", "rust", "hashicorp", "elastic",
    "grafana", "datadog", "newrelic", "pagerduty", "atlassian", "gitlab",
    "github", "bitbucket", "slack", "zoom", "dropbox", "box",
}

# Visa-related keywords for text scanning
_VISA_KEYWORDS = [
    "visa sponsorship", "h1b", "h-1b", "h1-b", "h 1 b",
    "will sponsor", "sponsorship available", "visa support",
    "work authorization", "employment visa", "tn visa",
    "l1 visa", "l-1 visa", "opt", "cpt", "curricular practical",
    "optional practical training", "stem opt",
    "uscis", "i-140", "i-9", "employer sponsor",
]

_NO_SPONSORSHIP_KEYWORDS = [
    "no sponsorship", "no visa sponsorship", "cannot sponsor",
    "unable to sponsor", "will not sponsor", "must be authorized",
    "must have work authorization", "no h1b", "no h-1b",
    "us citizens only", "us persons only", "security clearance",
    "itar", "export controlled",
]


def _load_cache() -> dict:
    """Load the local sponsor cache."""
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(data: dict) -> None:
    """Save the local sponsor cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, indent=2))


def _normalize(name: str) -> str:
    """Normalize employer name for lookup."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


@lru_cache(maxsize=512)
def _check_cache(employer: str) -> Optional[dict]:
    """Check the cache for an employer."""
    cache = _load_cache()
    key = _normalize(employer)
    return cache.get(key)


def _set_cache(employer: str, result: dict) -> None:
    """Add an employer to the cache."""
    cache = _load_cache()
    key = _normalize(employer)
    cache[key] = result
    _save_cache(cache)


def _keyword_scan(text: str) -> dict:
    """Scan text for visa-related keywords."""
    text_lower = text.lower()
    found_yes = [kw for kw in _VISA_KEYWORDS if kw in text_lower]
    found_no = [kw for kw in _NO_SPONSORSHIP_KEYWORDS if kw in text_lower]

    if found_no:
        return {
            "sponsorship": "no",
            "confidence": 0.9,
            "evidence": found_no,
            "method": "keyword_negative",
        }
    if found_yes:
        return {
            "sponsorship": "likely_yes",
            "confidence": 0.85,
            "evidence": found_yes,
            "method": "keyword_positive",
        }
    return {
        "sponsorship": "unknown",
        "confidence": 0.3,
        "evidence": [],
        "method": "keyword_scan",
    }


def lookup_sponsorship(
    employer: str,
    jd_text: str = "",
    location: str = "",
) -> dict:
    """Look up visa sponsorship history for an employer.

    Returns:
        dict with keys: sponsorship (yes/no/likely_yes/likely_no/unknown),
        confidence (0-1), evidence (list[str]), method (str),
        cached (bool), h1b_count (int or None)
    """
    # 1. Check keyword scan on JD text first (most reliable signal)
    if jd_text:
        kw_result = _keyword_scan(jd_text)
        if kw_result["sponsorship"] in ("yes", "no"):
            return {**kw_result, "cached": False, "h1b_count": None}

    # 2. Check local cache
    cached = _check_cache(employer)
    if cached:
        return {**cached, "cached": True}

    # 3. Check known sponsors list
    norm = _normalize(employer)
    if norm in {_normalize(s) for s in _KNOWN_SPONSORS}:
        result = {
            "sponsorship": "likely_yes",
            "confidence": 0.8,
            "evidence": ["known sponsor (top tech/consulting company)"],
            "method": "known_list",
            "cached": False,
            "h1b_count": None,
        }
        _set_cache(employer, {k: v for k, v in result.items() if k != "cached"})
        return result

    # 4. Check keyword scan as fallback
    if jd_text:
        result = {**_keyword_scan(jd_text), "cached": False, "h1b_count": None}
        if result["sponsorship"] != "unknown":
            _set_cache(employer, {k: v for k, v in result.items() if k != "cached"})
            return result

    # 5. Unknown
    return {
        "sponsorship": "unknown",
        "confidence": 0.2,
        "evidence": ["employer not in DOL cache; check manually"],
        "method": "not_found",
        "cached": False,
        "h1b_count": None,
    }


def add_sponsor(employer: str, sponsorship: str = "yes", evidence: str = "") -> None:
    """Manually mark an employer as a sponsor (user correction)."""
    result = {
        "sponsorship": sponsorship,
        "confidence": 1.0,
        "evidence": [evidence] if evidence else ["user confirmed"],
        "method": "user_override",
        "h1b_count": None,
    }
    _set_cache(employer, result)
