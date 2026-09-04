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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from hermes.config import load_dotenv, load_profile
from hermes.web.store import WebStore

app = FastAPI(title="Hermes Dashboard", version="0.6.0")

# Vite dev server talks to the API cross-origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


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
        app_id = store.create_application(resume_id, jd_id)
        store.update_application(
            app_id,
            kw_before=scores["keyword_match"],
            sem_before=scores["semantic_similarity"],
            ats_before=scores["overall"],
            score_keywords=_json_dump(pinned),
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
