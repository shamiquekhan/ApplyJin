<div align="center">

# ApplyJin

**The self-learning job application agent.**

*Auto-tailor + auto-fill. Human clicks submit.*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Tests](https://img.shields.io/badge/tests-149%20passing-brightgreen)](#testing)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)](LICENSE)

</div>

---

ApplyJin (built on the **Hermes** engine) is a fully open-source, self-learning
multi-agent system that automates the job application pipeline — from discovery
to tailored, ATS-optimized application packets — while keeping a human in the
loop for every submit decision.

It runs entirely on your machine with **zero subscription costs**, using free
LLM tiers (Gemini), local embeddings, and open-source libraries.

## What it does

| Capability | How |
|---|---|
| **Discover** | Scrape 8+ job boards via JobSpy + Greenhouse/Lever public JSON APIs |
| **Analyze** | Extract must-have skills, seniority, contacts, emails from every JD (LLM + heuristic fallback) |
| **Score** | Word-boundary keyword coverage + semantic similarity + seniority alignment |
| **Select** | Rank your *Master CV Database* and pick the top-3 experiences + top-3 projects per job |
| **Tailor** | Compose a focused, ATS-friendly resume from selected facts — never invented ones |
| **Generate** | Cover letters, interview prep (STAR), outreach drafts, application emails |
| **Export** | Professional PDFs via LaTeX (Trey Hunner template) or browser print — plus editable `.tex` bundles |
| **Track** | Every application in SQLite: fit score, ATS before/after, A/B variant, outcomes |
| **Learn** | Chi-squared A/B tests on resume styles → versioned style guides fed back into tailoring |

## The Master CV Database

The core idea: one complete, structured record of your career (experiences,
projects, education, certifications, 70+ skills) lives in SQLite. Every tailored
resume is **selected** from this database — the selection engine ranks each entry
against the job description (0.7 × keyword coverage + 0.3 × semantic
similarity) and the LLM composes only from chosen facts. Post-hoc guardrails
validate every output against the master facts: invented companies, dates, or
gap-skills are flagged before you ever see them.

## Architecture

```
┌─────────────────────────── FRONTEND (ApplyJin) ───────────────────────────┐
│  React 18 + Vite + TypeScript + Tailwind CSS + framer-motion              │
│  Landing page (cinematic, Almarai/Instrument Serif, WCAG 2.2 AA)          │
│  Console at /dashboard — Master CV · Resumes · JDs · Tailor & Score ·      │
│  Applications                                                             │
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
│  rotation under free-tier 20 RPM limits) → Ollama (local)                │
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

## Agent workflow

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

## Guardrails — non-negotiable

1. **No fabrication** — every tailored fact traces to the Master CV database; violations are flagged and surfaced in the UI
2. **No auto-submit** — the browser agent fills forms and stops; the human clicks submit
3. **Rate limits** — max N applications/day (default 20), enforced in the tracker
4. **No duplicates** — the same job is never applied to twice
5. **Privacy** — everything local: SQLite, ChromaDB, files; your `.env` and configs are gitignored

## Quickstart

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
python -m playwright install chromium

cp config/llm_config.example.yml config/llm_config.yml   # add a free Gemini key
echo 'GEMINI_API_KEY=...' > .env

hermes index-resume     # RAG-index your base resume
hermes run --offline    # sample jobs, full pipeline, zero risk
hermes review           # approve/reject each tailored application
hermes dashboard        # terminal funnel + follow-ups + A/B verdict

# Web: landing + Console
hermes serve            # → http://127.0.0.1:8000  (/dashboard = Console)

# Frontend development
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

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

## Testing

```bash
python -m pytest tests/ -q    # 149 tests, ~20s
```

Coverage spans: fabrication guardrails, word-boundary skill matching, the
selection engine, LaTeX compilation, A/B statistics, email triage, tracker
migrations, and the web API.

## Project layout

```
ApplyJin/
├── hermes/                  # backend engine
│   ├── agents/              # scout, analyzer, scorer, tailor, cover, tracker,
│   │                        # application (fill), learning, triage, prep,
│   │                        # outreach, dashboard, A/B, ATS boards
│   ├── web/                 # FastAPI app, master store, selection engine,
│   │                        # tailor v3, web store
│   ├── utils/               # LLM router, embeddings, skill matching,
│   │                        # LaTeX generator, PDF, experience library
│   ├── prompts/             # LLM prompt templates
│   └── cli.py               # Typer CLI (15 commands)
├── frontend/                # ApplyJin React app
│   ├── src/components/      # Hero, About, Features, Waitlist, Footer, Console
│   └── src/lib/             # api client, router, markdown
├── tests/                   # 149 tests across 7 suites
├── scripts/                 # cron wrappers, demo seeder
├── config/                  # YAML configs (examples committed)
├── docs/                    # ARCHITECTURE, SETUP, GUARDRAILS, LEARNING
└── data/                    # SQLite DB, artifacts (gitignored)
```

## Roadmap

- [x] Phase 1 — pipeline foundation, tracker, human review
- [x] Phase 2 — ChromaDB RAG, auto-fill, PDF export
- [x] Phase 3 — learning loop, A/B testing, email triage
- [x] Phase 4 — dashboards, prep, outreach, multi-profile, Docker
- [x] Master CV Database + selection-based tailoring
- [x] ApplyJin frontend (landing + Console), LaTeX packets
- [ ] LangGraph graph-based orchestration of the agent pipeline
- [ ] LinkedIn/Greenhouse auto-fill coverage expansion

## License

CC BY-NC 4.0 — Attribution-NonCommercial 4.0 International. See [LICENSE](LICENSE).

You are free to use, modify, and share this project for **non-commercial**
purposes with attribution. Commercial use requires a separate license from
the author.

## Acknowledgments

Inspired by and built with: [JobSpy](https://github.com/speedyapply/JobSpy),
[Resume Matcher](https://github.com/srbhr/Resume-Matcher), [LangGraph](https://github.com/langchain-ai/langgraph),
[ChromaDB](https://github.com/chroma-core/chroma), [LiteLLM](https://github.com/BerriAI/litellm),
and the Trey Hunner LaTeX resume template. See `hermes_guide.md` for the full
research landscape (15+ projects analyzed).
