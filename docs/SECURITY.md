# ApplyJin — Security

Threat model, security architecture, and reporting policy. This document is
referenced by `docs/PRODUCT_SCOPE.md` (honest-claims policy) and is the
authoritative map of what the security guarantees are, and where they end.

Related: `docs/GUARDRAILS.md` (product invariants), `docs/PRODUCT_SCOPE.md`
(what ApplyJin is), `tests/test_security.py` (the adversarial suite that
enforces the access-control claims below).

## Security posture

ApplyJin is a **local-first, single-operator workbench**. Auth exists to
protect one operator's data across accounts on one deployment — it is not
multi-tenant SaaS hardening. Every guarantee below maps to a test in
`tests/`; claims without a test were removed, per the honest-claims policy.

| Guarantee | Enforced by | Test |
|---|---|---|
| Auth gate on every private API route | `auth_middleware_dispatch` — JWT session required | `test_security.py::TestUnauthMatrix` (36 routes) |
| Store-level ownership scoping | `WebStore`/`MasterStore` require `user_id` at construction; every query filters on it | `test_tenancy.py::TestStoreIsolation` |
| Cross-tenant reads return 404 (no existence leak) | Ownership filters in every `SELECT`/`UPDATE`/`DELETE` | `test_security.py::TestCrossTenantIDOR` |
| Foreign references rejected at creation | `create_application` checks both parents are owned | `test_security.py::TestCrossTenantIDOR` |
| OAuth state is mandatory + browser-bound + one-shot | Signed, cookie-bound, `state_matches` | `test_auth.py` |
| Forged/expired/unknown-user tokens rejected | HS256 verify + user lookup on every request | `test_security.py::TestTokenForgery` |
| Uploads restricted by extension; text extraction is size-bounded | `_allowed_ext` + parser | `test_auth.py` |
| Uploaded text is untrusted input | Delimited as untrusted at every generation boundary | `tests/test_phase2.py`, prompt contract tests |
| Pre-isolation data migrates to an owner | `user_id` backfill migration | `test_tenancy.py::TestOwnershipMigration` |

## Threat model

Threats T1–T10 and their current disposition. "Mitigated" means a test
enforces it today; "partial" means the boundary exists but one leg is
weaker than the rest; "accepted" means deliberately not addressed.

| # | Threat | Vector | Mitigation | Status | Test |
|---|---|---|---|---|---|
| T1 | Unauthorized read of another candidate's resume/JD/application | Cross-user id probing (`GET /api/resumes/{id}`) | Store-level ownership filter; 404 without existence leak | Mitigated | `TestCrossTenantIDOR` |
| T2 | Edit or delete of another candidate's master CV | Cross-user writes to `/api/master/*` | Same store-level scoping; foreign deletes 404 | Mitigated | `TestCrossTenantIDOR`, `TestStoreIsolation` |
| T3 | Prompt injection via job description | Scraped/JD text instructing the model | Untrusted-content delimiters at generation boundaries; policy and submission stay outside model reach | Mitigated | `test_phase2.py`, decision tests |
| T4 | Prompt injection via uploaded resume | Crafted resume text steering the tailor | Same delimiting at the resume boundary | Mitigated | `test_phase2.py` |
| T5 | Malicious form fill via browser automation | Site tricks the filler into destructive actions | Fill-only policy; the agent never submits; Playwright build is fill-then-stop | Mitigated | Guardrail tests (never-submit invariant) |
| T6 | API key exposure | Keys in repo, logs, or responses | Keys are env/UI-set and gitignored; `/api/settings/llm` redacts keys in every response | Mitigated | redaction tests |
| T7 | Path traversal via upload filename or artifact path | `../../.ssh/...` as a filename | Timestamp-prefixed server-side filenames; `Path(file.filename).name` strips directories; extension allowlist | Partial | upload tests |
| T8 | Fabricated resume claims | LLM invents employers, metrics, dates, skills | Evidence-grounded selection + claim verification gate blocks unsupported resumes before tracking | Mitigated | `test_verification.py`, `test_resume_engine.py` |
| T9 | Autonomous submission | System applies to jobs without a human | Architectural: no code path submits; pipeline stops at human review by construction | Mitigated | guardrail tests |
| T10 | Model/provider failure producing bad output | Timeout, rate limit, malformed JSON | Fail-closed fallbacks route to heuristic mode or human review; retry + circuit breaker; failure taxonomy | Mitigated | `test_failures.py`, `test_decision_layer.py` |

### Known residuals (accepted for a local-first tool)

- **Local open mode**: with `GOOGLE_CLIENT_ID` unset, the API binds to the
  local user with no auth. This is the zero-config design. Do not expose an
  unconfigured instance to the internet.
- **SQLite file**: anyone with filesystem access to `data/` reads all data.
  Disk-level protection is the operator's responsibility.
- **Session TTL**: JWTs are 7-day, stateless, and not server-revocable;
  logout is client-side token discard.
- **CORS**: `*.vercel.app` previews are accepted by regex for the split
  demo deployment; constrain via `ALLOWED_ORIGINS` if you host publicly.

## File isolation

Uploaded artifacts live under per-user directories:

```
data/uploads/<user_id>/<timestamp>_<basename>
```

`user_id` comes from the session principal (never the client), basenames
are stripped to their final component, and artifact paths are generated
server-side — a client-supplied path is never used.

## Reporting

Found something? Open a private security advisory via GitHub
(Security → Report a vulnerability) or email the author. Please do not open
a public issue for an exploitable finding. Reproduction steps and affected
endpoints are enough — no need to include candidate data.
