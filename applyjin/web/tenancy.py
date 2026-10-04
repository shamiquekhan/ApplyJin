"""Per-user data isolation: the local principal + shared users schema.

Every tenant row (resumes, JDs, applications, copilot messages, the whole
master CV) carries a ``user_id`` and is queried through a store bound to a
single user. There is no unscoped access path by construction: both stores
require ``user_id`` at construction time.

``LOCAL_USER_ID`` is the principal for zero-config local runs (auth
disabled). The ownership migration attributes pre-isolation data to user 1;
if user 1 is already claimed by a signed-in account, that account keeps the
data — see SECURITY.md.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

LOCAL_USER_ID = 1
LOCAL_USER_EMAIL = "local@applyjin.dev"

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    google_sub TEXT UNIQUE,
    email TEXT NOT NULL,
    name TEXT DEFAULT '',
    picture TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
"""


def ensure_local_user(db_path: Path | str) -> None:
    """Guarantee the default/local user row exists before any backfill."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(USERS_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO users (id, google_sub, email, name) "
            "VALUES (?, NULL, ?, 'Local User')",
            (LOCAL_USER_ID, LOCAL_USER_EMAIL),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_users_table(db_path: Path | str) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(USERS_SCHEMA)
        conn.commit()
    finally:
        conn.close()
