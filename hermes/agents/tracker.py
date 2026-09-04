"""Tracker: SQLite single source of truth for all applications.

Implements the schema from hermes_guide.md § 6.7 with the daily rate limit
and duplicate-application guardrails built into `add_application`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from hermes.models import ApplicationRecord

logger = logging.getLogger("hermes.tracker")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE,
    title TEXT,
    company TEXT,
    board TEXT,
    url TEXT,
    applied_at TIMESTAMP,
    status TEXT CHECK(status IN (
        'draft','pending_review','approved','rejected_by_user',
        'submitted','no_response','rejected','phone_screen',
        'interview','offer','declined')),
    fit_score REAL,
    ats_score_before REAL,
    ats_score_after REAL,
    resume_variant_hash TEXT,
    coverletter_hash TEXT,
    tailored_resume_path TEXT,
    coverletter_path TEXT,
    notes TEXT,
    variant TEXT DEFAULT 'A',
    outcome_source TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_applied ON applications(applied_at);
CREATE TABLE IF NOT EXISTS learning_patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT,
    pattern_value TEXT,
    correlation_score REAL,
    sample_size INTEGER,
    discovered_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS style_guide_versions (
    id INTEGER PRIMARY KEY,
    version INTEGER,
    applied_at TIMESTAMP,
    source TEXT,
    style_guide TEXT,
    active INTEGER DEFAULT 0,
    notes TEXT
);
"""

# Column additions for databases created before Phase 3.
_MIGRATIONS = [
    "ALTER TABLE applications ADD COLUMN variant TEXT DEFAULT 'A'",
    "ALTER TABLE applications ADD COLUMN outcome_source TEXT DEFAULT ''",
]


