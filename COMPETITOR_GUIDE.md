# ApplyJin: Grounded Feature Guide & Honest Assessment

A realistic look at what ApplyJin already has, what's genuinely missing, what's
broken, and what from the competitor landscape is actually worth building — based
on reading the real code, not the README.

**Last updated:** Sep 2026  
**Status:** Phases 1–8 complete. 164 tests passing. 40+ REST endpoints.

---

## What ApplyJin already has (verified against source)

| Feature | Status | Where it lives |
|---|---|---|
| Job Scout (8+ boards via JobSpy) | Done | `hermes/agents/job_scout.py` |
| JD Analyzer (LLM + heuristic fallback) | Done | `hermes/agents/jd_analyzer.py` |
| Fit Scorer (4-component weighted) | Done | `hermes/agents/fit_scorer.py` |
| Ghost-job scoring (0–100 heuristic) | Done | `hermes/utils/ghost_score.py` |
| Selection engine (keyword + semantic ranking) | Done | `hermes/web/selection.py` |
| Tailor v3 (LLM + guardrails) | Done | `hermes/web/tailor_v3.py` |
| Master CV Database (SQLite) | Done | `hermes/web/master_store.py` |
| Fuzzy deduplication (RapidFuzz) | Done | `hermes/utils/deduplicator.py` |
| A/B learning loop + chi-squared | Done | `hermes/agents/learning_agent.py` |
| Email triage (IMAP) | Done | `hermes/agents/email_triage.py` |
| LaTeX PDF export | Done | `hermes/utils/latex_generator.py` |
| Stealth Playwright auto-fill | Done | `hermes/utils/stealth_browser.py` |
| RAG chat copilot | Done | `hermes/web/app.py:1047` |
| Kanban pipeline (7 statuses) | Done | `hermes/web/store.py` + `KanbanBoard.tsx` |
| LinkedIn headline/About generator | Done | `hermes/web/app.py:1207` |
| Visa sponsorship lookup | Done | `hermes/utils/visa_sponsorship.py` |
| Salary insights (BLS + Adzuna) | Done (buggy) | `hermes/utils/salary_insights.py` |
| Chrome extension (Manifest V3) | Done | `extension/` directory |
| Google OAuth + JWT auth | Done | `hermes/web/auth.py` |
| 9-tab Console (React) | Done | `frontend/src/components/Console.tsx` |

---

## Bugs found (real, not hypothetical)

### 1. `salary_insights.py` — location matching is broken

The `_LOCATION_MULTIPLIER` dict uses substring matching, which causes false
matches. "Dallas, TX" matches "la" (from "la" in the dict, value 1.37) instead
of the intended "dallas" (1.02).

```python
# Current code (broken):
for city, mult in _LOCATION_MULTIPLIER.items():
    if city in loc_lower:  # "la" in "dallas, tx" → True!
        loc_mult = mult
        break
```

**Fix:** Sort keys by length (longest first) so "los angeles" matches before
"la", or use exact word-boundary matching.

### 2. `salary_insights.py` — level detection doesn't work for BLS path

`_detect_level()` returns "junior"/"mid"/"senior"/"executive" but
`get_salary_insights()` only applies the level multiplier in the
`_heuristic_salary()` fallback path. When the BLS path is used (which is the
most common path for tech roles), the level multiplier is never applied. A
"Senior Software Engineer" and "Junior Software Engineer" get the same salary.

### 3. `selection.py:54` — wrong variable in summary

```python
lines.append(f"  prj: {p.title} (score {e.score:.2f} | {kws})")
#                                        ^ should be p.score, not e.score
```

This is a copy-paste bug in the `summary_lines()` method. It displays the last
experience's score for every project instead of the project's own score.

---

## What's genuinely worth adding

These are features that address real gaps in the current product, using only
free resources already in the stack or genuinely free public data.

### 1. Fix the salary bugs (2 hours)

**Priority:** High — this is broken right now.

The location matching and level detection fixes are straightforward. Sort dict
keys by length, apply level multiplier in the BLS path, fix the `e.score`
typo. Three changes, all in existing files.

### 2. RSS/Atom job feed monitoring (1 day)

**What it is:** Subscribe to RSS feeds from company career pages and job boards.
New postings are checked hourly, scored against your profile, and surfaced in
the Console.

**Why it matters:** Right now you have to manually paste JDs or run
`hermes scout`. RSS monitoring catches new postings automatically — the one
thing that makes Jobright's "smart matching" feel alive.

**How it works:**
- `feedparser` (free, mature) parses RSS/Atom feeds
- New entries are scored using the existing `score_pair()` in `pipeline.py`
- Add a `web_rss_feeds` table (url, last_check, enabled)
- Add a `/api/rss/check` endpoint that runs the check
- Surface new matches in the Console with a badge

**Honest assessment:** Most company career pages don't have RSS feeds. Job
boards sometimes do but throttle or remove them. This works for ~30% of target
companies. Better than nothing, not a silver bullet.

### 3. Enhanced contact extraction (1 day)

**What it is:** Extract recruiter/hiring manager names and emails from JD text
using regex patterns and LLM extraction.

**Why it matters:** Jobright's "Insider Connections" is their moat, but it
relies on LinkedIn account data access (ToS gray area). A simpler version that
just parses the JD text for contact info is safe, legal, and useful.

