"""Web dashboard: FastAPI app — interactive resume tailoring workbench.

Four-tab UI (Resumes / JDs / Tailor & Score / Applications) over the same
SQLite file as the CLI tracker. Mutations here are user-initiated (upload,
select keywords, tailor) — Hermes's guardrails (no fabrication, never
submit) apply unchanged to everything this app generates.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from hermes.config import load_dotenv, load_profile
from hermes.web.store import WebStore

app = FastAPI(title="Hermes Dashboard", version="0.6.0")

# Cross-origin policy:
#  - dev: the Vite server on :3000 (proxied — same-origin, but allow anyway)
#  - prod: the Vercel frontend (any *.vercel.app preview + custom domains
#    via env). Render backend + Vercel frontend = cross-origin by design.
import os as _os

_VERCEL_PREVIEW = r"https?://.*\.vercel\.app"
_EXTRA_ORIGINS = [
    o.strip()
    for o in _os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_VERCEL_PREVIEW,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *_EXTRA_ORIGINS,
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path("data/hermes.db")
UPLOAD_DIR = Path("data/uploads")
PDF_DIR = Path("data/pdfs")
STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

_allowed_ext = {".pdf", ".docx", ".doc", ".md", ".txt"}


def _router():
    """Gemini router (with model rotation) or None in heuristic mode."""
    from hermes.utils.llm_router import make_router

    router = make_router()
    return router if router.available else None


def _store() -> WebStore:
    return WebStore(DB_PATH)


def _master() -> "MasterStore":
    from hermes.web.master_store import MasterStore

    return MasterStore(DB_PATH)


# Static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


# ---------------------------------------------------------------- auth

from fastapi import Request  # noqa: E402

from hermes.web import auth as _auth  # noqa: E402


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    return await _auth.auth_middleware_dispatch(request, call_next, DB_PATH)


def _callback_base(request: Request) -> str:
    """The externally-visible backend origin (Render URL or localhost).

    X-Forwarded-Proto takes precedence behind Render's TLS proxy.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{proto}://{host}"


@app.get("/api/auth/google")
def google_login(request: Request):
    """Start sign-in: redirect the browser to Google's consent screen."""
    if not _auth.auth_enabled():
        raise HTTPException(503, "Sign-in is not configured on this instance")
    return RedirectResponse(
        _auth.google_login_url(_callback_base(request), _auth.make_state())
    )


@app.get("/api/auth/google/callback")
async def google_callback(request: Request):
    """Google returns here with ?code=... — exchange, upsert, mint JWT,
    then redirect to the frontend with the token in the #fragment."""
    code = request.query_params.get("code", "")
    state = request.query_params.get("state", "")
    if not code:
        return RedirectResponse(f"{_auth.frontend_url()}/auth/callback#error=missing_code")
    if state and not _auth.check_state(state):
        return RedirectResponse(f"{_auth.frontend_url()}/auth/callback#error=bad_state")

    profile = await _auth.exchange_code(code, _callback_base(request))
    if not profile.get("email"):
        return RedirectResponse(f"{_auth.frontend_url()}/auth/callback#error=no_email")

    user_id = _auth.upsert_user(
        DB_PATH, profile["sub"], profile["email"], profile["name"], profile["picture"]
    )
    token = _auth.create_token(user_id, profile["email"])
    return RedirectResponse(f"{_auth.frontend_url()}/auth/callback#token={token}")


@app.get("/api/auth/me")
def auth_me(request: Request):
    """Current session info (works whether auth is on or off)."""
    if not _auth.auth_enabled():
        return {"auth_enabled": False, "user": None}
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = _auth.verify_token(header[7:])
            user = _auth.get_user(DB_PATH, int(payload["sub"]))
            if user:
                return {"auth_enabled": True, "user": user}
        except (ValueError, KeyError, TypeError):
            pass
    return {"auth_enabled": True, "user": None}


@app.post("/api/auth/logout")
def auth_logout():
    """Stateless JWTs: logout is client-side token discard."""
    return {"ok": True}


def _serve_frontend() -> HTMLResponse:
    """The built React landing page (frontend/dist) or the legacy page."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    legacy = STATIC_DIR / "index.html"
    if legacy.exists():
        return HTMLResponse(legacy.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ApplyJin</h1><p>frontend not built</p>", status_code=500)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    load_dotenv()
    return _serve_frontend()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> HTMLResponse:
    """The ApplyJin Console — React SPA when built, legacy workbench otherwise."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    legacy = STATIC_DIR / "index.html"
    if legacy.exists():
        return HTMLResponse(legacy.read_text(encoding="utf-8"))
    raise HTTPException(404, "dashboard not found")


# --------------------------------------------------------- LLM settings

import yaml as _yaml  # noqa: E402

