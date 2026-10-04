# Architecture

## Pipeline

```
JobScout ──> JDAnalyzer ──> FitScorer ──> ResumeTailor ──> CoverLetter
   (JobSpy,     (LLM JSON,     (keyword +     (RAG via       (grounded
   dedup)       heuristic       semantic +     ChromaDB,      prompt,
                fallback)       seniority)     guardrails)    template
                                                                fallback)
                                                    │
                                       HumanReview (applyjin review) ◄─┘
                                                    │
                                    ApplicationAgent (fill, never submit)
                                                    │
                                                 Tracker (SQLite)
                                                    │
              LearningAgent ◄──────────────────────┘
              (keyword lift, A/B chi², style guide vN)
                       │
                       └──► ResumeTailor prompt (feedback loop)
```

## Modules

| Module | File | Role |
|---|---|---|
| Config | `applyjin/config.py` | Pydantic models over YAML; env keys override file |
| Models | `applyjin/models/__init__.py` | JobPosting, JobAnalysis, ScoredJob, Resume, Application |
| LLM router | `applyjin/utils/llm_router.py` | LiteLLM chain with failover (Gemini→OpenRouter→Ollama) |
| Embeddings | `applyjin/utils/embeddings.py` | MiniLM (torch) → ONNX MiniLM → hashed fallback |
| Experience library | `applyjin/utils/experience_library.py` | ChromaDB bullet store; JSON fallback |
| ATS scorer | `applyjin/utils/ats_scorer.py` | fuzzy keyword match + cosine similarity |
| PDF | `applyjin/utils/pdf_generator.py` | Playwright → WeasyPrint → HTML chain |
| Agents | `applyjin/agents/*` | scout, analyzer, scorer, tailor, cover, application, tracker, learning, triage, prep, outreach, dashboard, A/B |
| Web | `applyjin/web/app.py` | FastAPI read-only dashboard |
| CLI | `applyjin/cli.py` | Typer commands; orchestrator wires agents |

## Data flow

1. `applyjin run` → orchestrator: scout jobs → per job: analyze → score →
   filter → assign A/B variant → tailor (RAG + style guide) → cover letter →
   ATS before/after → artifacts (`data/applications/<job>/`) → tracker row
   (`pending_review`).
2. `applyjin review` → human approves/rejects each. Approved = submit manually
   (optionally `applyjin fill` pre-fills the form).
3. Outcomes flow back via `applyjin tracker update` or `applyjin triage-email`.
4. `applyjin learn` → lift analysis + ATS-delta correlation + A/B chi² →
   style guide version → injected into the next tailor run.

## Storage

- `data/hermes.db` — SQLite: applications (A/B variant, ATS scores,
  hashes), learning_patterns, style_guide_versions
- `data/chroma_db/` — vector store of resume bullets
- `data/applications/<job>/` — resume.md/.html/.pdf, cover_letter.md, job.md
- `config/` — profile(s), LLM chain, searches, email (gitignored)

## Degradation ladder

Every component has a fallback so the pipeline never hard-crashes:
LLM → heuristic; ChromaDB → JSON cosine; MiniLM → hashed embeddings;
Playwright PDF → WeasyPrint → HTML; JobSpy → sample JSONL.

## AI inference and evaluation layer

```text
retrieval/context budget
   -> Laya or heuristic decision provider
   -> deterministic policy
   -> utility-weighted generation router
   -> vLLM/OpenAI-compatible provider
   -> claim verification
   -> human review
```

Decision traces store hashes and typed results rather than raw candidate
documents. Runtime metrics are available at `/metrics`; benchmark reports live
under `evaluation/reports/`.
