"""Google OAuth 2.0 sign-in + JWT sessions for the ApplyJin Console.

Flow (frontend on Vercel, backend on Render — different origins):

  1. Frontend "Sign in with Google" -> {API_BASE}/api/auth/google
  2. Backend 302 -> Google consent screen
  3. Google 302  -> backend /api/auth/google/callback?code=...
  4. Backend exchanges the code, upserts the user, mints a JWT
  5. Backend 302 -> {FRONTEND_URL}/auth/callback#token=JWT
  6. Frontend stores the token (localStorage), navigates to /dashboard

The token travels in the URL *fragment* (#) so it never hits server
logs or referrers. Works in every browser — Firefox, Chrome, Safari.

Auth is ENFORCED only when GOOGLE_CLIENT_ID is configured: zero-config
local runs stay open, and the deployed instance is locked.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import httpx
import jwt as pyjwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from hermes.web.store import WebStore

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

TOKEN_TTL_SECONDS = 7 * 24 * 3600  # one week

_USERS_SCHEMA = """
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


def auth_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID"))


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "")


def client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "")


def frontend_url() -> str:
    """Where to send the user after login (the Vercel frontend)."""
    return (
        os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    )


# ---------------------------------------------------------------- secret

_SECRET: Optional[str] = None


def _secret() -> str:
    """JWT signing secret: AUTH_SECRET env, or a generated file-based one.

    The file fallback keeps sessions alive across local restarts. On
    ephemeral hosts (Render free) set AUTH_SECRET to keep sessions
    across deploys.
    """
    global _SECRET
    if _SECRET:
        return _SECRET
    env_secret = os.environ.get("AUTH_SECRET")
    if env_secret:
        _SECRET = env_secret
        return _SECRET
    secret_path = Path("data/auth_secret")
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        if secret_path.exists():
            _SECRET = secret_path.read_text(encoding="utf-8").strip()
        else:
            _SECRET = secrets.token_urlsafe(48)
            secret_path.write_text(_SECRET, encoding="utf-8")
    except OSError:
        # Read-only FS — generate per-process (sessions reset on restart)
        _SECRET = secrets.token_urlsafe(48)
    return _SECRET


# ---------------------------------------------------------------- JWT


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return pyjwt.encode(payload, _secret(), algorithm="HS256")


def verify_token(token: str) -> dict:
    """Decode + validate. Raises ValueError on any problem."""
    try:
        return pyjwt.decode(token, _secret(), algorithms=["HS256"])
    except pyjwt.PyJWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc


# ---------------------------------------------------------------- state (CSRF)


def _sign_state(data: str) -> str:
    sig = hmac.new(_secret().encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{data}.{sig}"


def make_state() -> str:
    return _sign_state(f"{int(time.time())}:{secrets.token_urlsafe(8)}")


def check_state(state: str, max_age_seconds: int = 600) -> bool:
    try:
        data, sig = state.rsplit(".", 1)
        if not hmac.compare_digest(_sign_state(data), state):
            return False
        ts = int(data.split(":")[0])
        return abs(time.time() - ts) < max_age_seconds
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- users


def _ensure_users_table(db_path) -> None:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_USERS_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_user(db_path, google_sub: str, email: str, name: str, picture: str) -> int:
    """Create the user on first sign-in; refresh profile + last_login after."""
    _ensure_users_table(db_path)
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE google_sub = ?", (google_sub,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET email = ?, name = ?, picture = ?, last_login = ? "
                "WHERE id = ?",
                (email, name, picture, datetime.utcnow(), existing["id"]),
            )
            conn.commit()
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO users (google_sub, email, name, picture, last_login) "
            "VALUES (?, ?, ?, ?, ?)",
            (google_sub, email, name, picture, datetime.utcnow()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user(db_path, user_id: int) -> Optional[dict]:
    _ensure_users_table(db_path)
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, email, name, picture FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------- endpoints


def google_login_url(callback_base: str, state: str) -> str:
    """The Google consent-screen URL for this app."""
    from urllib.parse import urlencode

    params = {
        "client_id": client_id(),
        "redirect_uri": f"{callback_base}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, callback_base: str) -> dict:
    """Exchange the auth code for tokens, then fetch the Google profile."""
    async with httpx.AsyncClient(timeout=30) as http:
        token_resp = await http.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id(),
                "client_secret": client_secret(),
                "redirect_uri": f"{callback_base}/api/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                502, f"Google token exchange failed: {token_resp.text[:200]}"
            )
        access_token = token_resp.json().get("access_token")

        user_resp = await http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(502, "Could not fetch the Google profile")
        profile = user_resp.json()

    return {
        "sub": profile["id"],
        "email": profile.get("email", ""),
        "name": profile.get("name", ""),
        "picture": profile.get("picture", ""),
        # Google returns `email_verified` as JSON bool
        "email_verified": profile.get("verified_email", False),
    }


# ---------------------------------------------------------------- middleware


PUBLIC_API_PREFIXES = ("/api/public/", "/api/auth/")


async def auth_middleware_dispatch(request: Request, call_next, db_path):
    """Gate every /api/* route except public + auth + CORS preflight.

    Disabled entirely when GOOGLE_CLIENT_ID is unset (local dev mode).
    """
    if not auth_enabled():
        return await call_next(request)

    path = request.url.path
    if (
        not path.startswith("/api/")
        or path.startswith(PUBLIC_API_PREFIXES)
        or request.method == "OPTIONS"
    ):
        return await call_next(request)

    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return JSONResponse({"detail": "Sign in required"}, status_code=401)
    try:
        payload = verify_token(header[7:])
        user = get_user(db_path, int(payload["sub"]))
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)
    if not user:
        return JSONResponse({"detail": "Account not found"}, status_code=401)
    request.state.user = user
    return await call_next(request)