_LLM_CONFIG_PATH = Path("config/llm_config.yml")


def _read_llm_config() -> dict:
    """Read the current LLM config, returning a safe dict with defaults."""
    if _LLM_CONFIG_PATH.exists():
        try:
            return _yaml.safe_load(_LLM_CONFIG_PATH.read_text()) or {}
        except Exception:
            pass
    return {"chain": [], "generation": {"temperature": 0.3, "max_tokens": 4096, "timeout_seconds": 60}}


def _write_llm_config(cfg: dict) -> None:
    """Persist LLM config to the YAML file."""
    _LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LLM_CONFIG_PATH.write_text(_yaml.dump(cfg, default_flow_style=False, sort_keys=False))


@app.get("/api/settings/llm")
def get_llm_settings() -> JSONResponse:
    """Return the current LLM provider config (keys redacted)."""
    cfg = _read_llm_config()
    # Redact API keys before sending to the frontend
    safe_chain = []
    for entry in cfg.get("chain", []):
        e = dict(entry)
        if e.get("api_key"):
            e["api_key_set"] = True
            e["api_key"] = ""  # never send real keys to the browser
        else:
            e["api_key_set"] = False
        safe_chain.append(e)
    return JSONResponse({"chain": safe_chain, "generation": cfg.get("generation", {})})


@app.post("/api/settings/llm")
async def update_llm_settings(payload: dict) -> JSONResponse:
    """Update LLM provider config. Pass api_key to set, empty string to unset."""
    cfg = _read_llm_config()
    chain = cfg.get("chain", [])

    updates = payload.get("chain", [])
    for update in updates:
        provider = update.get("provider", "")
        model = update.get("model", "")
        api_key = update.get("api_key", "")
        api_base = update.get("api_base", "")

        # Find existing entry or append new one
        found = False
        for entry in chain:
            if entry.get("provider") == provider and entry.get("model") == model:
                if api_key:
                    entry["api_key"] = api_key
                elif api_key == "":
                    entry["api_key"] = ""
                if api_base:
                    entry["api_base"] = api_base
                found = True
                break
        if not found and model:
            new_entry = {"provider": provider, "model": model}
            if api_key:
                new_entry["api_key"] = api_key
            if api_base:
                new_entry["api_base"] = api_base
            chain.append(new_entry)

    # Remove entries with empty keys (user wants to unset)
    chain = [e for e in chain if e.get("api_key") or e.get("provider") == "ollama"]

    cfg["chain"] = chain
    _write_llm_config(cfg)

    # Return redacted config
    safe_chain = []
    for entry in chain:
        e = dict(entry)
        if e.get("api_key"):
            e["api_key_set"] = True
            e["api_key"] = ""
        else:
            e["api_key_set"] = False
        safe_chain.append(e)
    return JSONResponse({"ok": True, "chain": safe_chain})


# ---------------------------------------------------------- master CV DB


@app.get("/api/master/profile")
def master_get_profile() -> JSONResponse:
    store = _master()
    try:
        return JSONResponse(store.get_profile())
    finally:
        store.close()


@app.put("/api/master/profile")
async def master_update_profile(profile: dict) -> JSONResponse:
    store = _master()
    try:
        store.update_profile(**profile)
        return JSONResponse(store.get_profile())
    finally:
        store.close()


@app.get("/api/master/stats")
def master_stats() -> JSONResponse:
    store = _master()
    try:
        return JSONResponse(store.stats())
    finally:
        store.close()


@app.get("/api/master/experiences")
def master_list_experiences() -> JSONResponse:
    store = _master()
    try:
        return JSONResponse(store.list_experiences())
    finally:
        store.close()


@app.post("/api/master/experiences")
async def master_add_experience(entry: dict) -> JSONResponse:
    store = _master()
    try:
        entry_id = store.add_experience(
            title=entry.get("title", ""),
            organization=entry.get("organization", ""),
            location=entry.get("location", ""),
            start_date=entry.get("start_date", ""),
            end_date=entry.get("end_date", ""),
            description=entry.get("description", ""),
            bullets=entry.get("bullets", []),
            tags=entry.get("tags", ""),
        )
        return JSONResponse({"id": entry_id})
    finally:
        store.close()


@app.delete("/api/master/experiences/{entry_id}")
def master_delete_experience(entry_id: int) -> JSONResponse:
    store = _master()
    try:
        if not store.delete_experience(entry_id):
            raise HTTPException(404, "Experience not found")
        return JSONResponse({"deleted": entry_id})
    finally:
        store.close()


@app.get("/api/master/projects")
def master_list_projects() -> JSONResponse:
    store = _master()
    try:
        return JSONResponse(store.list_projects())
    finally:
        store.close()


