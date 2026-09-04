# Guardrails

Hermes automates preparation, never misrepresentation. These are
non-negotiable invariants enforced in code and tested in
`tests/test_phase1.py::TestTailorGuardrails` and beyond.

## 1. No fabrication

- The tailor prompt carries ABSOLUTE RULES: never invent companies,
  titles, dates, achievements, skills, or certifications.
- Post-hoc validation (`validate_tailored`) checks every tailored resume:
  - dates outside the base resume → violation
  - JD-required skills the candidate lacks but that appear anyway → violation
  - floods of new capitalized entities → violation
- Violations are logged on the tracker record (`notes: GUARDRAIL:`) and the
  resume is marked `validated=False` for the human reviewer.
- RAG retrieval only ever returns bullets from the base resume.

## 2. No auto-submit

- `ApplicationAgent.fill` fills fields and uploads files, then **stops**.
  The submit button is never clicked by Hermes — the human does it in the
  open (headed) browser window.
- `hermes fill --dry-run` opens the page without filling anything.
- The web dashboard is 100% read-only; all mutations go through CLI
  commands the human runs.

## 3. Rate limits

- `limits.max_applications_per_day` (default 20) enforced in
  `Tracker.add_application` — over-limit adds are blocked, not queued.
- Recommended board etiquette: JobSpy discovery is read-only; direct
  scraping of LinkedIn/Indeed is their ToS risk — prefer the ATS board
  APIs (`hermes scout --ats company`) which are public JSON endpoints.

## 4. No duplicates

- `job_id` is UNIQUE in SQLite; re-applying to the same job is blocked
  ("Duplicate: job X already tracked").
- Cross-board duplicates deduplicated at discovery via fuzzy
  (company, title) matching.

## 5. Privacy

- All data local: SQLite, ChromaDB, files under `data/`.
- Real configs are gitignored (`profile.yml`, `llm_config.yml`,
  `email_config.yml`).
- LLM calls go directly to the provider you configure. No telemetry.
- Ollama mode keeps resume text fully on-machine.
- Email triage uses IMAP with an app password stored only in the
  gitignored config; it reads only, never sends.

## 6. Outreach is draft-only

- `hermes outreach` writes LinkedIn notes (≤300 chars) and follow-up
  emails to files. Hermes never sends any message.
- Follow-up drafting requires the human to decide to send.

## Detection ethics

`hermes fill` runs headed Chromium with automation flags stripped and
realistic delays — the goal is a *human reviewing a pre-filled form*, not
evasion for mass application. CAPTCHAs → log "blocked", never fake.
