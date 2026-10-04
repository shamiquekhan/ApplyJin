# ApplyJin — Product Scope (frozen)

This document fixes what ApplyJin **is**, what it **is not**, and the rules
for any public claim it makes. New features must fit inside this scope or
change this document deliberately (scope changes are a review event, not a
drift).

Related: `docs/GUARDRAILS.md` (non-negotiable invariants),
`docs/ARCHITECTURE.md` (system shape), `SECURITY.md` (threat model +
reporting).

## What ApplyJin is

A local-first, single-operator job-application workbench. It automates
preparation and administration; a human makes every decision that touches
the outside world.

**In scope (implemented):**

| Capability | Status |
|---|---|
| Master CV database — structured career record (experiences, projects, education, certifications, skills) imported from a resume, never invented | shipped |
| JD ingestion + keyword extraction (LLM with heuristic fallback) | shipped |
| Grounded resume tailoring: requirements → plan → compose → validate → one-page gate with physical PDF QA and automatic repair | shipped |
| Fit scoring: keyword overlap, semantic similarity, requirement coverage — all heuristics | shipped |
| Copilot chat over an application (LLM, same guardrails as the tailor) | shipped |
| Pipeline tracker (saved → tailored → applied → interview → offer/reject) | shipped |
| Cover letter, cold-email, and LinkedIn note drafts from the master record | shipped |
| LaTeX/PDF export with one-page and ATS-parsability checks | shipped |
| Application auto-fill via Playwright — fills fields, then stops (CLI) | shipped |
| Job discovery through public ATS board APIs (Greenhouse/Lever etc.) | shipped |
| Outcome learning: IMAP triage + weekly style-guide promotion (opt-in, dry-run by default) | shipped |
| Interview-prep and outreach drafts from the master record | shipped |
| Research mode: swap the generation backend for a local vLLM server | experimental |
| Evaluation harness (`evaluation/`) for grounding and claim fidelity | in progress |

## What ApplyJin is not

- **Never auto-submits.** Filling is code; submitting is a human click.
  This is a guardrail, not a setting.
- **Never fabricates.** Generated material is selected from, and traceable
  to, the user's own record. Validation rejects invented dates, companies,
  and skills.
- **Makes no hiring-outcome claims.** No guarantee of interviews, ATS
  passage, callbacks, or offers — none is possible to make honestly.
- **Not a scraper.** Discovery uses public ATS board APIs only; direct
  scraping of LinkedIn/Indeed is out of scope (ToS risk).
- **Not multi-tenant SaaS.** Per-user data isolation exists to protect one
  operator's data across accounts on one deployment — there are no
  organizations, teams, or sharing features.
- **Not hosted by default.** Local-first: data lives in `data/` on the
  user's machine. A deployment is the operator's responsibility.
- **Not commercially re-licensable.** CC BY-NC 4.0 — commercial use
  requires a separate license.
- **Not an ATS, and not a resume "writer."** Scores are heuristics for the
  user's own comparison; the product does not score candidates for others.

## Honest-claims policy

1. Every product claim in README, docs, or UI must map to a test in
   `tests/` or an artifact in `evaluation/`. Claims without a source are
   removed, not softened.
2. Scores are labeled for what they are (keyword overlap, semantic
   similarity, coverage). Any metric presented as predictive of hiring
   outcomes is prohibited.
3. The physical one-page guarantee is stated precisely: the rendered PDF
   is verified page-count 1 by the QA loop, not "optimized" or
   "ATS-friendly."
4. Test counts in badges are refreshed at release time, never by hand.
5. Evaluation results are reported with dataset, date, and configuration —
   no cherry-picked runs.

## Scope-change rule

Anything not listed above (teams, mobile apps, hosted SaaS, job-board
scraping, auto-apply, commercial licensing, new LLM providers beyond what
`config/llm_config.yml` already abstracts) requires amending this file in
its own commit with rationale.