@app.post("/api/master/projects")
async def master_add_project(entry: dict) -> JSONResponse:
    store = _master()
    try:
        entry_id = store.add_project(
            name=entry.get("name", ""),
            tech=entry.get("tech", ""),
            description=entry.get("description", ""),
            bullets=entry.get("bullets", []),
            link=entry.get("link", ""),
            tags=entry.get("tags", ""),
        )
        return JSONResponse({"id": entry_id})
    finally:
        store.close()


@app.delete("/api/master/projects/{entry_id}")
def master_delete_project(entry_id: int) -> JSONResponse:
    store = _master()
    try:
        if not store.delete_project(entry_id):
            raise HTTPException(404, "Project not found")
        return JSONResponse({"deleted": entry_id})
    finally:
        store.close()


@app.get("/api/master/skills")
def master_list_skills() -> JSONResponse:
    store = _master()
    try:
        return JSONResponse(store.list_skills())
    finally:
        store.close()


@app.post("/api/master/skills")
async def master_add_skills(payload: dict) -> JSONResponse:
    store = _master()
    try:
        added = store.add_skills(payload.get("category", "other"), payload.get("names", []))
        return JSONResponse({"added": added})
    finally:
        store.close()


@app.post("/api/master/import-resume")
async def master_import_resume(payload: dict) -> JSONResponse:
    """Import a stored web resume into the master DB (rich parse)."""
    from hermes.web.master_store import import_from_resume_text

    resume_id = payload.get("resume_id")
    if not resume_id:
        raise HTTPException(400, "resume_id required")
    web = _store()
    master = _master()
    try:
        resume = web.get_resume(int(resume_id))
        if not resume:
            raise HTTPException(404, "Resume not found")
        result = import_from_resume_text(resume["raw_text"], master)
        return JSONResponse({"imported": result, "stats": master.stats()})
    finally:
        web.close()
        master.close()


# ---------------------------------------------------------- public landing API


_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.get("/api/public/stats")
def public_stats() -> JSONResponse:
    """Aggregated, non-sensitive numbers for the landing page."""
    from hermes.agents.tracker import Tracker

    store = _store()
    try:
        tracker = Tracker(DB_PATH)
        try:
            t_stats = tracker.stats(days=30)
            style = tracker.active_style_guide()
        finally:
            tracker.close()
        return JSONResponse(
            {
                "applications": t_stats["total"],
                "interviews": t_stats["interviews"],
                "response_rate": t_stats["response_rate"],
                "waitlist": store.waitlist_count(),
                "style_guide_version": style[0],
                "boards_supported": 8,
                "agents": 7,
            }
        )
    finally:
        store.close()


@app.post("/api/public/waitlist")
async def join_waitlist(
    email: str = Form(...), source: str = Form("")
) -> JSONResponse:
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "That email address doesn't look right.")
    store = _store()
    try:
        row_id, message = store.add_waitlist(email, source or "landing")
        if row_id is None:
            return JSONResponse({"ok": True, "message": message, "duplicate": True})
        return JSONResponse({"ok": True, "message": message, "duplicate": False})
    finally:
        store.close()


# ---------------------------------------------------------------- resumes


@app.post("/api/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...), name: str = Form("")
) -> JSONResponse:
    from hermes.utils.resume_parser import parse_resume_text

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{datetime.utcnow():%Y%m%d%H%M%S}_{Path(file.filename).name}"
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)

    text = _extract_text(dest)
    if not text.strip() or len(text.strip()) < 50:
        raise HTTPException(400, "Could not extract text — scanned PDF or empty file?")

    profile = load_profile()
    parsed = parse_resume_text(text, profile)
    store = _store()
    try:
        resume_id = store.add_resume(
            name=name or Path(file.filename).stem,
            content_md=parsed.raw_text,
            raw_text=text,
            skills=sorted({s for b in parsed.bullets for s in b.skills})
            or profile.all_skills[:20],
            file_path=str(dest),
        )
    finally:
        store.close()
    return {"id": resume_id, "name": name, "bullets": len(parsed.bullets)}


