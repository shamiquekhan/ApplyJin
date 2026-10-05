"""Adversarial security suite: IDOR, cross-tenant isolation, token forgery.

Two signed-in tenants (A and B) over HTTP: B attacks every family of A's
resources by id. Anything B can see, change, or delete of A's is a fail —
cross-tenant reads must 404 (existence is not leaked) and lists must be
empty.
"""

from __future__ import annotations

import pytest

_JD_CONTENT = (
    "We are hiring a software engineer. Requirements: Python, SQL, "
    "testing culture, REST APIs, collaboration with product teams. "
    "Nice to have: Docker and CI experience."
)
_RESUME_CONTENT = (
    "# Jane Doe\njane@example.com\n\n## Experience\n### Engineer | Acme\n"
    "- Built REST APIs in Python used by 10k users\n"
    "- Led migration to Docker CI pipelines\n"
)


@pytest.fixture
def sec(monkeypatch, tmp_path):
    """Auth ENABLED client + user factory + tenant A's seeded resource ids."""
    fastapi_test = pytest.importorskip("fastapi.testclient")
    from applyjin.web import app as web_module
    from applyjin.web import auth as auth_mod

    monkeypatch.setattr(web_module, "DB_PATH", tmp_path / "web.db")
    monkeypatch.setattr(web_module, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(web_module, "PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(web_module, "_router", lambda: None)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "sec-test-client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec-test-secret")
    monkeypatch.setenv("AUTH_SECRET", "sec-test-secret-key")
    monkeypatch.setattr("applyjin.web.auth._SECRET", None)
    monkeypatch.setenv("FRONTEND_URL", "https://fe.example.com")

    client = fastapi_test.TestClient(web_module.app)

    def make_user(tag: str):
        uid = auth_mod.upsert_user(
            web_module.DB_PATH, f"sub-{tag}", f"{tag}@example.com", tag.title(), ""
        )
        token = auth_mod.create_token(uid, f"{tag}@example.com")
        return {"Authorization": f"Bearer {token}"}

    return type("Sec", (), {"client": client, "auth": auth_mod, "make_user": make_user})


@pytest.fixture
def tenant_a(sec):
    """User A's resources, created through the API as A."""
    h = sec.make_user("alice")
    client = sec.client
    resume = client.post(
        "/api/resumes/create",
        data={"name": "Alice CV", "content": _RESUME_CONTENT},
        headers=h,
    ).json()
    jd = client.post(
        "/api/job-descriptions",
        data={"title": "Backend Engineer", "company": "Initech", "content": _JD_CONTENT},
        headers=h,
    ).json()
    application = client.post(
        "/api/applications",
        data={"resume_id": resume["id"], "jd_id": jd["id"]},
        headers=h,
    ).json()
    exp = client.put(
        "/api/master/profile",
        json={"full_name": "Alice Doe", "email": "alice@example.com"},
        headers=h,
    )
    assert exp.status_code == 200
    experiences = client.post(
        "/api/master/experiences",
        json={"title": "Lead Engineer", "organization": "Acme", "bullets": ["shipped x"]},
        headers=h,
    ).json()
    return {
        "headers": h,
        "resume_id": resume["id"],
        "jd_id": jd["id"],
        "app_id": application["id"],
        "exp_id": experiences["id"],
    }


class TestUnauthMatrix:
    """Without a session token every private route 401s; public stays open."""

    PRIVATE_ROUTES = [
        ("GET", "/api/resumes"),
        ("GET", "/api/resumes/1"),
        ("POST", "/api/resumes/create"),
        ("DELETE", "/api/resumes/1"),
        ("GET", "/api/job-descriptions"),
        ("GET", "/api/job-descriptions/1"),
        ("POST", "/api/job-descriptions"),
        ("POST", "/api/job-descriptions/1/extract-keywords"),
        ("GET", "/api/applications"),
        ("GET", "/api/applications/1"),
        ("POST", "/api/applications"),
        ("POST", "/api/applications/1/tailor"),
        ("GET", "/api/applications/1/download-resume"),
        ("GET", "/api/applications/1/resume-qa"),
        ("GET", "/api/applications/1/download-resume-latex"),
        ("GET", "/api/applications/1/download-cover-letter"),
        ("POST", "/api/applications/1/cover-letter"),
        ("POST", "/api/applications/1/email-template"),
        ("GET", "/api/pipeline"),
        ("POST", "/api/pipeline/1/status"),
        ("GET", "/api/copilot/history/1"),
        ("POST", "/api/copilot/chat"),
        ("GET", "/api/master/profile"),
        ("PUT", "/api/master/profile"),
        ("GET", "/api/master/stats"),
        ("GET", "/api/master/experiences"),
        ("POST", "/api/master/experiences"),
        ("DELETE", "/api/master/experiences/1"),
        ("GET", "/api/master/projects"),
        ("GET", "/api/master/skills"),
        ("POST", "/api/master/import-resume"),
        ("GET", "/api/settings/llm"),
        ("GET", "/api/decisions"),
        ("GET", "/api/score"),
        ("POST", "/api/linkedin/generate"),
    ]

    @pytest.mark.parametrize("method,path", PRIVATE_ROUTES)
    def test_401_without_token(self, sec, method, path):
        resp = sec.client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"

    def test_public_routes_stay_open(self, sec):
        assert sec.client.get("/api/public/stats").status_code == 200
        assert sec.client.get("/api/auth/me").status_code == 200
        assert sec.client.get("/health").status_code == 200


class TestCrossTenantIDOR:
    def test_lists_do_not_leak(self, sec, tenant_a):
        h_b = sec.make_user("bob")
        client = sec.client
        assert client.get("/api/resumes", headers=h_b).json() == []
        assert client.get("/api/job-descriptions", headers=h_b).json() == []
        assert client.get("/api/applications", headers=h_b).json() == []
        assert client.get("/api/master/experiences", headers=h_b).json() == []
        assert client.get("/api/master/projects", headers=h_b).json() == []
        pipeline = client.get("/api/pipeline", headers=h_b).json()
        assert all(group == [] for group in pipeline.values())
        profile = client.get("/api/master/profile", headers=h_b).json()
        assert profile.get("full_name", "") == ""

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("GET", "/api/resumes/{rid}", {}),
            ("GET", "/api/job-descriptions/{jid}", {}),
            ("GET", "/api/applications/{aid}", {}),
            ("GET", "/api/applications/{aid}/download-resume", {}),
            ("GET", "/api/applications/{aid}/resume-qa", {}),
            ("GET", "/api/applications/{aid}/download-resume-latex", {}),
            ("GET", "/api/applications/{aid}/download-cover-letter", {}),
            ("POST", "/api/applications/{aid}/tailor", {"data": {"selected_keywords": "[]"}}),
            ("POST", "/api/applications/{aid}/cover-letter", {"data": {}}),
            ("POST", "/api/applications/{aid}/email-template", {"data": {}}),
            ("POST", "/api/job-descriptions/{jid}/extract-keywords", {}),
            ("GET", "/api/job-descriptions/{jid}/contacts", {}),
            ("DELETE", "/api/resumes/{rid}", {}),
            ("GET", "/api/copilot/history/{aid}", {}),
            ("POST", "/api/pipeline/{aid}/status", {"json": {"status": "applied"}}),
        ],
    )
    def test_foreign_object_404_or_empty(self, sec, tenant_a, method, path, body):
        h_b = sec.make_user("bob")
        target = path.format(
            rid=tenant_a["resume_id"], jid=tenant_a["jd_id"], aid=tenant_a["app_id"]
        )
        resp = sec.client.request(method, target, headers=h_b, **body)
        if method == "GET" and "copilot" in path:
            assert resp.json() == []  # history scoped: nothing to leak
        else:
            assert resp.status_code == 404, f"{method} {target} -> {resp.status_code}"

    def test_foreign_delete_leaves_owner_intact(self, sec, tenant_a):
        h_b = sec.make_user("bob")
        client = sec.client
        assert (
            client.delete(f"/api/resumes/{tenant_a['resume_id']}", headers=h_b)
            .status_code == 404
        )
        owned = client.get(
            f"/api/resumes/{tenant_a['resume_id']}", headers=tenant_a["headers"]
        )
        assert owned.status_code == 200
        assert owned.json()["name"] == "Alice CV"

    def test_foreign_delete_master_entry_404(self, sec, tenant_a):
        h_b = sec.make_user("bob")
        resp = sec.client.delete(
            f"/api/master/experiences/{tenant_a['exp_id']}", headers=h_b
        )
        assert resp.status_code == 404
        owned = sec.client.get("/api/master/experiences", headers=tenant_a["headers"])
        assert [e["id"] for e in owned.json()] == [tenant_a["exp_id"]]

    def test_foreign_application_references_rejected(self, sec, tenant_a):
        h_b = sec.make_user("bob")
        resp = sec.client.post(
            "/api/applications",
            data={"resume_id": tenant_a["resume_id"], "jd_id": tenant_a["jd_id"]},
            headers=h_b,
        )
        assert resp.status_code == 404

    def test_master_profile_update_is_per_user(self, sec, tenant_a):
        h_b = sec.make_user("bob")
        client = sec.client
        client.put(
            "/api/master/profile", json={"full_name": "Bob Roe"}, headers=h_b
        )
        a_profile = client.get("/api/master/profile", headers=tenant_a["headers"])
        b_profile = client.get("/api/master/profile", headers=h_b)
        assert a_profile.json()["full_name"] == "Alice Doe"
        assert b_profile.json()["full_name"] == "Bob Roe"

    def test_owner_still_sees_everything(self, sec, tenant_a):
        client = sec.client
        h = tenant_a["headers"]
        assert client.get("/api/resumes", headers=h).json()[0]["name"] == "Alice CV"
        assert client.get(f"/api/resumes/{tenant_a['resume_id']}", headers=h).status_code == 200
        assert client.get(f"/api/applications/{tenant_a['app_id']}", headers=h).status_code == 200


