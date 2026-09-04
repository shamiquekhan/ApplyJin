# Setup

## 1. Install

```bash
git clone <your-fork> hermes && cd hermes
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
python -m playwright install chromium   # auto-fill + PDF
```

Minimal install (no scraping/browser): `pip install -e ".[web]"` etc. —
see pyproject extras: `scrape`, `rag`, `pdf`, `browser`, `web`, `all`.

## 2. Configure

```bash
cp config/profile.example.yml config/profile.yml
cp config/llm_config.example.yml config/llm_config.yml
cp config/search_configs.example.yml config/search_configs.yml
```

- `profile.yml` — identity, skills (facts only), preferences, limits
- `llm_config.yml` — provider chain; or env vars `GEMINI_API_KEY`,
  `OPENROUTER_API_KEY`, `GROQ_API_KEY`, ...
- Free keys: Google AI Studio (1M tok/day), OpenRouter (free models),
  NVIDIA NIM, Groq. Zero-key runs work in heuristic mode.

## 3. Add your resume

```bash
cp /path/to/your_resume.docx data/base_resume.docx   # docx/pdf/md all work
hermes index-resume            # RAG-index bullets into ChromaDB
```

## 4. First run

```bash
hermes run --offline           # sample jobs, full pipeline, zero risk
hermes review                  # approve/reject each tailored application
hermes run --title "AI Engineer" --location "Remote"   # live
```

## 5. Daily/weekly rhythm

```bash
hermes run                     # morning scan -> tailored queue
hermes review                  # coffee-time review, approve, submit via fill
hermes fill --id 42            # opens form, fills, you click submit
hermes tracker update --id 42 --status submitted
hermes triage-email --apply    # pull outcomes from inbox
hermes learn --apply           # weekly: refresh style guide
hermes dashboard               # anytime: funnel + follow-ups + A/B
```

Cron: `scripts/daily_run.sh` (2×/day), `scripts/learn_weekly.sh` (Mon).

## 6. Optional extras

- Web dashboard: `hermes serve` → http://127.0.0.1:8000
- Multi-profile: `hermes --profile ml-research run`
- ATS boards directly: `hermes scout --ts stripe,anthropic` —
  Greenhouse/Lever public JSON APIs, no scraping
- Demo the learning loop: `python scripts/seed_demo_data.py --wipe && hermes learn`

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No LLM configured" | Add a key to llm_config.yml or env — heuristic mode still works |
| WeasyPrint import error | Playwright PDF used instead; install libpango for WeasyPrint |
| Ollama connection refused | Start ollama or remove it from the chain |
| Duplicate job blocked | Intended — never apply twice |
| Daily limit reached | Raise `limits.max_applications_per_day` |
