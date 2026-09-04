

# Hermes: Self-Learning Job Application Agent

## Complete Research Guide & Implementation Plan

### 100% Free / Open-Source Stack | September 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Landscape Analysis: Existing Projects](#2-landscape-analysis-existing-projects)
3. [Hermes Architecture: The 7-Agent Pipeline](#3-hermes-architecture-the-7-agent-pipeline)
4. [Free Resource Stack](#4-free-resource-stack)
5. [Implementation Plan: 4 Phases](#5-implementation-plan-4-phases)
6. [Agent Deep Dives](#6-agent-deep-dives)
7. [Guardrails, Ethics &amp; Safety](#7-guardrails-ethics--safety)
8. [The Learning Loop](#8-the-learning-loop)
9. [Project File Structure](#9-project-file-structure)
10. [Getting Started](#10-getting-started)
11. [References &amp; Repositories](#11-references--repositories)

---

## 1. Executive Summary

**Hermes** is a fully open-source, self-learning multi-agent system that automates the job search pipeline — from discovery to tailored application materials — while keeping the human in the loop for the final submit decision. It is designed to run entirely on your machine with zero subscription costs, using free LLM APIs, local models, and open-source libraries.

### Core Value Proposition

- **Auto-Discover**: Scrape 8+ job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google, Naukri, etc.) via a single unified API
- **Auto-Analyze**: Extract must-have skills, seniority signals, and keyword gaps from every JD
- **Auto-Tailor**: Rewrite resume bullets using RAG over your own experience library — no fabricated facts
- **Auto-Generate**: Write role-specific cover letters grounded in the JD analysis
- **Auto-Track**: Log every application, resume variant, and outcome in a local SQLite + CSV tracker
- **Auto-Learn**: Periodically review tracker data to identify which phrasing/keyword patterns correlate with interview callbacks, then feed insights back into the tailoring prompts

> *"Auto-tailor + auto-fill, human clicks submit."*
> Fully automated submission violates ToS on LinkedIn/Indeed and risks account bans. A safer v1 keeps the human as the final gate while automating 90% of the grunt work.

---

## 2. Landscape Analysis: Existing Projects

After researching 15+ open-source job automation projects, here are the most relevant ones to learn from and differentiate against:

### 2.1 Career-Ops (santifer)

- **What it does**: CLI-agnostic job-search command center. Evaluates job offers against your CV with an A-H rubric, generates ATS-tailored PDFs, finds contacts, tracks applications.
- **Key lesson**: The "human-in-the-loop" design — it never submits, only drafts. It is the first reference implementation of the CareerOps Manifesto.
- **Free?** Yes. MIT license. Runs on free/local models via OpenRouter, Ollama, or any OpenAI-compatible endpoint.
- **Architecture**: YAML-config-driven, AI-CLI-integrated (Claude Code, Codex, etc.)
- **Repo**: `github.com/santifer/career-ops`

### 2.2 ApplyPilot (Pickle-Pixel)

- **What it does**: 6-stage autonomous pipeline — discovers jobs across 5+ boards, scores them against your resume with AI, tailors resume per job, writes cover letters, and **submits applications autonomously** via Playwright/Selenium.
- **Key lesson**: The 6-stage pipeline (discover -> enrich -> score -> tailor -> cover -> apply) is a proven pattern. Their dry-run mode (`--dry-run`) is essential for safe testing.
- **Free?** Yes. GNU AGPL v3. Uses Gemini API free tier (15 RPM / 1M tokens/day).
- **Architecture**: Python 3.11+ core, Node.js for Playwright MCP server, Claude Code CLI for browser-driven submission.
- **Repo**: `github.com/Pickle-Pixel/ApplyPilot`

### 2.3 AIHawk (feder-cr)

- **What it does**: Browser automation + web scraping to read job postings, then auto-apply with tailored resume and cover letter. Uses `invisible_playwright` — a C++-patched Firefox that passes reCAPTCHA, hCaptcha, Cloudflare Turnstile.
- **Key lesson**: The stealth layer is critical. `invisible_playwright` patches Firefox at the engine level, making it impossible to detect via JavaScript fingerprinting.
- **Free?** Yes. Core architecture is open source.
- **Repo**: `github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk`

### 2.4 Jobber (sentient-engineering)

- **What it does**: Autonomous browser-controlled job applier. You provide a resume and it applies by controlling your own browser.
- **Key lesson**: Browser-control approach (controlling the user's own Chrome instance) is lower-risk than headless automation because it uses real user sessions.
- **Free?** Yes. Open source.
- **Repo**: `github.com/sentient-engineering/jobber`

### 2.5 ai-job-agent (AkbarDevop)

- **What it does**: 13 Claude Code skills (1 orchestrator + 12 verbs) for LinkedIn Easy Apply, Greenhouse, Lever, Jobvite, Ashby, Outlook triage, tracking. Built during a real job search with 228+ applications.
- **Key lesson**: The "career coach" persona pattern — you talk to it naturally, it chains the right skills. The 5-tab TUI dashboard (Applications / Outreach / Follow-ups / Pipeline / Reports) is excellent UX.
- **Free?** Yes. MIT license.
- **Repo**: `github.com/AkbarDevop/ai-job-agent`

### 2.6 ApplyKit (wihlarkop)

- **What it does**: Self-hosted web app (SvelteKit + FastAPI) for AI CV generation, cover letters, fit analysis, smart apply, Kanban tracker. BYOK — bring your own API key.
- **Key lesson**: Self-hosted = full data privacy. No cloud, no subscription. Docker one-command setup.
- **Free?** Yes. Open source. Uses LiteLLM for model routing.
- **Repo**: `github.com/wihlarkop/applykit`

### 2.7 Resume Matcher (srbhr)

- **What it does**: Open-source ATS tool. Parses resume + JD, extracts keywords, computes vector similarity using Qdrant, gives match score and suggestions.
- **Key lesson**: Vector similarity (embeddings) for resume-JD matching is more robust than simple keyword counting. The Qdrant-based approach can be replicated with ChromaDB for a fully local setup.
- **Free?** Yes. Open source.
- **Repo**: `github.com/srbhr/Resume-Matcher`

### 2.8 LinkedIn AI Auto Job Applier (GodsScion)

- **What it does**: Free, open-source LinkedIn automation. Finds relevant jobs, fills application questions, tailors resume, applies. 100+ jobs in under an hour.
- **Key lesson**: The control panel (`app.py` Flask server) for settings, run controls, and applied jobs history is a nice touch for non-technical users.
- **Free?** Yes. Open source.
- **Repo**: `github.com/GodsScion/Auto_job_applier_linkedIn`

### 2.9 MadsLorentzen/ai-job-search

- **What it does**: 38K stars AI job search skill for Claude Code. Evaluate postings, tailor CVs, write cover letters, prep interviews.
- **Key lesson**: The "fork and own it" model — the repo is public, so you must use a private repo for your personal data.
- **Free?** Yes. Open source.
- **Repo**: `github.com/MadsLorentzen/ai-job-search`

### 2.10 CoverLetterMaker (stanleyume)

- **What it does**: Simple open-source cover letter generator using Ollama/local LLMs. Editable output with one-click copy.
- **Key lesson**: Local LLM for cover letters is viable and free. The "no placeholder" approach (fully generated, not templated) produces better results.
- **Free?** Yes. Open source.
- **Repo**: `github.com/stanleyume/coverlettermaker`

---

## 3. Hermes Architecture: The 7-Agent Pipeline

Hermes uses a **LangGraph** state machine to orchestrate 7 specialized agents. LangGraph is chosen because it provides deterministic control, checkpointing, human-in-the-loop interrupts, and durable execution — essential for a regulated-like workflow where you cannot afford hallucinated submissions.

```
+-----------------------------------------------------------------------------+
|                           HERMES LANGGRAPH PIPELINE                          |
+-----------------------------------------------------------------------------+
|                                                                              |
|   +----------+    +----------+    +----------+    +----------+            |
|   | JobScout |--->| JDAnalyzer|--->|FitScorer |--->| Resume   |            |
|   |          |    |          |    |          |    | Tailor   |            |
|   +----------+    +----------+    +----------+    +----+-----+            |
|        ^                                               |                   |
|        |                    +---------------------------+                   |
|        |                    |                                              |
|   +----+----+         +----------+    +----------+    +----------+      |
|   | Learning|<--------| Tracker  |<---| Cover    |<---| Human    |      |
|   | Agent   |         |          |    | Letter   |    | Review   |      |
|   +---------+         +----------+    +----------+    +----------+      |
|        |                                                                  |
|        +------------------------------------------------------------------->|
|                              (Feedback Loop)                               |
|                                                                              |
|   Shared State Store: SQLite + ChromaDB (vector experience library)        |
|                                                                              |
+-----------------------------------------------------------------------------+
```

### State Schema (TypedDict)

```python
class HermesState(TypedDict):
    # Input
    search_config: SearchConfig      # title, location, boards, filters
    base_resume: ResumeDocument      # parsed base resume (facts)
  
    # Pipeline artifacts
    raw_jobs: List[JobPosting]       # from JobScout
    analyzed_jobs: List[JobAnalysis] # from JDAnalyzer
    scored_jobs: List[ScoredJob]     # from FitScorer (filtered)
    tailored_resumes: List[TailoredResume]  # from ResumeTailor
    cover_letters: List[CoverLetter] # from CoverLetterAgent
  
    # Human checkpoint
    human_decisions: List[HumanDecision]  # approve/reject/skip per job
  
    # Output
    submitted_apps: List[ApplicationRecord]  # from ApplicationAgent
  
    # Learning
    outcomes: List[OutcomeRecord]    # no_response / rejected / interview
    learned_patterns: LearnedPatterns  # from LearningAgent
```

---

## 4. Free Resource Stack

Every component below has a **zero-cost** option. No subscriptions, no credit cards required.

| Layer                          | Component                               | Free Option                                  | Why It Fits                                                                                             |
| ------------------------------ | --------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Orchestration**        | LangGraph                               | MIT license, free                            | Graph-based state machine with checkpointing, human-in-the-loop, durable execution                      |
| **Job Scraping**         | JobSpy                                  | `pip install python-jobspy`                | Scrapes LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Naukri, Bayt, BDJobs into a pandas DataFrame |
| **Vector DB**            | ChromaDB                                | `pip install chromadb`                     | Open-source, local, stores resume bullet embeddings for RAG retrieval                                   |
| **Embeddings**           | sentence-transformers                   | `pip install sentence-transformers`        | Local embedding model (`all-MiniLM-L6-v2`) — no API calls, no data leaves machine                    |
| **LLM (Cloud)**          | Gemini API                              | Google AI Studio — 1M tokens/day, 15 RPM    | Free tier is generous enough for resume tailoring + cover letters for dozens of jobs daily              |
| **LLM (Cloud alt)**      | OpenRouter                              | 28 free models, 20 RPM, 50 req/day           | Aggregates free tiers from DeepSeek, Llama, Qwen, Gemma. One API key, many models                       |
| **LLM (Cloud alt)**      | NVIDIA NIM                              | 120+ open-weight models, ~40 req/min         | Widest model choice, no credit card, OpenAI-compatible endpoint                                         |
| **LLM (Cloud alt)**      | Groq                                    | Llama, Qwen — 30 req/min, ~1,000-14,400/day | Fastest inference for open models                                                                       |
| **LLM (Local)**          | Ollama                                  | `ollama pull llama3.1` / `qwen2.5`       | Fully private, runs on your GPU/CPU. No rate limits, no data leaves machine                             |
| **LLM Router**           | LiteLLM                                 | `pip install litellm`                      | Single interface to Gemini, OpenRouter, Ollama, Groq, NVIDIA NIM. Failover between free providers       |
| **Browser Auto**         | Playwright                              | `pip install playwright`                   | Microsoft's automation framework. Multi-browser, auto-waiting, network interception                     |
| **Stealth**              | playwright-stealth                      | `pip install playwright-stealth`           | Hides`navigator.webdriver`, automation flags. Drop-in plugin for Playwright                           |
| **Stealth (alt)**        | nodriver                                | `pip install nodriver`                     | CDP-direct, no WebDriver, no`navigator.webdriver` flag. Zero-config stealth                           |
| **Stealth (alt)**        | Camoufox                                | Engine-level Firefox patches                 | C++-patched Firefox. Passes canvas, WebGL, font checks. For high-detection targets                      |
| **Resume Parsing**       | pdfplumber + python-docx                | `pip install pdfplumber python-docx`       | Extract text from PDF/DOCX resumes reliably                                                             |
| **Resume Parsing (alt)** | pyresparser                             | `pip install pyresparser`                  | Extracts name, email, skills, experience, education from resumes into structured JSON                   |
| **ATS Scoring**          | Resume Matcher logic                    | Open-source algorithm                        | Keyword extraction + vector similarity (can be replicated with ChromaDB + scikit-learn)                 |
| **PDF Generation**       | WeasyPrint                              | `pip install weasyprint`                   | Server-side HTML -> PDF for tailored resumes                                                            |
| **PDF Generation (alt)** | Playwright print-to-PDF                 | Built-in                                     | Headless Chrome renders HTML and prints to PDF                                                          |
| **Tracking**             | SQLite + pandas                         | Built into Python                            | Zero-config local database. CSV export for spreadsheets                                                 |
| **Dashboard**            | Rich / Textual                          | `pip install rich textual`                 | Terminal UI for live tracker dashboard (zero dependencies)                                              |
| **Scheduling**           | cron / systemd / Windows Task Scheduler | Built-in OS                                  | Run Hermes on a schedule (e.g., scan twice daily)                                                       |

### Recommended Free LLM Strategy

1. **Primary**: Gemini Flash (free tier) — fast, high quality, 1M tokens/day
2. **Backup**: OpenRouter free models (DeepSeek-R1, Llama 3.3 70B, Qwen3 Coder) — when Gemini hits rate limits
3. **Privacy mode**: Ollama with `llama3.1:8b` or `qwen2.5:7b` — for sensitive resume data you don't want in the cloud
4. **Router**: LiteLLM handles failover automatically

---

## 5. Implementation Plan: 4 Phases

### Phase 1: Foundation (Week 1-2)

**Goal**: End-to-end pipeline for discovery -> analysis -> tailoring -> human review

| Task                        | Deliverable                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| Set up project scaffold     | `hermes/` repo with Poetry/pipenv, config files                                        |
| Integrate JobSpy            | `hermes scout --title "Python Developer" --location "Remote"` CLI                      |
| Build JD Analyzer           | Extract skills, seniority, keywords from JD using Gemini + structured output (JSON mode) |
| Build Fit Scorer            | Compute keyword overlap + vector similarity score. Filter jobs below threshold           |
| Build Resume Tailor v1      | Prompt-based rewriting of base resume bullets per JD. No RAG yet                         |
| Build Cover Letter Agent v1 | Generate cover letter from JD + base resume                                              |
| Build Tracker v1            | SQLite schema + CLI commands (`hermes tracker list`, `hermes tracker add`)           |
| Human review checkpoint     | Pause pipeline after tailoring, show diff, wait for human approve/reject                 |

**Milestone**: Run `hermes run` and get a queue of 10 tailored applications ready for your review.

### Phase 2: Intelligence (Week 3-4)

**Goal**: RAG-powered tailoring + ATS optimization + better stealth

| Task                   | Deliverable                                                                                                                                |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Set up ChromaDB        | Ingest base resume bullets as embeddings. Each bullet = one document with metadata (skill tags, impact metric)                             |
| Build Resume Tailor v2 | RAG retrieval: given JD keywords, retrieve top-N most relevant bullets from ChromaDB, then rewrite around them                             |
| Add ATS Score          | Compute ATS keyword-match score (resume vs JD). Show before/after score to human                                                           |
| Add Stealth Layer      | Integrate playwright-stealth or nodriver for form-filling dry-runs                                                                         |
| Build Auto-Fill v1     | Playwright script that navigates to application URL, fills personal info, uploads tailored resume + cover letter.**Does NOT submit** |
| Add LiteLLM router     | Failover between Gemini -> OpenRouter -> Ollama automatically                                                                              |
| Enhance Tracker        | Add resume variant hash, cover letter hash, ATS score, application URL to each record                                                      |

**Milestone**: `hermes run --auto-fill` opens Chrome, fills 5 forms, stops at submit button. You click submit.

### Phase 3: Learning (Week 5-6)

**Goal**: Self-learning loop with proxy signals

| Task                        | Deliverable                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| Design Learning Agent       | Analyze tracker data: which keywords/phrases in tailored resumes correlate with "interview" outcomes? |
| Proxy Signal: ATS Score     | Track "ATS score delta" (before tailoring vs after) per application. Higher delta = better tailoring  |
| Proxy Signal: Response Rate | Track response rate by job board, by keyword cluster, by resume variant                               |
| Feedback Loop               | Feed top-performing bullet patterns back into Resume Tailor's system prompt as "style guide"          |
| A/B Test Framework          | Randomly assign 2 resume variants per similar job, track which gets more responses                    |
| Email Triage (optional)     | Scan Gmail/Outlook for rejection/interview emails, auto-update tracker statuses                       |

**Milestone**: After 50 applications, Learning Agent produces a "winning phrases" report and updates the tailor prompt.

### Phase 4: Scale & Polish (Week 7-8)

**Goal**: Production-ready, robust, beautiful

| Task                        | Deliverable                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| Terminal Dashboard          | Rich TUI showing: pipeline status, today's jobs, response funnel, follow-up reminders    |
| Web UI (optional)           | Streamlit or FastAPI + htmx dashboard for non-CLI users                                  |
| Multi-profile support       | Switch between "Backend Engineer" and "ML Engineer" profiles with different base resumes |
| Company career page scraper | Custom scraper for Greenhouse, Lever, Workday, Ashby using Playwright                    |
| Cold outreach agent         | Draft LinkedIn connection requests + follow-up emails to hiring managers                 |
| Interview prep agent        | Generate STAR-format prep docs based on JD + your experience                             |
| Docker packaging            | `docker compose up` for one-command deployment                                         |
| Documentation               | Full README, architecture docs, contribution guide                                       |

**Milestone**: `docker compose up` -> configure in browser -> `hermes run` -> check dashboard -> land interview.

---

## 6. Agent Deep Dives

### 6.1 JobScout

**Purpose**: Discover and collect job postings from multiple sources.

**Implementation**:

```python
from jobspy import scrape_jobs
import pandas as pd

def scout_jobs(config: SearchConfig) -> pd.DataFrame:
    jobs = scrape_jobs(
        site_name=config.boards,  # ["linkedin", "indeed", "glassdoor", "google"]
        search_term=config.title,
        location=config.location,
        results_wanted=config.max_results,
        hours_old=config.max_age_hours,
        is_remote=config.remote_only,
        proxies=config.proxies,  # optional rotating proxies
    )
    # Deduplicate by (title, company, location) fuzzy matching
    jobs = deduplicate_jobs(jobs)
    return jobs
```

**Key considerations**:

- JobSpy returns a pandas DataFrame — perfect for filtering
- LinkedIn rate-limits unauthenticated scraping within a few hundred results. Use proxies or authenticated cookies for scale
- 18-22% of postings are "ghost jobs" — add a "freshness" heuristic (hours_old < 72, company verified)
- Deduplication is critical: the same role appears on 3 boards as 3 rows. Use fuzzy string matching on title+company

### 6.2 JD Analyzer

**Purpose**: Extract structured signals from raw job descriptions.

**Output schema**:

```python
class JobAnalysis(BaseModel):
    job_id: str
    title: str
    company: str
  
    # Extracted signals
    required_skills: List[str]           # e.g., ["Python", "Kubernetes", "gRPC"]
    preferred_skills: List[str]          # e.g., ["Rust", "Terraform"]
    seniority_level: str                 # junior / mid / senior / staff
    years_experience: int                # minimum years required
    must_have_keywords: List[str]        # exact phrases from JD
    company_values: List[str]            # e.g., ["customer-obsessed", "move fast"]
    red_flags: List[str]                 # e.g., ["unpaid internship", "rockstar"]
    salary_range: Optional[Tuple[int, int]]
    remote_policy: str                   # fully_remote / hybrid / onsite
```

**Implementation approach**:

- Use Gemini's JSON mode (or Ollama's structured output) with a detailed system prompt
- Two-pass extraction: first pass extracts raw entities, second pass validates and normalizes
- Cache analysis results to avoid re-parsing the same JD

### 6.3 Fit Scorer

**Purpose**: Score how well your base profile matches the job, and filter out poor fits.

**Scoring algorithm**:

```python
def compute_fit_score(resume: ResumeDocument, analysis: JobAnalysis) -> float:
    # 1. Keyword overlap (Jaccard similarity)
    resume_skills = set(resume.skills)
    required_skills = set(analysis.required_skills)
    keyword_score = len(resume_skills & required_skills) / len(required_skills)
  
    # 2. Vector similarity (semantic match beyond exact keywords)
    resume_embedding = embed_text(resume.summary)
    jd_embedding = embed_text(analysis.normalized_description)
    semantic_score = cosine_similarity(resume_embedding, jd_embedding)
  
    # 3. Seniority alignment
    seniority_score = seniority_match(resume.seniority, analysis.seniority_level)
  
    # 4. Experience threshold
    exp_score = 1.0 if resume.years_experience >= analysis.years_experience else 0.5
  
    # Weighted combination
    final_score = (
        0.35 * keyword_score +
        0.35 * semantic_score +
        0.15 * seniority_score +
        0.15 * exp_score
    )
    return final_score
```

**Filtering**: Only pass jobs with `fit_score >= 0.65` to the tailoring stage. Log rejected jobs with reason.

### 6.4 Resume Tailor (RAG-Powered)

**Purpose**: Generate a job-specific resume variant that maximizes ATS match without fabricating facts.

**Architecture**:

```
Base Resume (facts) ----|
                        |---> RAG Retriever ---> LLM Rewriter ---> Tailored Resume
JD Analysis ------------|         ^
                                |
                    ChromaDB (experience library)
```

**ChromaDB Setup**:

```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

client = chromadb.PersistentClient(path="./chroma_db")
embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

collection = client.get_or_create_collection(
    name="experience_bullets",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}
)

# Ingest base resume bullets
for bullet in resume.bullets:
    collection.add(
        documents=[bullet.text],
        metadatas=[{
            "skill_tags": bullet.skills,
            "impact_metric": bullet.metric,
            "company": bullet.company,
            "role": bullet.role
        }],
        ids=[bullet.id]
    )
```

**Retrieval + Rewriting**:

```python
def tailor_resume(resume: ResumeDocument, analysis: JobAnalysis) -> TailoredResume:
    # 1. Retrieve top-K relevant bullets for this JD
    results = collection.query(
        query_texts=[" ".join(analysis.required_skills + analysis.must_have_keywords)],
        n_results=10,
        where={"skill_tags": {"$in": analysis.required_skills}}  # optional filter
    )
    relevant_bullets = results["documents"][0]
  
    # 2. Build prompt with guardrails
    prompt = f"""
    You are a professional resume writer. Rewrite the candidate's resume to maximize 
    alignment with this job description while following these ABSOLUTE RULES:
  
    ABSOLUTE RULES (violating any is a critical failure):
    1. NEVER invent companies, titles, dates, or achievements not in the base resume
    2. NEVER change employment dates or durations
    3. NEVER add skills the candidate does not possess
    4. NEVER claim certifications or degrees not listed
    5. ALWAYS preserve quantified metrics (%, $, headcount, etc.)
    6. If a required skill is missing, do NOT mention it — focus on transferable skills
  
    STYLE GUIDE (from Learning Agent):
    {learned_patterns.style_guide}
  
    JOB REQUIREMENTS:
    {analysis.required_skills}
    {analysis.must_have_keywords}
  
    RELEVANT EXPERIENCE BULLETS (use these as source material):
    {relevant_bullets}
  
    BASE RESUME (facts must be preserved):
    {resume.to_text()}
  
    OUTPUT: A tailored resume in markdown format, ready for PDF conversion.
    """
  
    tailored_text = llm.generate(prompt, temperature=0.3)
    return TailoredResume(text=tailored_text, source_bullets=relevant_bullets)
```

**Guardrails**:

- Post-process validation: extract entities from tailored resume, verify against base resume entities. Reject if new companies/titles/dates appear.
- Human diff view: show "before -> after" side by side for every changed bullet.

### 6.5 Cover Letter Agent

**Purpose**: Generate a short, role-specific cover letter.

**Prompt design**:

```python
def generate_coverletter(resume: ResumeDocument, analysis: JobAnalysis, tailored: TailoredResume) -> str:
    prompt = f"""
    Write a concise cover letter (250-350 words) for this specific role.
  
    RULES:
    1. Reference the company name and role title explicitly
    2. Connect 2-3 specific achievements from the resume to the job requirements
    3. Mention one company value or recent project if known
    4. Do NOT repeat the resume verbatim
    5. End with a clear call to action
    6. Tone: confident but not arrogant
  
    JOB: {analysis.title} at {analysis.company}
    REQUIREMENTS: {analysis.required_skills}
    COMPANY VALUES: {analysis.company_values}
  
    CANDIDATE HIGHLIGHTS:
    {tailored.top_3_bullets}
    """
    return llm.generate(prompt, temperature=0.4)
```

### 6.6 Application Agent (Auto-Fill, NOT Auto-Submit)

**Purpose**: Navigate to the application page and fill the form, stopping before the final submit.

**Implementation with Playwright**:

```python
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def auto_fill_application(job: JobPosting, resume_path: str, coverletter_path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headed = lower detection risk
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
        )
        page = context.new_page()
        stealth_sync(page)  # hide automation fingerprints
      
        page.goto(job.application_url)
      
        # Detect ATS platform (Greenhouse, Lever, Workday, etc.)
        ats_type = detect_ats(page)
      
        if ats_type == "greenhouse":
            fill_greenhouse(page, job, resume_path, coverletter_path)
        elif ats_type == "lever":
            fill_lever(page, job, resume_path, coverletter_path)
        elif ats_type == "linkedin_easy_apply":
            fill_linkedin_easy_apply(page, job, resume_path, coverletter_path)
        # ... etc
      
        # STOP HERE. Do not click submit.
        print("Form filled. Review and click submit manually.")
        input("Press Enter when done...")
      
        browser.close()
```

**ATS Detection heuristics**:

- Greenhouse: URL contains `boards.greenhouse.io`
- Lever: URL contains `jobs.lever.co`
- Workday: URL contains `myworkdayjobs.com`
- LinkedIn Easy Apply: Button with `jobs-search-box__easy-apply` class
- Ashby: URL contains `ashbyhq.com`
- Jobvite: URL contains `jobvite.com`

**Form filling strategy**:

- Use label text matching ("First Name", "Email", "Resume") rather than fragile CSS selectors
- For screening questions, use an LLM to generate answers from your profile + a config-driven "answer bank"
- Upload resume/cover letter via file input
- Log every filled field for debugging

### 6.7 Tracker

**Purpose**: Single source of truth for all applications.

**SQLite schema**:

```sql
CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    job_id TEXT UNIQUE,
    title TEXT,
    company TEXT,
    board TEXT,
    url TEXT,
    applied_at TIMESTAMP,
    status TEXT CHECK(status IN ('draft','submitted','no_response','rejected','phone_screen','interview','offer','declined')),
    fit_score REAL,
    ats_score_before REAL,
    ats_score_after REAL,
    resume_variant_hash TEXT,
    coverletter_hash TEXT,
    tailored_resume_path TEXT,
    coverletter_path TEXT,
    notes TEXT
);

CREATE TABLE outcomes (
    id INTEGER PRIMARY KEY,
    application_id INTEGER,
    outcome_type TEXT,
    occurred_at TIMESTAMP,
    source TEXT,  -- 'email_triage', 'manual_update', 'linkedin_dm'
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

CREATE TABLE learning_patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT,  -- 'keyword', 'phrase', 'structure'
    pattern_value TEXT,
    correlation_score REAL,  -- correlation with interview outcome
    sample_size INTEGER,
    discovered_at TIMESTAMP
);
```

**CLI interface**:

```bash
hermes tracker list --status interview          # show all interviews
hermes tracker stats --days 30                  # response rate last 30 days
hermes tracker update --id 42 --status rejected # manual status update
```

### 6.8 Learning Agent

**Purpose**: Periodically analyze tracker data to find what works.

**Analysis pipeline** (runs weekly via cron):

```python
class LearningAgent:
    def analyze(self) -> LearnedPatterns:
        # 1. Load all applications with outcomes
        apps = self.db.query("""
            SELECT * FROM applications 
            WHERE status IN ('interview', 'offer', 'rejected', 'no_response')
        """)
      
        # 2. Feature extraction from tailored resumes
        features = []
        for app in apps:
            resume_text = load_resume(app.tailored_resume_path)
            features.append({
                'job_id': app.job_id,
                'keywords_used': extract_keywords(resume_text),
                'bullet_structures': extract_structures(resume_text),
                'ats_score_delta': app.ats_score_after - app.ats_score_before,
                'outcome': app.status
            })
      
        # 3. Correlation analysis
        df = pd.DataFrame(features)
      
        # Which keywords appear more in interview-getting resumes?
        interview_resumes = df[df.outcome.isin(['interview', 'offer'])]
        rejected_resumes = df[df.outcome == 'rejected']
      
        winning_keywords = find_overrepresented_keywords(
            interview_resumes.keywords_used,
            rejected_resumes.keywords_used
        )
      
        # Which bullet structures correlate with success?
        winning_structures = find_overrepresented_structures(
            interview_resumes.bullet_structures,
            rejected_resumes.bullet_structures
        )
      
        # Does higher ATS score delta correlate with interviews?
        ats_correlation = df['ats_score_delta'].corr(
            df['outcome'].map({'interview': 1, 'offer': 1, 'rejected': 0, 'no_response': 0})
        )
      
        return LearnedPatterns(
            style_guide=self._generate_style_guide(winning_keywords, winning_structures),
            keyword_priorities=winning_keywords,
            ats_delta_correlation=ats_correlation,
            sample_size=len(apps)
        )
```

**Bootstrap strategy** (before real outcomes accumulate):

- Use ATS score delta as a proxy signal: higher delta = better tailoring
- Use "application-to-view" rate (if trackable via LinkedIn analytics) as early signal
- Use email open/click tracking for outreach campaigns
- Minimum sample size: 30 applications before generating reliable patterns

**Feedback mechanism**:

- Save `learned_patterns.json` to disk
- Inject into Resume Tailor's system prompt as "STYLE GUIDE" section
- Version the style guide so you can roll back if quality degrades

---

## 7. Guardrails, Ethics & Safety

### 7.1 The Hard Guardrails (Non-Negotiable)

1. **No fabrication**: Resume Tailor must pass a post-hoc validation step that checks for invented companies, titles, dates, or skills
2. **No auto-submit**: Application Agent fills forms but stops before the submit button. Human must review and click
3. **No spam**: Rate limiting — max N applications per day per board (configurable, default 20)
4. **No duplicate applications**: Tracker prevents applying to the same job twice
5. **No sensitive data leakage**: All resume data stays local. LLM calls use your own API keys, no intermediary servers

### 7.2 ToS Compliance

- LinkedIn: Automation of Easy Apply is against ToS. Use authenticated browser sessions with realistic delays (5-15s between actions)
- Indeed: Similar restrictions. Consider using JobSpy for discovery only, manual apply for submission
- Greenhouse/Lever: No explicit anti-automation clauses, but be respectful (don't hammer their servers)
- **Mitigation**: Randomized delays, human-like mouse movements (Bezier curves), realistic session duration

### 7.3 Detection Evasion (If Using Auto-Fill)

| Detection Vector             | Mitigation                                                                  |
| ---------------------------- | --------------------------------------------------------------------------- |
| `navigator.webdriver`      | Use`playwright-stealth` or `nodriver`                                   |
| `--enable-automation` flag | Remove via launch args:`--disable-blink-features=AutomationControlled`    |
| Headless mode detection      | Run headed (`headless=False`) with a real user profile                    |
| CAPTCHA                      | Graceful failure — log as "blocked", never fake submission                 |
| Rate limiting                | Exponential backoff, proxy rotation, max 20 apps/day                        |
| Fingerprinting               | Use`invisible_playwright` (C++-patched Firefox) for high-security targets |

### 7.4 Data Privacy

- All data stored locally in SQLite/ChromaDB
- No telemetry, no analytics, no cloud sync (unless user explicitly configures Google Sheets sync)
- Resume text never leaves machine when using Ollama
- When using cloud LLMs, data goes directly to provider (Gemini/OpenRouter) — no intermediary

---

## 8. The Learning Loop

### 8.1 Signal Timeline

```
Day 0:    Application submitted
Day 1-3:  ATS score delta (immediate proxy)
Day 3-7:  Email triage (rejection or interview invite)
Day 7-14: Phone screen scheduled
Day 14-30: Interview rounds
Day 30+:  Offer or final rejection
```

### 8.2 Learning Signals (in order of reliability)

| Signal              | Reliability | Latency   | How to Capture                                 |
| ------------------- | ----------- | --------- | ---------------------------------------------- |
| ATS score delta     | Low (proxy) | Immediate | Compute before/after tailoring                 |
| Email response      | Medium      | 3-7 days  | Triage inbox for "interview" / "unfortunately" |
| Interview scheduled | High        | 7-14 days | Manual update or calendar scan                 |
| Offer received      | Very High   | 30+ days  | Manual update                                  |

### 8.3 The Feedback Cycle

```
1. Collect 30+ applications with outcomes
2. Run Learning Agent analysis
3. Generate "winning patterns" report
4. Update Resume Tailor's STYLE GUIDE prompt
5. A/B test new style vs old style for next 30 applications
6. Measure if interview rate improves
7. Repeat
```

### 8.4 A/B Testing Framework

```python
# Randomly assign variant A or B to each job
variant = "A" if random.random() < 0.5 else "B"

if variant == "A":
    style_guide = current_patterns.style_guide
else:
    style_guide = experimental_patterns.style_guide  # test new hypothesis

# Track outcome by variant
# After N samples, chi-squared test for significance
```

---

## 9. Project File Structure

```
hermes/
├── README.md
├── LICENSE (MIT)
├── pyproject.toml
├── docker-compose.yml
├── config/
│   ├── profile.yml              # Your name, contact, target roles, preferences
│   ├── search_configs.yml       # Job search parameters per role type
│   ├── answer_bank.yml          # Pre-written answers to common screening questions
│   └── llm_config.yml           # API keys, model selection, failover rules
├── data/
│   ├── hermes.db                # SQLite tracker (gitignored)
│   ├── chroma_db/               # ChromaDB vector store (gitignored)
│   ├── base_resume.md           # Your canonical resume in markdown
│   ├── base_resume.pdf          # Original PDF
│   └── applications/            # Tailored resumes + cover letters (gitignored)
├── hermes/
│   ├── __init__.py
│   ├── cli.py                   # Click/Typer CLI entry point
│   ├── config.py                # Pydantic settings loader
│   ├── state.py                 # LangGraph state schema
│   ├── graph.py                 # LangGraph node definitions + edges
│   ├── orchestrator.py          # Main pipeline runner
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── job_scout.py         # JobSpy integration
│   │   ├── jd_analyzer.py       # LLM-based JD parsing
│   │   ├── fit_scorer.py        # Matching algorithm
│   │   ├── resume_tailor.py     # RAG + LLM resume rewriting
│   │   ├── cover_letter.py      # Cover letter generation
│   │   ├── application_agent.py # Playwright form filling
│   │   ├── tracker.py           # SQLite CRUD + queries
│   │   └── learning_agent.py    # Pattern analysis + feedback
│   ├── models/
│   │   ├── __init__.py
│   │   ├── resume.py            # ResumeDocument, Bullet, etc.
│   │   ├── job.py               # JobPosting, JobAnalysis, etc.
│   │   └── application.py       # ApplicationRecord, Outcome, etc.
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── llm_router.py        # LiteLLM wrapper with failover
│   │   ├── embeddings.py        # SentenceTransformer wrapper
│   │   ├── pdf_generator.py     # WeasyPrint HTML->PDF
│   │   ├── resume_parser.py     # pdfplumber + pyresparser
│   │   ├── ats_scorer.py        # Keyword match + vector similarity
│   │   ├── deduplicator.py      # Fuzzy job deduplication
│   │   └── stealth_browser.py   # Playwright + stealth setup
│   └── prompts/
│       ├── jd_analyzer.txt
│       ├── resume_tailor.txt
│       ├── cover_letter.txt
│       ├── screening_qa.txt
│       └── style_guide.txt      # Updated by Learning Agent
├── scripts/
│   ├── setup.sh                 # One-command setup
│   ├── daily_run.sh             # Cron-friendly wrapper
│   └── email_triage.py          # Optional: Gmail/Outlook scanner
├── tests/
│   ├── test_scout.py
│   ├── test_tailor.py
│   ├── test_guardrails.py       # Fabrication detection tests
│   └── test_learning.py
└── docs/
    ├── ARCHITECTURE.md
    ├── SETUP.md
    ├── GUARDRAILS.md
    └── LEARNING.md
```

---

## 10. Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Playwright browser automation)
- Chrome/Chromium (auto-detected)
- Git

### Step 1: Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/hermes.git
cd hermes
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
```

### Step 2: Configure

```bash
cp config/profile.example.yml config/profile.yml
# Edit profile.yml with your details

cp config/llm_config.example.yml config/llm_config.yml
# Add your free API keys (Gemini, OpenRouter, etc.)
# Or set OLLAMA_URL for fully local mode
```

### Step 3: Add Your Resume

```bash
# Place your base resume in data/base_resume.md (markdown format)
# Or use: hermes parse-resume data/my_resume.pdf
```

### Step 4: Index Your Experience (RAG)

```bash
hermes index-resume
# Parses bullets, embeds them into ChromaDB
```

### Step 5: Run the Pipeline

```bash
# Discovery + analysis + tailoring only (recommended for first run)
hermes run --mode draft

# With auto-fill (opens browser, fills forms, stops at submit)
hermes run --mode fill

# Dry-run (no browser, just log what would happen)
hermes run --mode dry-run
```

### Step 6: Review & Submit

```bash
hermes dashboard
# Opens terminal UI showing today's queue
# Review each tailored resume, approve or reject
```

### Step 7: Track Outcomes

```bash
# After you hear back from employers:
hermes tracker update --company "Stripe" --status interview

# Or run email triage (optional):
python scripts/email_triage.py
```

### Step 8: Learn

```bash
# After 30+ applications:
hermes learn
# Generates style guide update + winning patterns report
```

---

## 11. References & Repositories

### Core Dependencies

| Tool                  | Repo / URL                                   | License     |
| --------------------- | -------------------------------------------- | ----------- |
| LangGraph             | `github.com/langchain-ai/langgraph`        | MIT         |
| JobSpy                | `github.com/speedyapply/JobSpy`            | MIT         |
| ChromaDB              | `github.com/chroma-core/chroma`            | Apache 2.0  |
| LiteLLM               | `github.com/BerriAI/litellm`               | MIT         |
| Playwright            | `github.com/microsoft/playwright`          | Apache 2.0  |
| playwright-stealth    | `github.com/AtuboDad/playwright_stealth`   | MIT         |
| nodriver              | `github.com/ultrafunkamsterdam/nodriver`   | AGPL        |
| invisible_playwright  | `github.com/feder-cr/invisible_playwright` | Open Source |
| Ollama                | `github.com/ollama/ollama`                 | MIT         |
| sentence-transformers | `github.com/UKPLab/sentence-transformers`  | Apache 2.0  |
| WeasyPrint            | `github.com/Kozea/WeasyPrint`              | BSD         |
| pdfplumber            | `github.com/jsvine/pdfplumber`             | MIT         |
| pyresparser           | `github.com/OmkarPathak/pyresparser`       | GPL v3      |
| Resume Matcher        | `github.com/srbhr/Resume-Matcher`          | Apache 2.0  |
| Rich                  | `github.com/Textualize/rich`               | MIT         |
| Textual               | `github.com/Textualize/textual`            | MIT         |

### Inspiration Projects

| Project               | Repo                                                 | Key Takeaway                                               |
| --------------------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| Career-Ops            | `github.com/santifer/career-ops`                   | Human-in-the-loop, CLI-agnostic, CareerOps Manifesto       |
| ApplyPilot            | `github.com/Pickle-Pixel/ApplyPilot`               | 6-stage pipeline, dry-run mode, Gemini free tier           |
| AIHawk                | `github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk` | Engine-level stealth via invisible_playwright              |
| Jobber                | `github.com/sentient-engineering/jobber`           | Browser-control approach, real user sessions               |
| ai-job-agent          | `github.com/AkbarDevop/ai-job-agent`               | 13 Claude Code skills, 5-tab TUI dashboard, 228+ real apps |
| ApplyKit              | `github.com/wihlarkop/applykit`                    | Self-hosted, BYOK, Docker one-command, SvelteKit+FastAPI   |
| Resume Matcher        | `github.com/srbhr/Resume-Matcher`                  | Vector similarity ATS scoring, Qdrant-based                |
| LinkedIn Auto Applier | `github.com/GodsScion/Auto_job_applier_linkedIn`   | Flask control panel, 100+ jobs/hour                        |
| ai-job-search         | `github.com/MadsLorentzen/ai-job-search`           | 38K stars Claude Code skill, fork-and-own model            |
| CoverLetterMaker      | `github.com/stanleyume/coverlettermaker`           | Local LLM cover letters, Ollama-powered                    |

### Free LLM API References

| Provider   | Free Tier                      | URL                 |
| ---------- | ------------------------------ | ------------------- |
| Gemini     | 1M tokens/day, 15 RPM          | aistudio.google.com |
| OpenRouter | 28 free models, 20 RPM, 50/day | openrouter.ai       |
| NVIDIA NIM | 120+ models, ~40 req/min       | build.nvidia.com    |
| Groq       | Llama/Qwen, 30 req/min         | groq.com            |
| Ollama     | Unlimited, local only          | ollama.ai           |

---

## Appendix: The "Hermes" Name

Hermes, the Greek messenger god, was the patron of boundaries, commerce, and cunning. He guided souls to the underworld — and in our case, guides your application through the labyrinth of ATS systems to the hiring manager's inbox. The name also nods to the "hermeneutic circle": understanding the part through the whole, and the whole through the part — exactly what the Learning Agent does with resume patterns and outcomes.

---

*Document generated September 2026. All tools and APIs referenced offer genuine free tiers as of this date. Rate limits and terms change — verify before deploying.*