**How it works:**
- Regex patterns for email addresses, phone numbers, LinkedIn URLs in JD text
- LLM extraction for "Contact: Jane Doe, Senior Recruiter" patterns
- Store in `web_jds.contacts_json` (already has a column for this)
- Surface in the Console JD view

**Honest coverage:** Most JDs don't contain direct contact info. Maybe 10–20%
have an email or recruiter name. Useful when it works, not a core feature.

### 4. Application status auto-detection from email (2 days)

**What it is:** Enhance the existing email triage agent to automatically move
applications through the pipeline based on email content.

**Why it matters:** The email_triage agent already classifies emails but doesn't
update the pipeline status. This closes the loop — when you get an interview
invitation email, the application card moves to "Interviewing" automatically.

**How it works:**
- Email triage already detects offer/interview/rejection categories
- Add a pipeline update call: `store.update_pipeline_status(app_id, "interviewing")`
- Match emails to applications by company name (fuzzy, already exists in
  `deduplicator.py`)
- Surface auto-movements in the Console with a "auto-updated from email" badge

**Honest assessment:** Fuzzy company matching works maybe 80% of the time. The
other 20% you'll need to move cards manually. Still a big time saver.

### 5. Salary comparison across applications (half day)

**What it is:** When viewing the pipeline, show salary ranges for each
application so you can compare offers.

**Why it matters:** This is purely a display feature — the salary data is
already fetched via `get_salary_insights()`. Just show it on the pipeline cards.

**How it works:**
- Store `salary_min`, `salary_max` in `web_applications` when the application
  is created
- Display on KanbanBoard cards
- Sort by salary in the Applications table

---

## What's NOT worth building (honest assessment)

### 1. Chrome extension selector maintenance

The extension works for a few sites but maintaining selectors across
Greenhouse, Lever, Workday, iCIMS, and generic forms is a standing cost, not a
one-time build. Simplify is an entire company built around this. The current
extension is fine as a best-effort tool — don't sink time into making it
perfect.

### 2. Referral-lead discovery

The `hermes_guide.md` §14 idea of scraping GitHub orgs, engineering blogs, and
"Team" pages for contact info sounds good in theory. In practice, maybe 10–20%
of target companies have public GitHub orgs with real employee names. Most
"Team" pages list executives, not engineers. The hit rate is too low to justify
the build.

### 3. LinkedIn auto-apply

Violates LinkedIn ToS. Risks account bans. The existing auto-fill approach
(Playwright + extension) is safer and covers the same ground without the legal
risk.

### 4. Multi-profile support

The `hermes_guide.md` mentions multi-profile support. In practice, almost
nobody has multiple distinct career profiles they're tailoring for. The Master
CV database already handles different experience sets. Adding profile switching
is complexity for an edge case.

---

## What the competitor research guide got wrong

The separate competitor research guide (generated by Claude) had several
problems:

1. **Invented file paths** — `ghost_scorer.py`, `referral_finder.py` don't
   exist. The real files are `ghost_score.py` and there is no referral finder.
2. **Sourced from competitor marketing** — LoopCV's review of Jobright,
   JobCopilot's comparison pages, and SEO content sites were presented as
   "independent reviews." They're not.
3. **Didn't read `hermes_guide.md`** — which already covers 15+ projects and
   Phases 1–4 in detail. Half the "new" research was duplicating existing work.
4. **Asymmetric skepticism** — scrutinized Jobright's claims but took ApplyJin's
   README at face value.
5. **Invisible effort** — Phase numbers implied reasoned priority but reflected
   "cheap first, everything else grouped by theme."

---

## Priority order (effort estimates based on real code)

| # | Feature | Effort | Impact | Worth it? |
|---|---|---|---|---|
| 1 | Fix salary bugs | 2h | High — currently broken | Yes |
| 2 | Fix selection.py typo | 5m | Low — display only | Yes |
| 3 | RSS feed monitoring | 1d | Medium — automates discovery | Yes |
| 4 | Email → pipeline auto-update | 2d | High — closes the loop | Yes |
| 5 | Contact extraction from JD | 1d | Low — works 10–20% of the time | Maybe |
| 6 | Salary comparison in pipeline | 0.5d | Low — display only | Yes |
| 7 | Chrome extension polish | 3d+ | Low — diminishing returns | No |
| 8 | Referral-lead discovery | 2d | Low — 10–20% hit rate | No |
| 9 | LinkedIn auto-apply | 5d+ | High but illegal | No |
| 10 | Multi-profile support | 2d | Low — edge case | No |

**Total realistic work for items 1–6: about 5 days.**

---

## Sources (verified, not marketing)

- **BLS Occupational Employment Statistics** — `bls.gov/oes/` — actual government
  salary data, not vendor-claimed
- **DOL OFLC disclosure data** — `dol.gov/agencies/eta/foreign-labor/performance` —
  actual visa sponsorship records, not secondhand summaries
- **Adzuna API** — `developers.adzuna.com` — free tier documented on their own
  site, 1000 calls/month
- **feedparser** — `pythonhosted.org/feedparser/` — mature RSS/Atom library, MIT
- **RapidFuzz** — already a dependency, used in `deduplicator.py`

Not cited: competitor comparison pages, affiliate review sites, SEO content
marketing. Those are sales materials, not sources.
