# ApplyJin Tutorial — Complete Guide

A step-by-step guide to running ApplyJin locally, from zero to tailored resumes.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Backend Setup](#3-backend-setup)
4. [Frontend Setup](#4-frontend-setup)
5. [Building Your Master CV](#5-building-your-master-cv)
6. [Uploading Resumes](#6-uploading-resumes)
7. [Adding Job Descriptions](#7-adding-job-descriptions)
8. [Tailoring a Resume](#8-tailoring-a-resume)
9. [Understanding the Fit Score](#9-understanding-the-fit-score)
10. [Pipeline Management](#10-pipeline-management)
11. [LinkedIn Profile Generator](#11-linkedin-profile-generator)
12. [Research Panel (Visa + Salary)](#12-research-panel-visa--salary)
13. [RAG Chat Copilot](#13-rag-chat-copilot)
14. [Chrome Extension](#14-chrome-extension)
15. [CLI Commands](#15-cli-commands)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Prerequisites

You need:
- **Python 3.11+** — check with `python3 --version`
- **Node.js 18+** — check with `node --version`
- **Git** — check with `git --version`
- **A free Gemini API key** — optional but recommended (get one at [aistudio.google.com](https://aistudio.google.com))

Optional:
- **LaTeX** (`pdflatex`) — for professional PDF generation (install `texlive-full` or `texlive-base`)
- **Playwright** — for browser-based PDF fallback and auto-fill

---

## 2. Installation

```bash
# Clone the repo
git clone https://github.com/shamiquekhan/ApplyJin.git
cd ApplyJin

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -e ".[all,dev]"

# Install Playwright browser (for PDF fallback + auto-fill)
python -m playwright install chromium
```

---

## 3. Backend Setup

### 3a. Add your API key

```bash
echo "GEMINI_API_KEY=your-key-here" > .env
```

Or skip this — the agent runs in heuristic mode without an LLM key.

### 3b. Start the backend

```bash
hermes serve
# → http://127.0.0.1:8000
```

Or directly:

```bash
python -m uvicorn hermes.web.app:app --host 0.0.0.0 --port 8000 --reload
```

The backend is now running. You can test it:

```bash
curl http://localhost:8000/api/master/stats
```

### 3c. Add API keys from the UI (optional)

Instead of editing `.env`, you can add keys from the Console:
1. Open the Console
2. Click the **Settings** tab
3. Paste your Gemini, Groq, or Ollama key
4. Click **Save**

Keys are saved to `config/llm_config.yml` and redacted in API responses.

---

## 4. Frontend Setup

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

Open **http://localhost:3000** in your browser.

- The landing page loads at `/`
- The Console loads at `/dashboard`

No Google OAuth is required locally — the Console runs in open-access mode.

---

## 5. Building Your Master CV

The Master CV is the foundation of everything. It's a structured database of your career — not a static resume. Every tailored resume is built from this data.

### 5a. Via the CLI

```bash
# Import an existing resume (PDF, DOCX, or Markdown)
hermes index-resume path/to/your-resume.pdf
```

This parses the resume and adds entries to the Master CV database.

### 5b. Via the Console

1. Open the Console → **Master CV** tab
2. Fill in your **Profile** (name, headline, email, phone, location, LinkedIn, GitHub)
3. Add **Experiences** — each with title, organization, dates, location, and bullet points
4. Add **Projects** — each with name, dates, URLs, and bullet points
5. Add **Skills** — organized by category (languages, frameworks, tools, etc.)
6. Add **Education** — school, degree, dates
7. Add **Certifications** — name, issuer, date

### 5c. What to include

- **Every job** you've held (even short ones)
- **Every project** you've built (personal, open-source, work)
- **Every skill** you can demonstrate with evidence
- **Every certification** you hold
- Be specific: "Reduced API latency by 40% by implementing Redis caching" is better than "Improved performance"

The selection engine ranks these entries against each job description, so more data = better tailoring.

---

## 6. Uploading Resumes

Resumes in ApplyJin are the **output** — tailored documents generated from your Master CV. But you can also upload existing resumes for reference.

### Via the Console

1. Go to the **Resumes** tab
2. Click **Upload resume**
3. Select a PDF, DOCX, or Markdown file
4. The resume is parsed and stored

### Via the CLI

```bash
hermes index-resume path/to/resume.pdf
```

---

## 7. Adding Job Descriptions

### Via the Console

1. Go to the **Job descriptions** tab
2. Paste the full job description text
3. Add the job title, company name, and URL (optional)
4. Click **Add JD**

The system will:
- Auto-analyze the JD (extract skills, seniority, requirements)
- Run ghost-job scoring (0–100 genuineness score)
- Show you the analysis results

### Via the CLI

```bash
# Scrape jobs from boards
hermes scout --ats stripe,anthropic

# Or manually add a JD
hermes add-jd --title "Software Engineer" --company "Acme" --url "https://..."
```

### Ghost-job score

Every JD gets a genuineness score (0–100):
- **80–100**: Likely genuine, active listing
- **50–79**: Probably real, but check details
- **Below 50**: Suspicious — vague requirements, buzzwords, templated language

---

## 8. Tailoring a Resume

This is the core of ApplyJin.

### Via the Console

1. Go to the **Tailor & score** tab
2. Select a **resume** from the left panel
3. Select a **job description** from the right panel
4. Click **Tailor resume**

What happens:
1. The **selection engine** picks the best 3 experiences + 3 projects from your Master CV
2. **Tailor v3** composes an ATS-friendly resume using only selected facts
3. **Guardrails** validate the output — no fabricated companies, dates, or skills
4. You see the **fit score** decomposed into keyword/semantic/seniority/experience bars
5. You can **download** the tailored resume as PDF (LaTeX) or Markdown

### Via the CLI

```bash
# Tailor a resume for a specific JD
hermes tailor --jd-id 1 --resume-id 1

# Export as PDF
hermes export --id 1
```

---

## 9. Understanding the Fit Score

The fit score is decomposed into four weighted components:

| Component | Weight | What it measures |
|---|---|---|
| Keyword overlap | 0.35 | Exact keyword matches between your resume and the JD |
| Semantic similarity | 0.35 | Meaning-level alignment (not just exact words) |
| Seniority match | 0.15 | Does your level match what they want? |
| Experience depth | 0.15 | How many relevant entries did you include? |

### Per-category breakdown

The score further breaks down into skill categories:
- **Hard skills** — programming languages, frameworks
- **Tools** — databases, cloud platforms, dev tools
- **Soft skills** — leadership, communication, teamwork
- **Certifications** — AWS, GCP, etc.
- **Domain keywords** — industry-specific terms

Each category shows a coverage bar (green ≥70%, amber ≥40%, red <40%) and lists matched vs missing keywords.

---

## 10. Pipeline Management

The Kanban board tracks your applications through the hiring pipeline.

### Pipeline statuses

| Status | Meaning |
|---|---|
| **Saved** | JD added, not yet tailored |
| **Tailored** | Resume tailored, ready to apply |
| **Applied** | Application submitted |
| **Interviewing** | Got an interview |
| **Offer** | Received an offer |
| **Rejected** | Application rejected |
| **Ghosted** | No response after 2+ weeks |

### Moving cards

1. Go to the **Pipeline** tab
2. Click any card to expand it
3. Click the status you want to move it to
4. The card moves to the new column

---

## 11. LinkedIn Profile Generator

Generate keyword-rich LinkedIn copy from your Master CV.

### Via the Console

1. Go to the **LinkedIn** tab
2. Click **Generate from Master CV**
3. Review the generated headline (max 220 chars) and About section (max 2600 chars)
4. Click **Copy** to copy to clipboard
5. Paste into LinkedIn

The generator uses your Master CV data — no fabricated facts.

---

## 12. Research Panel (Visa + Salary)

### Visa sponsorship lookup

1. Go to the **Research** tab
2. Enter a company name
3. Click **Visa lookup**

The system checks:
- Known sponsor database (200+ tech companies)
- JD text for visa-related keywords
- User-override cache (you can mark employers manually)

Results: yes / likely_yes / no / likely_no / unknown — with confidence score and evidence.

### Salary insights

1. Enter a job title and location
2. Click **Salary lookup**

The system returns:
- Min / median / max salary range
- Source (BLS data, Adzuna API, or heuristic estimate)
- Location cost-of-living adjustment

---

## 13. RAG Chat Copilot

The copilot answers questions about any tailored match, grounded in your actual data.

### Via the Console

1. Go to the **Tailor & score** tab
2. Select an application from the list
3. The copilot panel appears on the right
4. Type a question, e.g.:
   - "Why was this experience selected?"
   - "What keywords am I missing?"
   - "How can I improve this resume?"
   - "Summarize this match"

The copilot uses:
- Your Master CV snapshot
- ChromaDB experience retrieval (top-8 relevant bullets)
- The job description
- The tailored resume
- Fabrication guardrails (same as Tailor v3)

Chat history is saved per application.

---

## 14. Chrome Extension

### Installation

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repo
5. Pin the extension to your toolbar

### Setup

1. Click the extension icon
2. Go to **Settings** tab
3. Enter your backend URL: `http://localhost:8000`
4. (Optional) Paste your JWT auth token from the dashboard
5. Click **Save settings**

### Autofill

1. Navigate to any job application form
2. Click the extension icon
3. The **Autofill** tab shows detected fields
4. Click **Fill all fields** to auto-fill with your resume data

### Extract JD

1. Navigate to a job posting page
2. Click the extension icon
3. Go to the **Extract JD** tab
4. Click **Extract JD from page**
5. Review the extracted title, company, and description
6. Click **Score this JD** to run ghost scoring via the backend

Supported job boards: LinkedIn, Greenhouse, Lever, Workday, iCIMS, and generic sites.

---

## 15. CLI Commands

```bash
# Full pipeline (scout → analyze → score → tailor → track)
hermes run

# Scout for jobs on specific ATS boards
hermes scout --ats stripe,anthropic

# Index a resume into the Master CV database
hermes index-resume path/to/resume.pdf

# Tailor a resume for a specific JD
hermes tailor --jd-id 1 --resume-id 1

# Export as PDF
hermes export --id 1

# Review applications (approve/reject)
hermes review

# Auto-fill a form (never auto-submits)
hermes fill --id 1

# Generate interview prep
hermes prep --id 1

# Generate outreach (LinkedIn notes, follow-up emails)
hermes outreach --id 1

# Analyze outcomes and update learning loop
hermes learn --apply

# Triage email outcomes
hermes triage-email --apply

# Start the web dashboard
hermes dashboard          # TUI
hermes serve              # Web API
```

---

## 16. Troubleshooting

### "No module named hermes"

```bash
pip install -e ".[all,dev]"
```

### "No Gemini API key"

The agent runs in heuristic mode. You'll see a warning in the Console but the full pipeline works. Add a key via Settings tab or `.env` file.

### Backend won't start

Check if port 8000 is in use:

```bash
lsof -ti:8000 | xargs kill -9
```

Then restart.

### Frontend can't connect to backend

Make sure the backend is running on port 8000. The Vite dev server proxies API calls automatically.

### LaTeX PDF generation fails

Install LaTeX:

```bash
# Ubuntu/Debian
sudo apt install texlive-full

# macOS
brew install --cask mactex

# Or use the Playwright fallback (automatic)
```

### Chrome extension can't detect fields

Some job boards use shadow DOM or iframes. The extension works best on:
- Greenhouse (`boards.greenhouse.io`)
- Lever (`jobs.lever.co`)
- Workday (`*.myworkdayjobs.com`)
- LinkedIn (`linkedin.com/jobs`)
- Generic application forms

### "Ghost score is low"

That's the point — it's warning you the listing might be fake or recycled. Review the flags and decide whether to apply.

---

## Quick Reference

| Task | Where |
|---|---|
| Add your career data | Master CV tab |
| Upload an existing resume | Resumes tab |
| Add a job to apply to | Job descriptions tab |
| Generate a tailored resume | Tailor & score tab |
| Track your applications | Pipeline tab |
| Generate LinkedIn copy | LinkedIn tab |
| Look up visa/salary data | Research tab |
| Chat about a match | Tailor & score → copilot panel |
| Auto-fill a form | Chrome extension |
| Run the full pipeline | `hermes run` |

---

<div align="center">

Made by [Shamique Khan](https://github.com/shamiquekhan)

</div>
