"""Per-user ownership: schema migration + store-enforced isolation."""

from __future__ import annotations

import sqlite3

import pytest

from applyjin.web.master_store import MasterStore
from applyjin.web.store import WebStore

# The pre-isolation schema, exactly as production databases have it.
_OLD_SCHEMA = """
CREATE TABLE web_resumes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    content_md TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    file_path TEXT DEFAULT '',
    skills TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE web_jds (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    content TEXT NOT NULL,
    keywords_json TEXT DEFAULT '',
    ghost_score INTEGER,
    ghost_flags_json TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE web_applications (
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
CREATE TABLE waitlist (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE copilot_messages (
    id INTEGER PRIMARY KEY,
    application_id INTEGER,
    role TEXT CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE master_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    location TEXT DEFAULT '',
    linkedin TEXT DEFAULT '',
    github TEXT DEFAULT '',
    website TEXT DEFAULT '',
    headline TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    years_experience INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE master_experiences (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    organization TEXT DEFAULT '',
    location TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    description TEXT DEFAULT '',
    bullets_json TEXT DEFAULT '[]',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE master_projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    tech TEXT DEFAULT '',
    description TEXT DEFAULT '',
    bullets_json TEXT DEFAULT '[]',
    link TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE master_education (
    id INTEGER PRIMARY KEY,
    degree TEXT NOT NULL,
    institution TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    details TEXT DEFAULT ''
);
CREATE TABLE master_certifications (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    issuer TEXT DEFAULT '',
    year TEXT DEFAULT ''
);
CREATE TABLE master_skills (
    id INTEGER PRIMARY KEY,
    category TEXT DEFAULT '',
    name TEXT NOT NULL UNIQUE
);
INSERT INTO master_profile (id, full_name, email) VALUES (1, 'Legacy User', 'old@example.com');
INSERT INTO master_experiences (title, organization) VALUES ('Engineer', 'Acme');
INSERT INTO master_skills (category, name) VALUES ('lang', 'Python');
INSERT INTO web_resumes (name, content_md, raw_text) VALUES ('Legacy CV', '# md', 'raw');
"""