class TestTokenForgery:
    def test_garbage_token_401(self, sec):
        resp = sec.client.get(
            "/api/resumes", headers={"Authorization": "Bearer not.a.token"}
        )
        assert resp.status_code == 401

    def test_wrong_secret_token_401(self, sec):
        import time

        import jwt as pyjwt

        forged = pyjwt.encode(
            {
                "sub": "1",
                "email": "a@b.c",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            },
            "attacker-secret",
            algorithm="HS256",
        )
        resp = sec.client.get("/api/resumes", headers={"Authorization": f"Bearer {forged}"})
        assert resp.status_code == 401

    def test_expired_token_401(self, sec):
        import time

        import jwt as pyjwt

        expired = pyjwt.encode(
            {
                "sub": "1",
                "email": "a@b.c",
                "iat": int(time.time()) - 800000,
                "exp": int(time.time()) - 10,
            },
            "sec-test-secret-key",
            algorithm="HS256",
        )
        resp = sec.client.get("/api/resumes", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401

    def test_nonexistent_user_token_401(self, sec):
        token = sec.auth.create_token(999999, "ghost@example.com")
        resp = sec.client.get(
            "/api/resumes", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401


class TestUploadIsolation:
    """Uploaded artifacts live under per-user directories; no traversal."""

    def _upload(self, client, headers, filename="cv.txt", content=None):
        text = content or (
            "# Jane Doe\njane@example.com\n\n## Experience\n"
            "### Engineer | Acme\n- Built REST APIs in Python for 5 years\n"
        )
        return client.post(
            "/api/resumes/upload",
            files={"file": (filename, text.encode(), "text/plain")},
            headers=headers,
        )

    def test_uploads_are_separated_per_user(self, sec, tmp_path):
        h_a = sec.make_user("cara")
        h_b = sec.make_user("dave")
        assert self._upload(sec.client, h_a).status_code == 200
        assert self._upload(sec.client, h_b).status_code == 200
        user_dirs = {
            p.name for p in tmp_path.joinpath("uploads").iterdir() if p.is_dir()
        }
        # Two distinct per-user directories, both named by principal id.
        assert len(user_dirs) == 2
        assert user_dirs == {"1", "2"}

    def test_traversal_filename_lands_flat_in_user_dir(self, sec, tmp_path):
        h = sec.make_user("erin")
        resp = self._upload(sec.client, h, filename="../../escape.txt")
        assert resp.status_code == 200
        uploads_root = tmp_path / "uploads"
        # Nothing escaped the uploads root: every stored file sits inside a
        # per-user directory, never at the root itself.
        for p in uploads_root.rglob("*"):
            assert p.is_dir() or uploads_root.joinpath(p.relative_to(uploads_root).parts[0], *p.relative_to(uploads_root).parts[1:-1]).is_dir()
        stored = list((uploads_root / "1").glob("*.txt"))
        assert len(stored) == 1
        assert "/" not in stored[0].name and "\\" not in stored[0].name

    def test_stored_path_records_user_scope(self, sec, tmp_path):
        from applyjin.web.store import WebStore

        h = sec.make_user("frank")
        resume_id = self._upload(sec.client, h).json()["id"]
        store = WebStore(tmp_path / "web.db", user_id=1)
        try:
            row = store.conn.execute(
                "SELECT file_path FROM web_resumes WHERE id = ?", (resume_id,)
            ).fetchone()
            assert str(tmp_path / "uploads" / "1") in row["file_path"]
        finally:
            store.close()