class Tracker:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(applications)")
        }
        for stmt in _MIGRATIONS:
            col = stmt.split("ADD COLUMN ")[1].split(" ")[0]
            if col not in existing:
                self.conn.execute(stmt)

    # ----------------------------------------------------------- CRUD

    def add_application(
        self,
        record: ApplicationRecord,
        max_per_day: int = 20,
    ) -> tuple[Optional[int], str]:
        """Insert with guardrails. Returns (id, message); id is None on block."""
        existing = self.conn.execute(
            "SELECT id FROM applications WHERE job_id = ?", (record.job_id,)
        ).fetchone()
        if existing:
            return None, f"Duplicate: job {record.job_id} already tracked (id={existing['id']})"

        today = datetime.utcnow().strftime("%Y-%m-%d")
        count_today = self.conn.execute(
            "SELECT COUNT(*) c FROM applications WHERE applied_at LIKE ?",
            (f"{today}%",),
        ).fetchone()["c"]
        if count_today >= max_per_day:
            return None, (
                f"Daily limit reached ({count_today}/{max_per_day}). "
                "Increase limits.max_applications_per_day to override."
            )

        cursor = self.conn.execute(
            """
            INSERT INTO applications (
                job_id, title, company, board, url, applied_at, status,
                fit_score, ats_score_before, ats_score_after,
                resume_variant_hash, coverletter_hash,
                tailored_resume_path, coverletter_path, notes, variant
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id, record.title, record.company, record.board,
                record.url, record.applied_at or datetime.utcnow(),
                record.status, record.fit_score,
                record.ats_score_before, record.ats_score_after,
                record.resume_variant_hash, record.coverletter_hash,
                record.tailored_resume_path, record.coverletter_path,
                record.notes, record.variant,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid, f"Tracked job {record.job_id} (id={cursor.lastrowid})"

    def update_status(self, row_id: int, status: str, notes: str = "") -> bool:
        valid = {
            "draft", "pending_review", "approved", "rejected_by_user",
            "submitted", "no_response", "rejected", "phone_screen",
            "interview", "offer", "declined",
        }
        if status not in valid:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(valid)}")
        cursor = self.conn.execute(
            "UPDATE applications SET status = ?, "
            "notes = CASE WHEN ? != '' THEN ? ELSE notes END WHERE id = ?",
            (status, notes, notes, row_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get(self, row_id: int) -> Optional[ApplicationRecord]:
        row = self.conn.execute(
            "SELECT * FROM applications WHERE id = ?", (row_id,)
        ).fetchone()
        return _row_to_record(row) if row else None

    def list_applications(
        self, status: Optional[str] = None, days: Optional[int] = None
    ) -> list[ApplicationRecord]:
        query = "SELECT * FROM applications"
        conditions, params = [], []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            conditions.append("applied_at >= ?")
            params.append(cutoff)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY applied_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [_row_to_record(r) for r in rows]

    def has_job(self, job_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    # ------------------------------------------------------- A/B variants

    def set_variant(self, row_id: int, variant: str) -> bool:
        if variant not in ("A", "B"):
            raise ValueError("variant must be 'A' or 'B'")
        cursor = self.conn.execute(
            "UPDATE applications SET variant = ? WHERE id = ?", (variant, row_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def variant_stats(self) -> dict:
        """Outcome counts per resume variant for A/B analysis."""
        rows = self.conn.execute(
            """
            SELECT variant, status, COUNT(*) c FROM applications
            WHERE variant IN ('A','B') AND status IN (
                'submitted','no_response','rejected','phone_screen',
                'interview','offer','declined')
            GROUP BY variant, status
            """
        ).fetchall()
        stats: dict[str, dict[str, int]] = {"A": {}, "B": {}}
        for row in rows:
            stats.setdefault(row["variant"], {})[row["status"]] = row["c"]
        return stats

    def variant_ats_deltas(self) -> dict[str, list[float]]:
        """ATS tailoring deltas per variant (proxy signal before outcomes)."""
        rows = self.conn.execute(
            """
            SELECT variant, ats_score_before, ats_score_after FROM applications
            WHERE variant IN ('A','B')
              AND ats_score_before IS NOT NULL
              AND ats_score_after IS NOT NULL
            """
        ).fetchall()
        deltas: dict[str, list[float]] = {"A": [], "B": []}
        for row in rows:
            deltas.setdefault(row["variant"], []).append(
                row["ats_score_after"] - row["ats_score_before"]
            )
        return deltas

    # ------------------------------------------------------- learning

    def save_pattern(
        self, pattern_type: str, pattern_value: str,
        correlation: float, sample_size: int,
    ) -> None:
        self.conn.execute(
            "INSERT INTO learning_patterns "
            "(pattern_type, pattern_value, correlation_score, sample_size, discovered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (pattern_type, pattern_value, correlation, sample_size, datetime.utcnow()),
        )
        self.conn.commit()

    def save_style_guide(
        self, version: int, style_guide: str, source: str, notes: str = ""
    ) -> None:
        self.conn.execute("UPDATE style_guide_versions SET active = 0 WHERE active = 1")
        self.conn.execute(
            "INSERT INTO style_guide_versions (version, applied_at, source, style_guide, active, notes) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (version, datetime.utcnow(), source, style_guide, notes),
        )
        self.conn.commit()

    def active_style_guide(self) -> tuple[Optional[int], str]:
        row = self.conn.execute(
            "SELECT version, style_guide FROM style_guide_versions "
            "WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return (row["version"], row["style_guide"]) if row else (None, "")

    def style_guide_history(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM style_guide_versions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------- stats

    def stats(self, days: int = 30) -> dict:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows = self.conn.execute(
            "SELECT status, COUNT(*) c FROM applications "
            "WHERE applied_at >= ? GROUP BY status",
            (cutoff,),
        ).fetchall()
        by_status = {r["status"]: r["c"] for r in rows}
        total = sum(by_status.values())
        responses = sum(
            by_status.get(s, 0)
            for s in ("rejected", "phone_screen", "interview", "offer", "declined")
        )
        interviews = sum(
            by_status.get(s, 0) for s in ("phone_screen", "interview", "offer")
        )
        return {
            "days": days,
            "total": total,
            "by_status": by_status,
            "responses": responses,
            "response_rate": round(responses / total, 3) if total else 0.0,
            "interviews": interviews,
            "interview_rate": round(interviews / total, 3) if total else 0.0,
        }

    def close(self) -> None:
        self.conn.close()


def _row_to_record(row: sqlite3.Row) -> ApplicationRecord:
    return ApplicationRecord(
        id=row["id"],
        job_id=row["job_id"],
        title=row["title"] or "",
        company=row["company"] or "",
        board=row["board"] or "",
        url=row["url"] or "",
        applied_at=_parse_dt(row["applied_at"]),
        status=row["status"] or "draft",
        fit_score=row["fit_score"] or 0.0,
        ats_score_before=row["ats_score_before"],
        ats_score_after=row["ats_score_after"],
        resume_variant_hash=row["resume_variant_hash"] or "",
        coverletter_hash=row["coverletter_hash"] or "",
        tailored_resume_path=row["tailored_resume_path"] or "",
        coverletter_path=row["coverletter_path"] or "",
        notes=row["notes"] or "",
        variant=row["variant"] or "A",
        outcome_source=row["outcome_source"] or "",
    )


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None