def _old_db(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()
    return db


# ---------------------------------------------------------------- migration


class TestOwnershipMigration:
    def test_web_tables_gain_user_id_and_keep_rows(self, tmp_path):
        db = _old_db(tmp_path)
        store = WebStore(db, user_id=1)
        resumes = store.list_resumes()
        assert [r["name"] for r in resumes] == ["Legacy CV"]
        assert store.list_jds() == []
        assert store.get_resume(1)["raw_text"] == "raw"
        store.close()

    def test_master_profile_singleton_rebuilt_for_user(self, tmp_path):
        db = _old_db(tmp_path)
        store = MasterStore(db, user_id=1)
        profile = store.get_profile()
        assert profile["full_name"] == "Legacy User"
        assert profile["user_id"] == 1
        assert store.list_experiences()[0]["title"] == "Engineer"
        assert store.all_skill_names() == ["Python"]
        store.close()

    def test_profile_row_created_for_new_user(self, tmp_path):
        db = _old_db(tmp_path)
        store = MasterStore(db, user_id=1)
        store.update_profile(full_name="First")
        store.close()
        other = MasterStore(db, user_id=2)
        assert other.get_profile()["user_id"] == 2
        assert other.get_profile()["full_name"] == ""
        assert other.get_profile().get("id") is None
        other.close()

    def test_skills_unique_per_user_not_global(self, tmp_path):
        db = _old_db(tmp_path)
        a = MasterStore(db, user_id=1)
        b = MasterStore(db, user_id=2)
        # user 1 already has Python from the legacy data
        assert b.add_skills("lang", ["Python"]) == 1
        assert a.all_skill_names() == ["Python"]
        assert b.all_skill_names() == ["Python"]
        # deleting for user 2 leaves user 1's skill intact
        assert b.delete_skill("Python") is True
        assert a.all_skill_names() == ["Python"]
        assert b.all_skill_names() == []
        a.close()
        b.close()

    def test_fresh_db_creates_new_schema_directly(self, tmp_path):
        db = tmp_path / "fresh.db"
        store = MasterStore(db, user_id=7)
        store.update_profile(full_name="Fresh")
        store.close()
        reopened = MasterStore(db, user_id=7)
        assert reopened.get_profile()["full_name"] == "Fresh"
        sql = sqlite3.connect(db).execute(
            "SELECT sql FROM sqlite_master WHERE name='master_profile'"
        ).fetchone()[0]
        assert "CHECK" not in sql
        reopened.close()


# --------------------------------------------------------------- isolation


class TestStoreIsolation:
    def test_resume_read_write_scoped(self, tmp_path):
        db = tmp_path / "iso.db"
        a = WebStore(db, user_id=1)
        b = WebStore(db, user_id=2)
        rid = a.add_resume("A CV", "# a", "raw a", ["x"])
        assert [r["id"] for r in a.list_resumes()] == [rid]
        assert b.list_resumes() == []
        assert b.get_resume(rid) is None
        assert b.delete_resume(rid) is False
        assert a.get_resume(rid) is not None
        a.close()
        b.close()

    def test_application_read_write_scoped(self, tmp_path):
        db = tmp_path / "iso.db"
        a = WebStore(db, user_id=1)
        b = WebStore(db, user_id=2)
        rid = a.add_resume("CV", "# md", "raw", [])
        jid = a.add_jd("Engineer", "Acme", "content")
        app_id = a.create_application(rid, jid)
        assert b.list_applications() == []
        assert b.get_application(app_id) is None
        b.update_application(app_id, status="applied")
        assert a.get_application(app_id)["status"] == "analyzed"
        b.update_pipeline_status(app_id, "applied")  # not owned -> no-op
        assert a.get_application(app_id)["pipeline_status"] == "saved"
        with pytest.raises(ValueError):
            b.create_application(rid, jid)  # foreign references rejected
        a.close()
        b.close()

    def test_copilot_history_scoped(self, tmp_path):
        db = tmp_path / "iso.db"
        a = WebStore(db, user_id=1)
        b = WebStore(db, user_id=2)
        rid = a.add_resume("CV", "# md", "raw", [])
        jid = a.add_jd("T", "C", "x")
        app_id = a.create_application(rid, jid)
        a.add_copilot_message(app_id, "user", "hello")
        assert len(a.get_copilot_history(app_id)) == 1
        assert b.get_copilot_history(app_id) == []
        a.close()
        b.close()

    def test_master_data_scoped(self, tmp_path):
        db = tmp_path / "iso.db"
        a = MasterStore(db, user_id=1)
        b = MasterStore(db, user_id=2)
        a.update_profile(full_name="Alice")
        exp = a.add_experience("Dev", "Acme")
        assert b.get_profile()["full_name"] == ""
        assert b.list_experiences() == []
        assert b.delete_experience(exp) is False
        assert a.list_experiences()[0]["title"] == "Dev"
        a.close()
        b.close()

    def test_snapshot_scoped_to_one_user(self, tmp_path):
        db = tmp_path / "iso.db"
        a = MasterStore(db, user_id=1)
        b = MasterStore(db, user_id=2)
        a.add_experience("Dev", "Acme")
        assert len(a.snapshot()["experiences"]) == 1
        assert b.snapshot()["experiences"] == []
        a.close()
        b.close()

    def test_waitlist_stays_global(self, tmp_path):
        db = tmp_path / "iso.db"
        a = WebStore(db, user_id=1)
        b = WebStore(db, user_id=2)
        a.add_waitlist("x@example.com")
        assert b.waitlist_count() == 1
        a.close()
        b.close()


class TestConstructorIsFailClosed:
    def test_user_id_required(self, tmp_path):
        with pytest.raises(TypeError):
            WebStore(tmp_path / "x.db")
        with pytest.raises(TypeError):
            MasterStore(tmp_path / "x.db")

    def test_user_id_must_be_positive_int(self, tmp_path):
        with pytest.raises(ValueError):
            WebStore(tmp_path / "x.db", user_id=0)
        with pytest.raises(ValueError):
            MasterStore(tmp_path / "x.db", user_id=-1)


# ----------------------------------------------------------------- principal


class TestAPIPrincipal:
    def _request(self):
        from starlette.requests import Request

        return Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    def test_local_mode_maps_to_local_user(self, monkeypatch):
        from applyjin.web.app import _current_user_id
        from applyjin.web.tenancy import LOCAL_USER_ID

        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        assert _current_user_id(self._request()) == LOCAL_USER_ID

    def test_auth_mode_requires_session_user(self, monkeypatch):
        import pytest
        from fastapi import HTTPException

        from applyjin.web.app import _current_user_id

        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        with pytest.raises(HTTPException) as exc:
            _current_user_id(self._request())
        assert exc.value.status_code == 401
        req = self._request()
        req.state.user = {"id": 42, "email": "a@b.c"}
        assert _current_user_id(req) == 42
