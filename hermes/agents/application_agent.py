"""Application Agent: navigate, detect ATS, fill forms — STOP before submit.

HARD RULE: this agent never clicks a submit button. It fills fields,
uploads documents, and pauses with the browser open so the human can
review and click submit personally. URLs can also be opened with zero
filling (--dry-run) to keep the human fully in the loop.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hermes.config import Profile
from hermes.utils.stealth_browser import StealthBrowser

logger = logging.getLogger("hermes.application_agent")

ANSWER_BANK_PATH = Path("config/answer_bank.yml")

# ---------------------------------------------------------------- detection

_ATS_PATTERNS: dict[str, list[str]] = {
    "greenhouse": ["boards.greenhouse.io", "job-boards.greenhouse.io", "greenhouse.io"],
    "lever": ["jobs.lever.co", "lever.co"],
    "workday": ["myworkdays.com", "myworkdayjobs.com", "workday.com"],
    "ashby": ["jobs.ashbyhq.com", "ashbyhq.com"],
    "jobvite": ["jobvite.com"],
    "smartrecruiters": ["smartrecruiters.com"],
    "bamboohr": ["bamboohr.com"],
    "linkedin_easy_apply": ["linkedin.com/jobs", "linkedin.com"],
}

_EASY_APPLY_SELECTOR = "jobs-search-box__easy-apply, .jobs-apply-button"


@dataclass
class FillResult:
    job_id: str
    url: str
    ats_type: str = "unknown"
    fields_filled: list[str] = field(default_factory=list)
    files_uploaded: list[str] = field(default_factory=list)
    submitted: bool = False  # always False — human clicks submit
    stopped_at: str = ""
    notes: list[str] = field(default_factory=list)


def detect_ats(url: str, page=None) -> str:
    """Classify the ATS platform from URL patterns and page markers."""
    lowered = (url or "").lower()
    for ats, patterns in _ATS_PATTERNS.items():
        if any(p in lowered for p in patterns):
            if ats == "linkedin_easy_apply" and page is not None:
                try:
                    if page.locator(_EASY_APPLY_SELECTOR).count() > 0:
                        return "linkedin_easy_apply"
                except Exception:  # noqa: BLE001
                    pass
            return ats
    return "unknown"


# ---------------------------------------------------------------- form filling

_TEXT_FIELD_HINTS = [
    ("first name", "first_name"),
    ("last name", "last_name"),
    ("full name", "full_name"),
    ("email", "email"),
    ("phone", "phone"),
    ("linkedin", "linkedin"),
    ("github", "github"),
    ("website", "website"),
    ("portfolio", "website"),
]

# Screening questions (textareas / long inputs) matched by keyword.
_SCREENING_HINTS = [
    "authorized to work", "work authorization", "visa",
    "relocate", "relocation",
    "start date", "earliest start", "when can you start",
    "salary", "compensation", "pay expectations",
    "why do you want", "why this company", "why are you interested",
    "remote", "work from home",
    "years of experience", "how many years",
    "notice period",
]


def _profile_answer(profile: Profile, hint: str) -> Optional[str]:
    ident = profile.identity
    mapping = {
        "first_name": ident.name.split(" ")[0] if ident.name else None,
        "last_name": " ".join(ident.name.split(" ")[1:]) if ident.name and " " in ident.name else None,
        "full_name": ident.name or None,
        "email": ident.email or None,
        "phone": ident.phone or None,
        "linkedin": ident.linkedin or None,
        "github": ident.github or None,
        "website": ident.website or None,
    }
    return mapping.get(hint)


def _find_text_input(page, label_text: str):
    """Locate a visible text input whose label/placeholder matches."""
    for selector in (
        f"label:has-text('{label_text}') >> xpath=following-sibling::input | "
        f"//label[contains(., '{label_text}')]/following::input[1]",
        f"input[placeholder*='{label_text}' i]",
        f"input[id*='{label_text.replace(' ', '_')}' i]",
    ):
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=500):
                return loc
        except Exception:  # noqa: BLE001
            continue
    return None


def fill_common_fields(page, profile: Profile) -> list[str]:
    """Best-effort fill of the standard identity fields."""
    filled: list[str] = []
    for label, hint in _TEXT_FIELD_HINTS:
        answer = _profile_answer(profile, hint)
        if not answer:
            continue
        loc = _find_text_input(page, label)
        if loc is None:
            continue
        try:
            loc.fill(answer)
            filled.append(hint)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not fill %s: %s", hint, exc)
    return filled


def upload_resume(page, resume_path) -> bool:
    """Upload the tailored resume to the first visible file input."""
    try:
        file_input = page.locator("input[type='file']").first
        if not file_input.count():
            return False
        file_input.set_input_files(str(resume_path))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Resume upload failed: %s", exc)
        return False


def _load_answer_bank() -> dict[str, str]:
    import yaml

    if not ANSWER_BANK_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(ANSWER_BANK_PATH.read_text(encoding="utf-8")) or {}
        return {
            key: str(entry.get("answer", "")) if isinstance(entry, dict) else str(entry)
            for key, entry in data.items()
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("Answer bank unreadable: %s", exc)
        return {}


def _answer_for_question(question_text: str, bank: dict[str, str]) -> Optional[str]:
    """Bank answer whose keys appear in the question text."""
    lowered = question_text.lower()
    for key, answer in bank.items():
        if key.replace("_", " ") in lowered:
            return answer
    return None


def fill_screening_questions(page, profile: Profile, router=None) -> list[str]:
    """Fill screening-question textareas using the answer bank.

    Only touches textarea/long-text fields whose question text matches a
    known screening topic. Honesty rule: the bank is human-authored.
    """
    filled: list[str] = []
    bank = _load_answer_bank()
    if not bank:
        return filled
    try:
        textareas = page.locator("textarea").all()
    except Exception as exc:  # noqa: BLE001
        logger.debug("textarea scan failed: %s", exc)
        return filled
    for area in textareas:
        try:
            if not area.is_visible(timeout=300):
                continue
            placeholder = (area.get_attribute("placeholder") or "").lower()
            aria_label = (area.get_attribute("aria-label") or "").lower()
            question_text = f"{placeholder} {aria_label}"
            matched_hint = any(
                hint in question_text for hint in _SCREENING_HINTS
            )
            if not matched_hint:
                continue
            answer = _answer_for_question(question_text, bank)
            if answer:
                area.fill(answer)
                label = placeholder or aria_label or "screening question"
                filled.append(label[:30])
        except Exception:  # noqa: BLE001
            continue
    return filled


# ---------------------------------------------------------------- agent


class ApplicationAgent:
    """Auto-fill, never auto-submit."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def fill(
        self,
        url: str,
        job_id: str,
        resume_path,
        coverletter_path=None,
        dry_run: bool = False,
        headless: bool = False,
        on_pause=None,
    ) -> FillResult:
        """Open the application page and fill identity fields.

        Stops before submit in all cases. `on_pause` receives the FillResult
        for integration tests / non-interactive flows; production runs block
        on input() so the human reviews the live browser.
        """
        result = FillResult(job_id=job_id, url=url)

        with StealthBrowser(headless=headless) as browser:
            page = browser.page
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_load_state("networkidle", timeout=20000)

            result.ats_type = detect_ats(url, page)

            if dry_run:
                result.stopped_at = "dry_run — page opened, nothing filled"
                result.notes.append("Review the posting manually in the open browser.")
            else:
                result.fields_filled = fill_common_fields(page, self.profile)
                result.fields_filled.extend(
                    fill_screening_questions(page, self.profile)
                )
                uploaded = upload_resume(page, resume_path)
                if uploaded:
                    result.files_uploaded.append("resume")
                if coverletter_path and _looks_like_two_file_fields(page):
                    if upload_resume(page, coverletter_path):
                        result.files_uploaded.append("cover_letter")
                result.stopped_at = (
                    "before_submit — review and click submit manually"
                )

            result.submitted = False
            logger.info(
                "Filled %s fields for %s (ats=%s). Stopped: %s",
                len(result.fields_filled), job_id, result.ats_type,
                result.stopped_at,
            )

            if on_pause is not None:
                on_pause(result)
            else:
                try:
                    input(
                        "\n>>> Form filled. Review in the browser window, then "
                        "click submit there yourself.\n>>> Press Enter here to close the browser... "
                    )
                except EOFError:
                    # Non-interactive session (CI/pipe): close immediately.
                    pass
        return result


def _looks_like_two_file_fields(page) -> bool:
    try:
        return page.locator("input[type='file']").count() >= 2
    except Exception:  # noqa: BLE001
        return False
