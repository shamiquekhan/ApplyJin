<div align="center">

# ApplyJin

**The self-learning job application agent.**

*Auto-tailor + auto-fill. Human clicks submit.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Tests](https://img.shields.io/badge/tests-164%20passing-brightgreen)](#testing)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)](LICENSE)

</div>

---

ApplyJin (built on the **Hermes** engine) is a fully open-source, self-learning
multi-agent system that automates the job application pipeline — from discovery
to tailored, ATS-optimized application packets — while keeping a human in the
loop for every submit decision.

It runs entirely on your machine with **zero subscription costs**, using free
LLM tiers (Gemini), local embeddings, and open-source libraries.

---

## Quickstart — run it locally

**Prerequisites:** Python 3.11+, Node 18+, a free [Gemini API key](https://aistudio.google.com) (optional — the agent falls back to heuristic mode without one).

```bash
# 1. Clone the repo
git clone https://github.com/shamiquekhan/ApplyJin.git
cd ApplyJin

# 2. Set up the backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"

# 3. Add your API key (paste your Gemini key after the =)
echo "GEMINI_API_KEY=your-key-here" > .env

# 4. Install the browser for PDF generation + auto-fill
python -m playwright install chromium

# 5. Import your resume into the master CV database
hermes index-resume

# 6. Start the backend (serves the API + the built-in Console)
hermes serve                        # → http://127.0.0.1:8000

# 7. In a second terminal — start the frontend dev server
cd frontend && npm install && npm run dev  # → http://localhost:3000
```

That's it. Open **http://localhost:3000** for the landing page, or
**http://localhost:3000/dashboard** for the Console.

**No API key?** The agent still works — it tailors using keyword matching
and heuristic scoring instead of LLM calls. You'll see a warning in the
Console but the full pipeline runs.

**Want to add your key from the UI?** Open the Console → Settings tab →
paste your Gemini or Groq key → Save. No `.env` file required.

---

### One-minute summary

| What you type | What happens |
|---|---|
| `hermes serve` | Starts the API + built-in Console at `localhost:8000` |
| `hermes run --offline` | Scrape sample jobs, tailor, score, track — no LLM needed |
| `hermes review` | Approve or reject each tailored application |
| `hermes export --id N` | Regenerate PDF + LaTeX packet for an application |

### CLI surface

| Command | Purpose |
|---|---|
| `hermes run` | Full pipeline: scout → analyze → score → tailor → track |
| `hermes scout --ats stripe,anthropic` | Greenhouse/Lever public board search |
| `hermes index-resume` | Vector-index resume bullets (ChromaDB) |
| `hermes learn [--apply]` | Analyze outcomes, promote style guide |
| `hermes triage-email [--apply]` | IMAP outcome triage (dry-run default) |
| `hermes fill --id N` | Auto-fill an application form — never submits |
| `hermes prep --id N` | Interview prep doc (STAR stories from your facts) |
| `hermes outreach --id N` | LinkedIn note + follow-up email drafts |
| `hermes dashboard` / `serve` | TUI / web dashboards |
| `hermes export --id N` | Regenerate PDFs |

---

## Features

### 1. Job Scout
Scrapes 8+ job boards (LinkedIn, Indeed, Glassdoor, etc.) via [JobSpy](https://github.com/speedyapply/JobSpy) plus
Greenhouse and Lever public JSON APIs — no scraping, no blocking. Fuzzy
deduplication means the same role posted on three boards is one application.

### 2. Master CV Database
One complete, structured record of your career: experiences, projects,
education, certifications, and 70+ skills. Every tailored resume is **selected**
from this database — the selection engine ranks each entry against the job
(0.7 keyword + 0.3 semantic similarity) and picks the top 3 experiences +
top 3 projects. Post-hoc guardrails validate every output against master facts.

### 3. Smart Tailoring (Tailor v3)
The agent composes an ATS-friendly resume from selected facts only — never
invented ones. X-Y-Z bullet formulas, quantified impact, keyword embedding,
and 15+ specialized skills (ATS optimization, no-invention guardrails) are
woven into the prompt. Guardrail violations are surfaced in the UI before
you see the output.

### 4. LaTeX PDF Export
Professional-quality PDFs via `pdflatex` using the Trey Hunner resume
template. Cover letters in a matching template. Editable `.tex` source
included. Falls back to Playwright browser print when LaTeX is unavailable.

### 5. Fabrication Guardrails
Every tailored fact traces back to your Master CV database. Invented
companies, dates, or gap-skills are flagged before you ever see them.
The agent never auto-submits — you click the final button, every time.

### 6. Learning Loop
Every application is randomly assigned variant A or B. Once 30+ outcomes
accumulate, a Yates-corrected chi-squared test declares the winning resume
style, and its phrasing patterns are promoted into the tailor prompt
(versioned, rollback-able). Style guides, keyword lift analysis, and
ATS-delta correlation feed back into the next tailor run.

### 7. Email Triage & Outreach
Connect IMAP to auto-classify offer, interview, and rejection emails.
Fuzzy company matching feeds outcomes into the tracker automatically.
The outreach agent drafts LinkedIn connection notes and follow-up emails.

### 8. Stealth Auto-Fill
A hardened Playwright browser fills application forms using your real
resume data — but never auto-submits. You click submit, every time.

### 9. Interview Prep
STAR stories generated from your real experience library. Questions are
matched to the job description and answered using only your actual
accomplishments.

---

## How It Works

```
hermes run
   │
   ▼
1. JOB SCOUT ─── scrape boards → fuzzy-dedup (company, title)
   │
   ▼ per job:
2. JD ANALYZER ─ LLM JSON extraction ── skills, seniority, contacts
   │             (heuristic lexicon fallback when keyless/rate-limited)
   ▼
3. FIT SCORER ── 0.35·keyword + 0.35·semantic + 0.15·seniority + 0.15·years
   │             jobs below threshold are skipped with reasons
   ▼
4. SELECTOR ──── rank Master CV entries vs this JD
   │             top-3 experiences + top-3 projects + skill intersection
   ▼
5. TAILOR v3 ─── LLM composes from selected facts only
   │             guardrails validate output vs master DB (no fabrication)
   ▼
6. COVER LETTER / EMAIL TEMPLATES ── grounded in the same selection
   │
   ▼
7. EXPORT ────── resume.md → LaTeX (.tex + resume.cls) → pdflatex PDF
   │             cover letter in matching template
   ▼
8. TRACKER ───── SQLite row: fit score, ATS before/after, A/B variant
   │
   ▼  human reviews → hermes review → hermes fill (never auto-submit)
   │
   ▼ outcomes flow back (manual or email triage):
9. LEARNING ─── keyword lift + ATS-delta correlation + A/B chi²
                → style guide vN → injected into next tailor run
```

**The learning loop in one line:** every application is randomly assigned
variant A or B; once ≥30 outcomes accumulate, a Yates-corrected chi-squared
test declares the winning resume style, and its phrasing patterns are promoted
into the tailor prompt (versioned, rollback-able).

---

## The Learning Loop

The learning loop is what makes ApplyJin *self-learning*. Every time you
tailor a resume, the agent randomly picks variant A or B (different
phrasing, structure, or emphasis). Once you have 30+ outcomes (interviews
vs rejections) for both variants, a statistical test declares a winner.

What gets learned:
- **Keyword lift** — which keywords correlate with callbacks
- **ATS delta** — which tailoring moves actually improve ATS scores
- **Style patterns** — phrasing that wins interviews gets promoted into the
  tailor prompt as a versioned style guide
- **Rollback** — every style guide is versioned; you can roll back if a
  pattern stops working

The result: the agent gets sharper with every application, and you can
watch the A/B verdicts in the Console.

---

## Architecture

```
┌─────────────────────────── FRONTEND (ApplyJin) ───────────────────────────┐
│  React 18 + Vite + TypeScript + Tailwind CSS + framer-motion              │
│  Landing page (cinematic, Almarai/Instrument Serif, WCAG 2.2 AA)          │
│  Console at /dashboard — Master CV · Resumes · JDs · Tailor & Score ·      │
│  Applications · Settings                                                  │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ REST (same origin / Vite proxy)
┌──────────────────────────────▼───────────────────────────────────────────┐
│                            BACKEND (FastAPI)                              │
│                                                                           │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Master CV   │  │ Selection    │  │ Tailor v3    │  │ Document        │ │
│  │ Database    │→ │ Engine       │→ │ (LLM +       │→ │ Generators      │ │
│  │ (SQLite)    │  │ (rank+pick)  │  │ guardrails)  │  │ (LaTeX/PDF)     │ │
│  └────────────┘  └─────────────┘  └──────────────┘  └─────────────────┘ │
│                                                                           │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Job Scout   │  │ JD Analyzer │  │ ATS Scorer   │  │ Learning Loop   │ │
│  │ (JobSpy +   │  │ (Gemini +   │  │ (word-bound. │  │ (A/B chi² +     │ │
│  │  ATS APIs)  │  │  heuristic) │  │  + semantic) │  │  style guides)  │ │
│  └────────────┘  └─────────────┘  └──────────────┘  └─────────────────┘ │
│                                                                           │
│  LLM Router: Gemini 3.6 Flash → flash-latest → flash-lite (model-pool    │
│  rotation under free-tier 20 RPM limits) → Groq → Ollama (local)         │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │
                    SQLite (data/hermes.db)
        ChromaDB (experience-library vectors, ONNX MiniLM)
        File artifacts (resumes, letters, .tex bundles, PDFs)
```

### Tech stack — all free / open source

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind, framer-motion, lucide-react | Cinematic dark theme, WCAG 2.2 AA audited |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic | 40+ REST endpoints |
| LLM | Google Gemini free tier via LiteLLM | Model-pool rotation, rate-limit-aware retry, heuristic fallback |
| Embeddings | ONNX MiniLM (ChromaDB-bundled) | No torch needed; fully local |
| Vector store | ChromaDB | Experience library for RAG-style retrieval |
| Scraping | JobSpy, Greenhouse/Lever public APIs | 8+ boards, ToS-friendly |
| Documents | pdflatex, Playwright, WeasyPrint, pdfplumber, python-docx | LaTeX-first PDF generation with fallbacks |
| Browser automation | Playwright (stealth-hardened) | Auto-fill that never auto-submits |
| Storage | SQLite | Tracker + master CV + web store, one file |

---

## Guardrails — non-negotiable

1. **No fabrication** — every tailored fact traces to the Master CV database; violations are flagged and surfaced in the UI
2. **No auto-submit** — the browser agent fills forms and stops; the human clicks submit
3. **Rate limits** — max N applications/day (default 20), enforced in the tracker
4. **No duplicates** — the same job is never applied to twice
5. **Privacy** — everything local: SQLite, ChromaDB, files; your `.env` and configs are gitignored

---

## Deployment (free)

The split deployment: **frontend on Vercel**, **backend on Render**.

### Backend → Render (Docker)

1. Push this repo to GitHub
2. [render.com](https://render.com) → **New → Blueprint** → select the repo
   (the included `render.yaml` configures everything) — or New → Docker Service manually
3. Set the `GEMINI_API_KEY` env var in the dashboard
4. Service goes live at `https://<name>.onrender.com` with `/health`,
   the full REST API, and LaTeX PDF generation (texlive included in the image)

### Frontend → Vercel

1. [vercel.com](https://vercel.com) → **Add New → Project** → import the repo
2. **Root Directory: `frontend`** (Vercel auto-detects Vite; `vercel.json` sets the SPA rewrites)
3. Environment variable: `VITE_API_URL = https://<your-render-service>.onrender.com`
4. Deploy → live at `https://<name>.vercel.app` with the Console at `/dashboard`

CORS is preconfigured: all `*.vercel.app` origins are accepted, plus anything
listed in the backend's `ALLOWED_ORIGINS` env var (for custom domains).

### Sign-in with Google (protects the Console)

Works in every browser (Firefox, Chrome, Safari) — it's the standard
"Continue with Google" flow. Auth activates **only** when configured;
zero-config local runs stay open.

1. **Google Cloud Console** → [console.cloud.google.com](https://console.cloud.google.com)
   → create (or pick) a project
2. **APIs & Services → OAuth consent screen** → External → fill app name
   (`ApplyJin`) and your email → add yourself as a **test user** → save
3. **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
   → *Web application*
4. **Authorized redirect URIs** — add your backend callback exactly:
   ```
   https://applyjin.onrender.com/api/auth/google/callback
   ```
   (and `http://localhost:8000/api/auth/google/callback` for local testing)
5. Copy the **Client ID** and **Client Secret**
6. **On Render** (Environment tab) set:
   | Variable | Value |
   |---|---|
   | `GOOGLE_CLIENT_ID` | `...apps.googleusercontent.com` |
   | `GOOGLE_CLIENT_SECRET` | `...` |
   | `FRONTEND_URL` | your Vercel URL, e.g. `https://applyjin.vercel.app` |
   | `AUTH_SECRET` | any long random string (keeps sessions alive across deploys) |
7. Redeploy — the Console now requires sign-in; the landing page stays public

The flow: the Console redirects to Google → Google returns to the backend →
the backend mints a week-long JWT and sends the browser to
`/auth/callback#token=...` (URL fragment — never logged or leaked via
referrers) → the SPA stores it and opens the Console.

**Free-tier caveats:** the Render service sleeps after ~15 min idle (first
request takes ~30s to wake) and its SQLite data resets on each deploy — the
public deployment is an ephemeral demo. For day-to-day use with persistent
data, run locally and expose it with a free Cloudflare tunnel
(`cloudflared tunnel --url http://localhost:8000`).

---

## Testing

```bash
python -m pytest tests/ -q    # 164 tests, ~20s
```

Coverage spans: fabrication guardrails, word-boundary skill matching, the
selection engine, LaTeX compilation, A/B statistics, email triage, tracker
migrations, web API, and authentication.

---

## Project layout

```
ApplyJin/
├── hermes/                  # backend engine
│   ├── agents/              # scout, analyzer, scorer, tailor, cover, tracker,
│   │                        # application (fill), learning, triage, prep,
│   │                        # outreach, dashboard, A/B, ATS boards
│   ├── web/                 # FastAPI app, auth, master store, selection engine,
│   │                        # tailor v3, web store, LLM settings
│   ├── utils/               # LLM router, embeddings, skill matching,
│   │                        # LaTeX generator, PDF, experience library
│   ├── prompts/             # LLM prompt templates
│   └── cli.py               # Typer CLI (15 commands)
├── frontend/                # ApplyJin React app
│   ├── src/components/      # Hero, About, Features, Waitlist, Footer, Console,
│   │                        # FeaturesPage, LoginScreen, AuthCallback
│   └── src/lib/             # api client, session (JWT), router, markdown
├── tests/                   # 164 tests across 7 suites
├── scripts/                 # cron wrappers, demo seeder
├── config/                  # YAML configs (examples committed)
├── docs/                    # ARCHITECTURE, SETUP, GUARDRAILS, LEARNING
└── data/                    # SQLite DB, artifacts (gitignored)
```

---

## Roadmap

- [x] Phase 1 — pipeline foundation, tracker, human review
- [x] Phase 2 — ChromaDB RAG, auto-fill, PDF export
- [x] Phase 3 — learning loop, A/B testing, email triage
- [x] Phase 4 — dashboards, prep, outreach, multi-profile, Docker
- [x] Master CV Database + selection-based tailoring
- [x] ApplyJin frontend (landing + Console), LaTeX packets
- [x] Google OAuth sign-in for the Console
- [x] Settings panel — add API keys from the UI, no .env required
- [ ] LangGraph graph-based orchestration of the agent pipeline
- [ ] LinkedIn/Greenhouse auto-fill coverage expansion

---

## License

CC BY-NC 4.0 — Attribution-NonCommercial 4.0 International. See [LICENSE](LICENSE).

You are free to use, modify, and share this project for **non-commercial**
purposes with attribution. Commercial use requires a separate license from
the author.

---

## Acknowledgments

Inspired by and built with: [JobSpy](https://github.com/speedyapply/JobSpy),
[Resume Matcher](https://github.com/srbhr/Resume-Matcher), [LangGraph](https://github.com/langchain-ai/langgraph),
[ChromaDB](https://github.com/chroma-core/chroma), [LiteLLM](https://github.com/BerriAI/litellm),
and the Trey Hunner LaTeX resume template. See `hermes_guide.md` for the full
research landscape (15+ projects analyzed).

---

<div align="center">

Made by [Shamique Khan](https://github.com/shamiquekhan)

</div>
