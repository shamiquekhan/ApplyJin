"""Web dashboard store: resumes, JDs, tailor applications.

Separate tables from the CLI tracker (applications) — the web UI is a
hands-on tailoring workbench, the tracker is the automated pipeline log.
Both live in the same SQLite file for one-source-of-truth backups.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS web_resumes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    content_md TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    file_path TEXT DEFAULT '',
    skills TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS web_jds (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords_json TEXT DEFAULT '',
    ghost_score INTEGER,
    ghost_flags_json TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS web_applications (
    id INTEGER PRIMARY KEY,
    resume_id INTEGER NOT NULL REFERENCES web_resumes(id),
    jd_id INTEGER NOT NULL REFERENCES web_jds(id),
    selected_keywords TEXT DEFAULT '[]',
    score_keywords TEXT DEFAULT '[]',
    tailored_resume_md TEXT DEFAULT '',
    cover_letter_md TEXT DEFAULT '',
    kw_before REAL, kw_after REAL,
    sem_before REAL, sem_after REAL,
    ats_before REAL, ats_after REAL,
    fit_breakdown_json TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    email_md TEXT DEFAULT '',
    hiring_manager TEXT DEFAULT '',
    emails_json TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS copilot_messages (
    id INTEGER PRIMARY KEY,
    application_id INTEGER,
    role TEXT CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Column additions for stores created before the master-DB era.
_MIGRATIONS = [
    "ALTER TABLE web_applications ADD COLUMN score_keywords TEXT DEFAULT '[]'",
    "ALTER TABLE web_applications ADD COLUMN email_md TEXT DEFAULT ''",
    "ALTER TABLE web_applications ADD COLUMN hiring_manager TEXT DEFAULT ''",
    "ALTER TABLE web_applications ADD COLUMN emails_json TEXT DEFAULT '[]'",
    "ALTER TABLE web_applications ADD COLUMN fit_breakdown_json TEXT DEFAULT ''",
    "ALTER TABLE web_applications ADD COLUMN pipeline_status TEXT DEFAULT 'saved'",
    "ALTER TABLE web_jds ADD COLUMN ghost_score INTEGER",
    "ALTER TABLE web_jds ADD COLUMN ghost_flags_json TEXT DEFAULT ''",
]


class WebStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        existing_apps = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(web_applications)")
        }
        existing_jds = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(web_jds)")
        }
        for stmt in _MIGRATIONS:
            col = stmt.split("ADD COLUMN ")[1].split(" ")[0]
            # Determine which table this migration targets
            if "web_jds" in stmt:
                if col not in existing_jds:
                    self.conn.execute(stmt)
            else:
                if col not in existing_apps:
                    self.conn.execute(stmt)

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------- resumes

    def add_resume(
        self, name: str, content_md: str, raw_text: str,
        skills: list[str], file_path: str = "",
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO web_resumes (name, content_md, raw_text, file_path, skills) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, content_md, raw_text, file_path, json.dumps(skills)),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_resumes(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, name, skills, created_at, substr(raw_text, 1, 180) preview "
            "FROM web_resumes ORDER BY id DESC"
        ).fetchall()
        return [
            {
                "id": r["id"], "name": r["name"],
                "skills": json.loads(r["skills"] or "[]"),
                "created_at": r["created_at"],
                "preview": (r["preview"] or "").replace("\n", " "),
            }
            for r in rows
        ]

    def get_resume(self, resume_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM web_resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "name": row["name"],
            "content_md": row["content_md"], "raw_text": row["raw_text"],
            "skills": json.loads(row["skills"] or "[]"),
            "created_at": row["created_at"],
        }

    def delete_resume(self, resume_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM web_resumes WHERE id = ?", (resume_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---------------------------------------------------------- JDs

    def add_jd(self, title: str, company: str, content: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO web_jds (title, company, content) VALUES (?, ?, ?)",
            (title, company, content),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_jds(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, title, company, created_at, ghost_score, "
            "substr(content, 1, 200) preview "
            "FROM web_jds ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_jd(self, jd_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM web_jds WHERE id = ?", (jd_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "title": row["title"], "company": row["company"],
            "content": row["content"],
            "keywords": json.loads(row["keywords_json"]) if row["keywords_json"] else None,
            "created_at": row["created_at"],
        }

    def save_jd_keywords(self, jd_id: int, keywords: dict) -> None:
        self.conn.execute(
            "UPDATE web_jds SET keywords_json = ? WHERE id = ?",
            (json.dumps(keywords), jd_id),
        )
        self.conn.commit()

    def save_jd_ghost_score(self, jd_id: int, ghost_score: int, flags: list[str]) -> None:
        self.conn.execute(
            "UPDATE web_jds SET ghost_score = ?, ghost_flags_json = ? WHERE id = ?",
            (ghost_score, json.dumps(flags), jd_id),
        )
        self.conn.commit()

    def get_jd_ghost_score(self, jd_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT ghost_score, ghost_flags_json FROM web_jds WHERE id = ?",
            (jd_id,),
        ).fetchone()
        if not row or row["ghost_score"] is None:
            return None
        return {
            "ghost_score": row["ghost_score"],
            "flags": json.loads(row["ghost_flags_json"] or "[]"),
        }

    # ---------------------------------------------------------- applications

    def create_application(self, resume_id: int, jd_id: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO web_applications (resume_id, jd_id, status, created_at) "
            "VALUES (?, ?, 'analyzed', ?)",
            (resume_id, jd_id, datetime.utcnow()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_application(self, app_id: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE web_applications SET {cols} WHERE id = ?",
            (*fields.values(), app_id),
        )
        self.conn.commit()

    def get_application(self, app_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT wa.*, r.name resume_name, j.title jd_title, j.company jd_company "
            "FROM web_applications wa "
            "JOIN web_resumes r ON r.id = wa.resume_id "
            "JOIN web_jds j ON j.id = wa.jd_id WHERE wa.id = ?",
            (app_id,),
        ).fetchone()
        if not row:
            return None
        record = dict(row)
        record["selected_keywords"] = json.loads(record.get("selected_keywords") or "[]")
        record["score_keywords"] = json.loads(record.get("score_keywords") or "[]")
        fb = record.get("fit_breakdown_json")
        record["fit_breakdown"] = json.loads(fb) if fb else None
        return record

    def list_applications(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT wa.id, wa.status, wa.ats_before, wa.ats_after, "
            "wa.kw_before, wa.kw_after, wa.fit_breakdown_json, wa.created_at, "
            "r.name resume_name, j.title jd_title, j.company jd_company "
            "FROM web_applications wa "
            "JOIN web_resumes r ON r.id = wa.resume_id "
            "JOIN web_jds j ON j.id = wa.jd_id "
            "ORDER BY wa.id DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            fb = d.pop("fit_breakdown_json", None)
            d["fit_breakdown"] = json.loads(fb) if fb else None
            result.append(d)
        return result

    # ---------------------------------------------------------- waitlist

    def add_waitlist(self, email: str, source: str = "") -> tuple[Optional[int], str]:
        """Insert with duplicate protection. Returns (id, message)."""
        existing = self.conn.execute(
            "SELECT id FROM waitlist WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return None, "You're already on the waitlist."
        cur = self.conn.execute(
            "INSERT INTO waitlist (email, source) VALUES (?, ?)", (email, source)
        )
        self.conn.commit()
        return cur.lastrowid, "You're on the list — welcome aboard."

    def waitlist_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) c FROM waitlist").fetchone()
        return row["c"]

    # ---------------------------------------------------------- copilot

    def add_copilot_message(self, application_id: int, role: str, content: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO copilot_messages (application_id, role, content) VALUES (?, ?, ?)",
            (application_id, role, content),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_copilot_history(self, application_id: int, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content, created_at FROM copilot_messages "
            "WHERE application_id = ? ORDER BY id DESC LIMIT ?",
            (application_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ---------------------------------------------------------- pipeline

    def update_pipeline_status(self, app_id: int, status: str) -> None:
        valid = ("saved", "tailored", "applied", "interviewing", "offer", "rejected", "ghosted")
        if status not in valid:
            raise ValueError(f"Invalid status: {status}")
        self.conn.execute(
            "UPDATE web_applications SET pipeline_status = ? WHERE id = ?",
            (status, app_id),
        )
        self.conn.commit()

    def list_pipeline(self) -> dict[str, list[dict]]:
        """Applications grouped by pipeline status for the Kanban board."""
        rows = self.conn.execute(
            "SELECT wa.id, wa.pipeline_status, wa.ats_after, wa.created_at, "
            "wa.fit_breakdown_json, "
            "r.name resume_name, j.title jd_title, j.company jd_company "
            "FROM web_applications wa "
            "JOIN web_resumes r ON r.id = wa.resume_id "
            "JOIN web_jds j ON j.id = wa.jd_id "
            "ORDER BY wa.id DESC"
        ).fetchall()
        groups: dict[str, list[dict]] = {
            "saved": [], "tailored": [], "applied": [],
            "interviewing": [], "offer": [], "rejected": [], "ghosted": [],
        }
        for r in rows:
            d = dict(r)
            status = d.get("pipeline_status") or "saved"
            fb = d.pop("fit_breakdown_json", None)
            d["fit_breakdown"] = json.loads(fb) if fb else None
            if status in groups:
                groups[status].append(d)
            else:
                groups["saved"].append(d)
        return groups
