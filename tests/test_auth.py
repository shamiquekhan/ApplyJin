"""Auth: JWT sessions, Google OAuth config, and the API gate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def auth_env(monkeypatch, tmp_path):
    """Auth ENABLED with a fixed secret + fake Google credentials."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_SECRET", "unit-test-secret")
    monkeypatch.setattr("hermes.web.auth._SECRET", None)
    return tmp_path


@pytest.fixture
def open_env(monkeypatch):
    """Auth DISABLED (local zero-config mode)."""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.setattr("hermes.web.auth._SECRET", None)


class TestJWT:
    def test_roundtrip(self, auth_env):
        from hermes.web.auth import create_token, verify_token

        token = create_token(42, "user@example.com")
        payload = verify_token(token)
        assert payload["sub"] == "42"
        assert payload["email"] == "user@example.com"

    def test_tampered_token_rejected(self, auth_env):
        from hermes.web.auth import create_token, verify_token

        token = create_token(1, "a@b.c")
        with pytest.raises(ValueError):
            verify_token(token[:-2] + "xx")  # corrupted signature

    def test_expired_token_rejected(self, auth_env):
        from hermes.web.auth import verify_token

        import jwt as pyjwt
        import time as _time

        expired = pyjwt.encode(
            {
                "sub": "1",
                "email": "a@b.c",
                "iat": int(_time.time()) - 800000,
                "exp": int(_time.time()) - 10,  # expired 10s ago
            },
            "unit-test-secret",
            algorithm="HS256",
        )
        with pytest.raises(ValueError):
            verify_token(expired)

    def test_wrong_secret_rejected(self, auth_env, monkeypatch):
        from hermes.web import auth

        token = auth.create_token(1, "a@b.c")
        monkeypatch.setattr(auth, "_SECRET", "different-secret")
        with pytest.raises(ValueError):
            auth.verify_token(token)


class TestStateCSRF:
    def test_state_validates(self, auth_env):
        from hermes.web.auth import check_state, make_state

        state = make_state()
        assert check_state(state)

    def test_forged_state_rejected(self, auth_env):
        from hermes.web.auth import check_state

        assert not check_state("12345.deadbeef")
        assert not check_state("")

    def test_expired_state_rejected(self, auth_env, monkeypatch):
        import time as _time

        from hermes.web.auth import check_state, make_state

        state = make_state()
        real_time = _time.time
        monkeypatch.setattr(_time, "time", lambda: real_time() + 3600)
        assert not check_state(state)


class TestUsers:
    def test_upsert_and_get(self, auth_env, tmp_path):
        from hermes.web.auth import get_user, upsert_user

        db = tmp_path / "users.db"
        uid = upsert_user(db, "g-sub-1", "new@example.com", "New User", "http://pic")
        assert uid == 1
        user = get_user(db, uid)
        assert user["email"] == "new@example.com"
        assert user["name"] == "New User"

        # second login with same google id -> same user, updated name
        uid2 = upsert_user(db, "g-sub-1", "new@example.com", "Renamed", "http://pic")
        assert uid2 == uid
        assert get_user(db, uid)["name"] == "Renamed"

        # different google id -> new user
        uid3 = upsert_user(db, "g-sub-2", "second@example.com", "Two", "")
        assert uid3 == 2

    def test_get_missing_user(self, auth_env, tmp_path):
        from hermes.web.auth import get_user

        assert get_user(tmp_path / "u.db", 999) is None


class TestAuthGate:
    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        fastapi_test = pytest.importorskip("fastapi.testclient")
        from hermes.web import app as web_module

        monkeypatch.setattr(web_module, "DB_PATH", tmp_path / "web.db")
        monkeypatch.setattr(web_module, "UPLOAD_DIR", tmp_path / "uploads")
        monkeypatch.setattr(web_module, "PDF_DIR", tmp_path / "pdfs")
        monkeypatch.setattr(web_module, "_router", lambda: None)
        return fastapi_test.TestClient(web_module.app)

    def test_gate_blocks_when_configured(self, client, monkeypatch):
        """Every private /api route 401s without a token when auth is on."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        assert client.get("/api/resumes").status_code == 401
        assert client.get("/api/master/stats").status_code == 401
        assert client.get("/api/applications").status_code == 401

        # public + auth routes stay open
        assert client.get("/api/public/stats").status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        # static pages stay open
        assert client.get("/dashboard").status_code == 200

    def test_gate_open_when_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        assert client.get("/api/resumes").status_code == 200
        assert client.get("/api/public/stats").status_code == 200

    def test_valid_token_passes_gate(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        from hermes.web import auth as auth_mod
        from hermes.web import app as web_module

        uid = auth_mod.upsert_user(
            web_module.DB_PATH, "sub-9", "me@example.com", "Me", ""
        )
        token = auth_mod.create_token(uid, "me@example.com")
        resp = client.get("/api/resumes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        # /me returns the session user
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["user"]["email"] == "me@example.com"

    def test_unknown_user_token_401s(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        from hermes.web import auth as auth_mod

        token = auth_mod.create_token(12345, "ghost@example.com")  # no such user row
        resp = client.get("/api/resumes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_google_login_redirects(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "my-app.apps.googleusercontent.com")
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        resp = client.get("/api/auth/google", follow_redirects=False)
        assert resp.status_code in (301, 302, 307, 308)
        location = resp.headers["location"]
        assert "accounts.google.com" in location
        assert "my-app.apps.googleusercontent.com" in location
        assert "state=" in location  # CSRF protection present

    def test_callback_bad_state_redirects_error(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setenv("FRONTEND_URL", "https://fe.example.com")
        monkeypatch.setattr("hermes.web.auth._SECRET", None)
        resp = client.get(
            "/api/auth/google/callback?code=x&state=forged.1234",
            follow_redirects=False,
        )
        assert resp.status_code in (301, 302, 307, 308)
        assert "/auth/callback#error=" in resp.headers["location"]
