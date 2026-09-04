"""Email Triage: scan an IMAP inbox for application outcomes.

Classifies messages as interview / rejection / offer / follow-up using
keyword heuristics, fuzzy-matches the sender company against tracked
applications, and updates tracker statuses. ALWAYS starts in dry-run —
nothing is written without --apply.

Config (config/email_config.yml, gitignored):
    imap_host: imap.gmail.com
    imap_user: you@gmail.com
    imap_password: app-password   # Gmail: use an App Password
    folders: [INBOX]
    days_lookback: 30
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from hermes.agents.tracker import Tracker
from hermes.utils.deduplicator import _similarity

logger = logging.getLogger("hermes.triage")

CONFIG_PATH = Path("config/email_config.yml")

# Classification keyword sets, ordered by confidence.
_SIGNATURES = [
    (
        "offer",
        [
            "we are pleased to offer",
            "pleased to extend an offer",
            "offer of employment",
            "your offer letter",
            "congratulations! we'd like to offer",
        ],
    ),
    (
        "interview",
        [
            "invite you to interview",
            "interview invitation",
            "schedule an interview",
            "phone screen",
            "technical interview",
            "would like to speak with you",
            "next steps in the interview process",
            "move forward with your application",
            "book a call",
        ],
    ),
    (
        "rejected",
        [
            "we regret to inform",
            "unfortunately",
            "decided to move forward with other candidates",
            "not moving forward with your application",
            "position has been filled",
            "decided not to proceed",
            "pursuing other candidates",
        ],
    ),
    (
        "phone_screen",
        ["initial call", "recruiter call", "screening call"],
    ),
]

_FOLLOWUP_MARKERS = ["we received your application", "thank you for applying", "application status"]


@dataclass
class TriageMatch:
    application_id: Optional[int]
    company: str
    matched_company: str
    classification: str
    subject: str
    date: str
    similarity: float


@dataclass
class TriageReport:
    scanned: int = 0
    classified: int = 0
    matches: list[TriageMatch] = field(default_factory=list)
    unmatched: list[TriageMatch] = field(default_factory=list)
    updated: list[tuple[int, str]] = field(default_factory=list)

    def summary(self) -> list[str]:
        lines = [
            f"scanned: {self.scanned} messages, classified: {self.classified}"
        ]
        by_class: dict[str, int] = {}
        for m in self.matches + self.unmatched:
            by_class[m.classification] = by_class.get(m.classification, 0) + 1
        for cls, count in sorted(by_class.items()):
            lines.append(f"  {cls}: {count}")
        if self.updated:
            lines.append(
                "updated: "
                + ", ".join(f"#{rid}->{status}" for rid, status in self.updated)
            )
        return lines


def classify_message(subject: str, body: str) -> Optional[str]:
    """Return offer/interview/phone_screen/rejected/follow_up or None."""
    text = f"{subject}\n{body}".lower()
    for label, phrases in _SIGNATURES:
        if any(p in text for p in phrases):
            return label
    if any(p in text for p in _FOLLOWUP_MARKERS):
        return "follow_up"
    return None


def _company_from_sender(sender: str) -> str:
    """Best-effort company from a 'Name <user@domain.com>' header."""
    match = re.search(r"@([\w.-]+)", sender)
    if not match:
        return ""
    domain = match.group(1).lower()
    domain = re.sub(r".*\.(gmail|outlook|hotmail|yahoo)\..*", "", domain)
    parts = domain.split(".")
    # heuristic: company is usually the second-level domain
    return parts[0] if parts else domain


class EmailTriageAgent:
    def __init__(self, tracker: Tracker) -> None:
        self.tracker = tracker

    # ----------------------------------------------------- connection

    def _load_config(self) -> dict:
        import yaml

        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                "config/email_config.yml not found. Copy "
                "config/email_config.example.yml and add an IMAP app-password."
            )
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}

    def _fetch_messages(self, cfg: dict) -> list:
        import imaplib

        since = (datetime.now() - timedelta(days=cfg.get("days_lookback", 30))).strftime("%d-%b-%Y")
        mail = imaplib.IMAP4_SSL(cfg["imap_host"])
        mail.login(cfg["imap_user"], cfg["imap_password"])
        messages = []
        for folder in cfg.get("folders", ["INBOX"]):
            status, _ = mail.select(f'"{folder}"', readonly=True)
            if status != "OK":
                continue
            _, data = mail.search(None, f'(SINCE "{since}")')
            for num in data[0].split():
                _, fetched = mail.fetch(num, "(RFC822)")
                if fetched and fetched[0] is not None:
                    messages.append(fetched[0][1])
        mail.logout()
        return messages

    # ------------------------------------------------------- main flow

    def triage(self, apply: bool = False) -> TriageReport:
        report = TriageReport()
        cfg = self._load_config()
        raw_messages = self._fetch_messages(cfg)
        parser = BytesParser(policy=policy.default)

        apps = self.tracker.list_applications()
        for raw in raw_messages:
            msg = parser.parsebytes(raw)
            subject = str(msg.get("subject", ""))
            body = _extract_body(msg)
            classification = classify_message(subject, body)
            if classification is None or classification == "follow_up":
                continue
            report.scanned += 1
            report.classified += 1

            sender = str(msg.get("from", ""))
            company = _company_from_sender(sender)
            match = self._match_company(company, apps)
            record = TriageMatch(
                application_id=match["id"] if match else None,
                company=company,
                matched_company=match["company"] if match else "",
                classification=classification,
                subject=subject[:80],
                date=str(msg.get("date", ""))[:20],
                similarity=match["similarity"] if match else 0.0,
            )
            if match and apply:
                status = _status_for(classification)
                if status and not _already_advanced(match["status"], status):
                    self.tracker.update_status(
                        match["id"], status, f"email_triage: {subject[:60]}"
                    )
                    self.tracker.conn.execute(
                        "UPDATE applications SET outcome_source = 'email_triage' "
                        "WHERE id = ?",
                        (match["id"],),
                    )
                    self.tracker.conn.commit()
                    report.updated.append((match["id"], status))
            (report.matches if match else report.unmatched).append(record)
        return report

    # ------------------------------------------------------- matching

    def _match_company(self, company: str, apps: list) -> Optional[dict]:
        """Fuzzy-match sender company against tracked application companies."""
        if not company:
            return None
        best: Optional[dict] = None
        best_score = 0.0
        for app in apps:
            score = _similarity(company, app.company)
            if score > best_score:
                best_score = score
                best = {
                    "id": app.id,
                    "company": app.company,
                    "status": app.status,
                    "similarity": score,
                }
        return best if best_score >= 0.7 else None


_STATUS_MAP = {
    "offer": "offer",
    "interview": "interview",
    "phone_screen": "phone_screen",
    "rejected": "rejected",
}


def _status_for(classification: str) -> Optional[str]:
    return _STATUS_MAP.get(classification)


_PROGRESS = ["no_response", "rejected", "phone_screen", "interview", "offer"]


def _already_advanced(current: str, new: str) -> bool:
    """Don't downgrade: a later positive email can't un-interview you."""
    if current in _PROGRESS and new in _PROGRESS:
        return _PROGRESS.index(current) >= _PROGRESS.index(new)
    return current == new


def _extract_body(msg) -> str:
    """Body text from a parsed email message (multipart aware)."""
    try:
        if msg.is_multipart():
            parts = []
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    parts.append(part.get_content())
            return " ".join(parts)[:2000]
        body = msg.get_content()
        return body[:2000] if isinstance(body, str) else ""
    except Exception:  # noqa: BLE001
        return ""