def _extract_text(path: Path) -> str:
    from hermes.utils.resume_parser import load_resume_text

    try:
        return load_resume_text(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Parse failed: {exc}") from exc


@app.post("/api/resumes/create")
async def create_resume(
    name: str = Form(...), content: str = Form(...)
) -> JSONResponse:
    if not content.strip():
        raise HTTPException(400, "Content is empty")
    from hermes.utils.resume_parser import parse_resume_text

    profile = load_profile()
    parsed = parse_resume_text(content, profile)
    store = _store()
    try:
        resume_id = store.add_resume(
            name=name or "Pasted resume",
            content_md=content,
            raw_text=content,
            skills=sorted({s for b in parsed.bullets for s in b.skills}),
        )
    finally:
        store.close()
    return {"id": resume_id}


@app.get("/api/resumes")
def list_resumes() -> JSONResponse:
    store = _store()
    try:
        return JSONResponse(store.list_resumes())
    finally:
        store.close()


@app.get("/api/resumes/{resume_id}")
def get_resume(resume_id: int) -> JSONResponse:
    store = _store()
    try:
        resume = store.get_resume(resume_id)
        if not resume:
            raise HTTPException(404, "Resume not found")
        return JSONResponse(resume)
    finally:
        store.close()


@app.delete("/api/resumes/{resume_id}")
def delete_resume(resume_id: int) -> JSONResponse:
    store = _store()
    try:
        if not store.delete_resume(resume_id):
            raise HTTPException(404, "Resume not found")
        return {"deleted": resume_id}
    finally:
        store.close()


# ---------------------------------------------------------- job descriptions


@app.post("/api/job-descriptions")
async def add_jd(
    title: str = Form(...), company: str = Form(...), content: str = Form(...)
) -> JSONResponse:
    if len(content.strip()) < 30:
        raise HTTPException(400, "JD content too short")
    store = _store()
    try:
        jd_id = store.add_jd(title, company, content)
        # Run ghost-job scoring on the new JD
        from hermes.utils.ghost_score import score_jd as _ghost_score
        ghost = _ghost_score(content, title=title, company=company)
        store.save_jd_ghost_score(jd_id, ghost["ghost_score"], ghost["flags"])
    finally:
        store.close()
    return {"id": jd_id}


@app.get("/api/job-descriptions")
def list_jds() -> JSONResponse:
    store = _store()
    try:
        return JSONResponse(store.list_jds())
    finally:
        store.close()


@app.get("/api/job-descriptions/{jd_id}")
def get_jd(jd_id: int) -> JSONResponse:
    store = _store()
    try:
        jd = store.get_jd(jd_id)
        if not jd:
            raise HTTPException(404, "JD not found")
        # Attach ghost score if available
        ghost = store.get_jd_ghost_score(jd_id)
        if ghost:
            jd["ghost_score"] = ghost["ghost_score"]
            jd["ghost_flags"] = ghost["flags"]
        return JSONResponse(jd)
    finally:
        store.close()


@app.post("/api/job-descriptions/{jd_id}/extract-keywords")
def extract_keywords(jd_id: int) -> JSONResponse:
    from hermes.web.pipeline import extract_keywords as run

    store = _store()
    try:
        jd = store.get_jd(jd_id)
        if not jd:
            raise HTTPException(404, "JD not found")
        keywords = run(jd["content"], _router())
        store.save_jd_keywords(jd_id, keywords)
        return JSONResponse(keywords)
    finally:
        store.close()


# ---------------------------------------------------------- applications


@app.post("/api/applications")
async def create_application(
    resume_id: int = Form(...), jd_id: int = Form(...)
) -> JSONResponse:
    from hermes.web.pipeline import extract_keywords, score_keywords_for, score_pair

    store = _store()
    try:
        resume = store.get_resume(resume_id)
        jd = store.get_jd(jd_id)
        if not resume:
            raise HTTPException(404, "Resume not found")
        if not jd:
            raise HTTPException(404, "JD not found")

        # Pin the keyword set at creation so before/after scores are
        # always computed against the same list (apples to apples).
        keywords = jd.get("keywords") or extract_keywords(jd["content"], _router())
        if not jd.get("keywords"):
            store.save_jd_keywords(jd_id, keywords)

        pinned = score_keywords_for(keywords)
        scores = score_pair(resume["raw_text"], jd["content"], keywords)
        # Per-category breakdown (hard_skills, tools, soft_skills, etc.)
        from hermes.web.pipeline import category_breakdown
        categories = category_breakdown(resume["raw_text"], keywords)
        app_id = store.create_application(resume_id, jd_id)
        # Persist the score breakdown as JSON for the Console UI
        breakdown = {
            "keyword_match": scores["keyword_match"],
            "semantic_similarity": scores["semantic_similarity"],
            "overall": scores["overall"],
            "matched_keywords": scores.get("matched_keywords", []),
            "missing_keywords": scores.get("missing_keywords", []),
            "categories": categories,
        }
        store.update_application(
            app_id,
            kw_before=scores["keyword_match"],
            sem_before=scores["semantic_similarity"],
            ats_before=scores["overall"],
            score_keywords=_json_dump(pinned),
            fit_breakdown_json=_json_dump(breakdown),
        )
        return JSONResponse({"id": app_id, "scores_before": scores})
    finally:
        store.close()


def _json_dump(value) -> str:
    import json as _json

    return _json.dumps(value)


@app.get("/api/applications")
def list_applications() -> JSONResponse:
    store = _store()
    try:
        return JSONResponse(store.list_applications())
    finally:
        store.close()


@app.get("/api/applications/{app_id}")
def get_application(app_id: int) -> JSONResponse:
    store = _store()
    try:
        record = store.get_application(app_id)
        if not record:
            raise HTTPException(404, "Application not found")
        return JSONResponse(record)
    finally:
        store.close()


@app.post("/api/applications/{app_id}/tailor")
async def tailor_application(
    app_id: int, selected_keywords: str = Form("[]")
) -> JSONResponse:
    import json as _json

    from hermes.web.pipeline import (
        score_keywords_for,
        score_pair,
        tailor as run_tailor,
        category_breakdown,
    )
    from hermes.web.master_store import MasterStore
    from hermes.web.selection import select_for_jd
    from hermes.web.tailor_v3 import tailor_from_master

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record:
            raise HTTPException(404, "Application not found")
        resume = store.get_resume(record["resume_id"])
        jd = store.get_jd(record["jd_id"])
        if not resume or not jd:
            raise HTTPException(404, "Linked resume/JD missing")

        try:
            selected = _json.loads(selected_keywords)
        except ValueError:
            selected = []

        master = MasterStore(DB_PATH)
        try:
            master_stats = master.stats()
            has_master = master_stats["experiences"] + master_stats["projects"] > 0
            router = _router()

            if has_master:
                # ---- v3: select from the master CV database
                keywords = jd.get("keywords") or {}
                snapshot = master.snapshot()
                report = select_for_jd(snapshot, keywords, jd["content"])
                result = tailor_from_master(
                    snapshot, report, jd["content"], keywords, router
                )
                result["selection"] = [
                    {
                        "kind": e.kind, "title": e.title,
                        "score": e.score,
                        "matched_keywords": e.matched_keywords[:6],
                    }
                    for e in report.experiences + report.projects
                ]
                result["skill_selection"] = report.skills
                result["gaps"] = report.missing_skills
            else:
                # ---- legacy: raw resume + chosen keywords
                result = run_tailor(resume, jd, selected, router)
                result["selection"] = []
                result["skill_selection"] = selected
                result["gaps"] = []
        finally:
            master.close()

        pinned = record.get("score_keywords") or score_keywords_for(
            jd.get("keywords") or {}
        )
        scores_after = score_pair(
            result["tailored_resume_md"], jd["content"], {"hard_skills": pinned}
        )
        # Per-category breakdown on the tailored resume
        tailoring_keywords = jd.get("keywords") or {}
        tailoring_categories = category_breakdown(result["tailored_resume_md"], tailoring_keywords)
        delta = {
            "overall": round(scores_after["overall"] - (record["ats_before"] or 0), 1),
            "keyword_match": round(
                scores_after["keyword_match"] - (record["kw_before"] or 0), 1
            ),
            "semantic": round(
                scores_after["semantic_similarity"] - (record["sem_before"] or 0), 1
            ),
        }
        store.update_application(
            app_id,
            tailored_resume_md=result["tailored_resume_md"],
            selected_keywords=_json.dumps(selected),
            kw_after=scores_after["keyword_match"],
            sem_after=scores_after["semantic_similarity"],
            ats_after=scores_after["overall"],
            fit_breakdown_json=_json_dump({
                "keyword_match": scores_after["keyword_match"],
                "semantic_similarity": scores_after["semantic_similarity"],
                "overall": scores_after["overall"],
                "matched_keywords": scores_after.get("matched_keywords", []),
                "missing_keywords": scores_after.get("missing_keywords", []),
                "categories": tailoring_categories,
            }),
            status="ready",
        )
        return JSONResponse(
            {
                "tailored_resume_md": result["tailored_resume_md"],
                "scores_after": scores_after,
                "delta": delta,
                "guardrail_violations": result["guardrail_violations"],
                "validated": result["validated"],
                "model_used": result["model_used"],
                "selection": result.get("selection", []),
                "skill_selection": result.get("skill_selection", []),
                "gaps": result.get("gaps", []),
            }
        )
    finally:
        store.close()


@app.post("/api/applications/{app_id}/email-template")
def generate_email_template(
    app_id: int,
    template_type: str = Form("application"),
) -> JSONResponse:
    """Draft an application/follow-up/thank-you email (never sends)."""
    from hermes.web.master_store import MasterStore
    from hermes.web.tailor_v3 import (
        extract_contacts,
        generate_email_template as draft,
    )

    if template_type not in ("application", "follow_up", "thank_you", "inquiry"):
        raise HTTPException(400, "template_type must be application|follow_up|thank_you|inquiry")

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record:
            raise HTTPException(404, "Application not found")
        jd = store.get_jd(record["jd_id"])
        if not jd:
            raise HTTPException(404, "JD not found")

        master = MasterStore(DB_PATH)
        try:
            profile = master.get_profile()
        finally:
            master.close()
        if not profile.get("full_name"):
            profile["full_name"] = "the candidate"

        contacts = extract_contacts(jd["content"])
        email_text = draft(
            profile, jd, template_type=template_type, router=_router()
        )
        store.update_application(
            app_id,
            email_md=email_text,
            hiring_manager=contacts.get("hiring_manager") or "",
            emails_json=_json_dump(contacts.get("emails") or []),
        )
        return JSONResponse(
            {
                "email_md": email_text,
                "hiring_manager": contacts.get("hiring_manager"),
                "emails": contacts.get("emails", []),
            }
        )
    finally:
        store.close()


@app.get("/api/job-descriptions/{jd_id}/contacts")
def jd_contacts(jd_id: int) -> JSONResponse:
    """Emails + hiring manager extracted from a stored JD."""
    from hermes.web.tailor_v3 import extract_contacts

    store = _store()
    try:
        jd = store.get_jd(jd_id)
        if not jd:
            raise HTTPException(404, "JD not found")
        return JSONResponse(extract_contacts(jd["content"]))
    finally:
        store.close()


@app.post("/api/applications/{app_id}/cover-letter")
def generate_cover_letter(app_id: int) -> JSONResponse:
    from hermes.web.pipeline import cover_letter as run

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record:
            raise HTTPException(404, "Application not found")
        if not record.get("tailored_resume_md"):
            raise HTTPException(400, "Tailor the resume first")
        resume = store.get_resume(record["resume_id"])
        jd = store.get_jd(record["jd_id"])
        letter = run(resume, jd, record["tailored_resume_md"], _router())
        store.update_application(app_id, cover_letter_md=letter)
        return JSONResponse({"cover_letter_md": letter})
    finally:
        store.close()


@app.get("/api/applications/{app_id}/download-resume")
def download_resume(app_id: int) -> FileResponse:
    from hermes.utils.latex_generator import compile_tex, markdown_to_latex
    from hermes.web.pipeline import to_pdf

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record or not record.get("tailored_resume_md"):
            raise HTTPException(404, "Tailored resume not found — tailor first")

        # LaTeX route (Trey Hunner template) first, browser-print fallback.
        md_text = record["tailored_resume_md"]
        tex = markdown_to_latex(md_text)
        latex_pdf = compile_tex(tex, PDF_DIR / f"latex_resume_{app_id}.pdf")
        if latex_pdf is not None:
            return FileResponse(
                latex_pdf, filename=f"hermes_resume_{app_id}.pdf",
                media_type="application/pdf",
            )
        out = to_pdf(md_text, PDF_DIR, f"resume_{app_id}")
        if out.suffix != ".pdf":
            raise HTTPException(503, "PDF engine unavailable — HTML fallback at " + str(out))
        return FileResponse(out, filename=f"hermes_resume_{app_id}.pdf")
    finally:
        store.close()


@app.get("/api/applications/{app_id}/download-resume-latex")
def download_resume_latex(app_id: int) -> FileResponse:
    """Editable LaTeX source bundle (.tex + resume.cls) for Overleaf etc."""
    import zipfile
    from pathlib import Path as _Path

    from hermes.utils.latex_generator import latex_bundle, markdown_to_latex

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record or not record.get("tailored_resume_md"):
            raise HTTPException(404, "Tailored resume not found — tailor first")
        tex = markdown_to_latex(record["tailored_resume_md"])
        bundle = latex_bundle(tex, PDF_DIR / f"latex_src_{app_id}.zip")
        return FileResponse(
            bundle, filename=f"hermes_resume_{app_id}_latex.zip",
            media_type="application/zip",
        )
    finally:
        store.close()


@app.get("/api/applications/{app_id}/download-cover-letter")
def download_cover_letter(app_id: int) -> FileResponse:
    from hermes.utils.latex_generator import (
        compile_tex,
        cover_letter_to_latex,
    )
    from hermes.web.pipeline import to_pdf

    store = _store()
    try:
        record = store.get_application(app_id)
        if not record or not record.get("cover_letter_md"):
            raise HTTPException(404, "Cover letter not found — generate first")
        letter_md = record["cover_letter_md"]
        resume = store.get_resume(record["resume_id"])
        name = ""
        contact = ""
        if resume:
            raw = resume["raw_text"].splitlines()
            non_empty = [l.strip() for l in raw if l.strip()]
            if non_empty:
                import re as _re

                name = _re.sub(r"^[#*\s]+", "", non_empty[0]).strip()
            if len(non_empty) > 1:
                contact = non_empty[1]

        tex = cover_letter_to_latex(letter_md, name=name, contact=contact)
        latex_pdf = compile_tex(tex, PDF_DIR / f"latex_cover_{app_id}.pdf")
        if latex_pdf is not None:
            return FileResponse(
                latex_pdf, filename=f"hermes_cover_{app_id}.pdf",
                media_type="application/pdf",
            )
        out = to_pdf(letter_md, PDF_DIR, f"cover_{app_id}")
        if out.suffix != ".pdf":
            raise HTTPException(503, "PDF engine unavailable — HTML fallback at " + str(out))
        return FileResponse(out, filename=f"hermes_cover_{app_id}.pdf")
    finally:
        store.close()


# ---------------------------------------------------------------- misc


@app.post("/api/score")
async def score(
    resume_text: str = Form(...), jd_text: str = Form(...)
) -> JSONResponse:
    from hermes.web.pipeline import score_pair

    scores = score_pair(resume_text, jd_text, {})
    return JSONResponse(scores)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# -------------------------------------------------------- copilot chat


@app.post("/api/copilot/chat")
async def copilot_chat(payload: dict) -> JSONResponse:
    """RAG-grounded chat copilot. Context: Master CV + ChromaDB + JD."""
    from hermes.utils.llm_router import LLMUnavailable
    from hermes.web.master_store import MasterStore

    app_id = payload.get("application_id")
    user_message = payload.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "Message is required")

    store = _store()
    try:
        # Build context
        jd_text = ""
        tailored_text = ""
        if app_id:
            record = store.get_application(app_id)
            if record:
                jd = store.get_jd(record["jd_id"])
                if jd:
                    jd_text = jd["content"][:3000]
                tailored_text = (record.get("tailored_resume_md") or "")[:2000]
                # Save user message
                store.add_copilot_message(app_id, "user", user_message)

        # Master CV context
        master = MasterStore(DB_PATH)
        try:
            snapshot = master.snapshot()
        finally:
            master.close()

        profile = snapshot.get("profile", {})
        skills = snapshot.get("skills", {})
        experiences = snapshot.get("experiences", [])[:5]
        projects = snapshot.get("projects", [])[:3]

        # RAG: retrieve relevant bullets from ChromaDB
        bullets_text = ""
        try:
            from hermes.utils.experience_library import ExperienceLibrary
            library = ExperienceLibrary(use_chroma=True)
            retrieved = library.query(user_message, n_results=8)
            if retrieved:
                bullets_text = "\n".join(f"- {r['text']}" for r in retrieved)
        except Exception:
            pass  # ChromaDB unavailable — proceed without RAG

        # Assemble context
        exp_text = ""
        for e in experiences:
            exp_text += f"\n### {e.get('title', '')} @ {e.get('organization', '')}\n"
            for b in e.get("bullets", [])[:3]:
                exp_text += f"- {b}\n"

        proj_text = ""
        for p in projects:
            proj_text += f"\n### {p.get('name', '')}\n"
            for b in p.get("bullets", [])[:2]:
                proj_text += f"- {b}\n"

        skills_text = ", ".join(s for group in skills.values() for s in group)

        system_prompt = (
            "You are ApplyJin Copilot, a career assistant grounded in the user's "
            "verified resume facts. You can rephrase, contextualize, and advise, "
            "but NEVER invent achievements, skills, dates, or companies not present "
            "in the provided facts. If you don't have enough information, say so "
            "clearly. Keep responses concise and actionable."
        )

        user_prompt = f"""## User Question
{user_message}

## Candidate Profile
Name: {profile.get('full_name', 'N/A')}
Headline: {profile.get('headline', 'N/A')}
Summary: {profile.get('summary', 'N/A')[:500]}
Skills: {skills_text[:800]}

## Relevant Experience (RAG-retrieved)
{bullets_text or '(no relevant bullets found)'}

## Work History
{exp_text or '(none)'}

## Projects
{proj_text or '(none)'}

## Target Job Description
{jd_text or '(no specific job targeted)'}

## Currently Tailored Resume (if any)
{tailored_text or '(not yet tailored)'}

Answer the user's question using ONLY the facts above. Cite specific
experiences or projects when relevant. If asked about something not in
your facts, say it's not in the Master CV."""

        router = _router()
        try:
            response = router.complete(prompt=user_prompt, system=system_prompt)
            answer = response.text
        except LLMUnavailable:
            answer = (
                "I can't reach the LLM right now. Please check your API key "
                "in Settings, or try again in a moment."
            )

        # Save assistant message
        if app_id:
            store.add_copilot_message(app_id, "assistant", answer)

        return JSONResponse({"reply": answer})
    finally:
        store.close()


@app.get("/api/copilot/history/{app_id}")
def copilot_history(app_id: int) -> JSONResponse:
    """Chat history for an application."""
    store = _store()
    try:
        return JSONResponse(store.get_copilot_history(app_id))
    finally:
        store.close()


# -------------------------------------------------------- pipeline (Kanban)


@app.get("/api/pipeline")
def get_pipeline() -> JSONResponse:
    """Applications grouped by pipeline status for the Kanban board."""
    store = _store()
    try:
        return JSONResponse(store.list_pipeline())
    finally:
        store.close()


@app.post("/api/pipeline/{app_id}/status")
async def update_pipeline_status(app_id: int, payload: dict) -> JSONResponse:
    """Move an application to a new pipeline status."""
    status = payload.get("status", "")
    store = _store()
    try:
        record = store.get_application(app_id)
        if not record:
            raise HTTPException(404, "Application not found")
        store.update_pipeline_status(app_id, status)
        return JSONResponse({"ok": True, "status": status})
    finally:
        store.close()


# --------------------------------------------------- LinkedIn generator


@app.post("/api/linkedin/generate")
async def generate_linkedin(payload: dict) -> JSONResponse:
    """Generate LinkedIn headline + About section from Master CV."""
    from hermes.utils.llm_router import LLMUnavailable
    from hermes.web.master_store import MasterStore

    master = MasterStore(DB_PATH)
    try:
        snapshot = master.snapshot()
    finally:
        master.close()

    profile = snapshot.get("profile", {})
    skills = snapshot.get("skills", {})
    experiences = snapshot.get("experiences", [])[:5]
    projects = snapshot.get("projects", [])[:3]

    if not profile.get("full_name"):
        raise HTTPException(400, "Set your name in the Master CV profile first")

    # Build context
    skills_text = ", ".join(s for group in skills.values() for s in group)
    exp_text = ""
    for e in experiences:
        exp_text += f"- {e.get('title', '')} @ {e.get('organization', '')}: {', '.join(e.get('bullets', [])[:2])}\n"
    proj_text = ""
    for p in projects:
        proj_text += f"- {p.get('name', '')}: {', '.join(p.get('bullets', [])[:2])}\n"

    system_prompt = (
        "You are a LinkedIn profile copywriter. Generate a professional LinkedIn "
        "headline (max 220 chars) and an About section (max 2600 chars) using ONLY "
        "the facts provided. The headline should be concise, keyword-rich for ATS, "
        "and convey the person's value proposition. The About section should tell "
        "their career story in first person, highlight key achievements with metrics "
        "where available, and end with a call to action. Do NOT invent any facts."
    )

    user_prompt = f"""Generate a LinkedIn headline and About section for:

Name: {profile.get('full_name', '')}
Current headline: {profile.get('headline', '')}
Summary: {profile.get('summary', '')[:500]}
Skills: {skills_text[:600]}

Experience:
{exp_text or '(none)'}

Projects:
{proj_text or '(none)'}

Return JSON with keys: "headline" (string, max 220 chars) and "about" (string, max 2600 chars)."""

    router = _router()
    try:
        response = router.complete_json(prompt=user_prompt, system=system_prompt)
        headline = response.get("headline", "")
        about = response.get("about", "")
    except (LLMUnavailable, Exception):
        # Heuristic fallback
        headline = f"{profile.get('headline', '')} | {skills_text[:100]}"
        about = (
            f"Hi, I'm {profile.get('full_name', '')}. "
            f"{profile.get('summary', 'I build things with code.')}\n\n"
            f"Core skills: {skills_text[:300]}\n\n"
            f"Let's connect."
        )

    return JSONResponse({"headline": headline, "about": about})


# --------------------------------------------------- Phase 7: visa + salary


@app.get("/api/visa-sponsorship/{company}")
def visa_sponsorship(company: str) -> JSONResponse:
    """Look up visa sponsorship history for a company."""
    from hermes.utils.visa_sponsorship import lookup_sponsorship
    result = lookup_sponsorship(company)
    return JSONResponse(result)


@app.post("/api/visa-sponsorship")
async def add_visa_sponsor(payload: dict) -> JSONResponse:
    """Manually mark an employer as a sponsor."""
    from hermes.utils.visa_sponsorship import add_sponsor
    employer = payload.get("employer", "")
    sponsorship = payload.get("sponsorship", "yes")
    evidence = payload.get("evidence", "")
    if not employer:
        raise HTTPException(400, "employer is required")
    add_sponsor(employer, sponsorship, evidence)
    return JSONResponse({"ok": True})


@app.get("/api/salary-insights")
def salary_insights(title: str = "", location: str = "", company: str = "") -> JSONResponse:
    """Get salary insights for a job title + location."""
    from hermes.utils.salary_insights import get_salary_insights
    if not title:
        raise HTTPException(400, "title is required")
    result = get_salary_insights(title, location, company)
    return JSONResponse(result)
