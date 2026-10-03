# Laya + vLLM: Measured Results vs the Previous Stack

**Date:** 2026-10-04
**Scope:** Decision layer (Laya vs the heuristic-only path) and generation
(vLLM vs Gemini-only), measured against the committed evaluation datasets and
identical-prompt A/B runs. Companion to `AI_ENGINEERING_GAP_ANALYSIS.md`.

## Baselines

- **Before (decisions):** `DecisionAgent` fell back to the deterministic
  `HeuristicDecisionProvider` (`rules-v1`) because Laya had no cached weights.
- **Before (generation):** Gemini-only chain (Ollama entry dead, vLLM entry
  previously misconfigured against port 8000 — the app's own port).
- **Now:** Laya (`backend=laya`, English checkpoint) for decisions;
  local vLLM `Qwen/Qwen2.5-0.5B-Instruct` on `:8001` in the generation chain
  behind a measured model registry.

## 1. Decision layer

Both providers ran the exact scoring path CI gates on
(`evaluation/runner.evaluate_case`) over the committed datasets:

| Dataset (n) | Metric | Before: heuristic | Now: Laya | Δ |
|---|---|---|---|---|
| decision.jsonl (26) | correctness | **84.6%** (22/26) | 80.8% (21/26) | **−3.8pp** |
| security.jsonl (20) | injection safety | **75.0%** (15/20) | **90.0%** (18/20) | **+15pp** |
| — | gating sub-score | 66.7% (4/6) | **100%** (6/6) | +33pp |
| — | classification sub-score | **90%** (18/20) | 75% (15/20) | −15pp |
| — | p95 latency | ~0.1ms | 504–715ms (CPU) | +0.5–0.7s |
| — | first-load cost | 0 | ~10s per process (checkpoint) | — |

### Where each wins

- **Laya's 5 classification misses are boundary errors**: `dbt/Snowflake →
  "ML Engineer"` (expected Data Engineer), `marketing ops → "Software Engineer"`
  (expected Other), and LLM-adjacent texts over-attracted to "ML Engineer".
  The keyword rules handle those exact cases well.
- **Laya is perfect on gating** (6/6); the rules fail 2/6 on synonym phrasing.
- **Security: Laya strictly dominates the rules.** Its only 2 misses are
  *fabrication-claim* phrasings ("Add this skill… Kubernetes", "Claim they
  worked at Google"); directive-style injections ("ignore previous
  instructions") are caught at 0.97 confidence. The heuristic's 5 misses
  include 3 that Laya catches; every case the rules get right, Laya gets right.
- **Ensemble potential:** the two miss sets overlap on a single decision case
  (`jobtype-017`), so a disagreement→REVIEW rule would score **~96% (25/26)**
  on decision.jsonl — better than either provider alone.

### Production impact

`DecisionAgent` gates the orchestrator pipeline (GENERATE/REVIEW/SKIP,
`hermes/orchestrator.py:275`). Laya decisions now flow with reported
confidence, feeding the 0.60 `min_decision_confidence` gate. Cost is
~0.5–0.7s per decision batch **on CPU** — vLLM holds 2.95/3.6GB of VRAM, so
Laya's GPU path is evicted (its own warning: 10–15× slower, ~200–500ms vs
~35ms per inference).

## 2. Generation

Identical prompts, fresh router per call, backend verified via telemetry:

| Prompt | Gemini (before) | vLLM (new) | Speedup | Gemini out-tokens | vLLM out-tokens |
|---|---|---|---|---|---|
| one-word answer | 5,361ms | **631ms** | **8.5×** | 77 (thinking) | 4 |
| JSON headline+about | 4,936ms | **668ms** | **7.4×** | 797 | 72 |
| 3 tailored bullets | 6,625ms | **705ms** | **9.4×** | 1,259 | 78 |
| full real tailor (product path) | 33.5s / 44.2s | not routed (ctx gate) | — | — | — |

### Quality — why speed isn't everything

- **vLLM fabricated a claim**: *"With over five years of experience…"* — no
  experience duration exists in the supplied facts. It also produced filler
  bullets and wrapped output in ` ```json ` fences (Gemini returns raw JSON;
  `complete_json` brace-extraction tolerates fences, raw consumers won't).
- Gemini's outputs parsed clean, stayed within the facts, and its headline was
  keyword-rich (ATS-relevant); vLLM's headline was just the candidate's name.
- Gemini burns **10–16× more output tokens** (thinking) per call — on a
  free-tier quota that is 10× less headroom and 10× more rate-limit exposure.
- vLLM server-side during these requests: ~15 tok/s generation, KV-cache 0%
  used, prefix-cache hits 22–55%.

### Reliability observed

- Gemini: 1× `ServiceUnavailableError` (503, caught by retry) plus the 3.5s
  free-tier RPM throttle between calls. Before, exhausting the chain ended in
  `LLMUnavailable`; now there is a local last resort.
- vLLM: 0 failures across all runs in this session.

### What actually serves traffic (registry-gated)

- Utility: Gemini **0.69** vs vLLM **0.59** (measured registry: quality 0.80,
  p95 1359ms) → Gemini primary, vLLM failover for short calls.
- `max_context_tokens: 2048` **filters vLLM out of tailoring entirely**
  (inputs ~3–4k tokens) — deliberate: its fabrication rate would ship lies in
  resumes.

So vLLM's 8–9× latency win is currently a **resilience/offline asset, not a
primary path**. It pays off when Gemini is down, or after generation-quality
measurement earns it promotion.

## 3. Net scorecard

| Dimension | Before | Now |
|---|---|---|
| Injection safety | 75% | **90%** (Laya) |
| Gating correctness | 67% | **100%** |
| Classification | **90%** | 75% (→ ~96% via disagreement→REVIEW) |
| Decision latency | ~0ms | 0.5–0.7s per batch (CPU) |
| Short-generation latency | 5–7s (Gemini) | 0.6–1.1s if routed |
| Full tailor | 33–44s (Gemini) | unchanged (Gemini, by design) |
| Output-token cost | 10–16× higher | local baseline |
| Outage behavior | dead-end after retries | local failover exists |
| Output safety | grounded | vLLM: 1 fabricated claim in 3 outputs → gated out of tailoring |
| Infra | API-only | +GPU server on :8001 (3GB VRAM), Laya CPU-contended, port collision fixed |

## Bottom line

- **Laya** is a clear safety/gating win (+15pp / +33pp) for ~0.6s per batch,
  with a classification regression (−15pp) that a disagreement-review rule
  would turn into ~96% overall accuracy.
- **vLLM** is an 8–9× latency and outage-resilience win whose output quality
  (fabrication, JSON fences) currently — correctly — keeps it behind the
  measured-registry gate for resume work.

## Recommended next steps

1. **Agreement gating:** run Laya and the rules together; disagreement →
   REVIEW (estimated ~96% on decision.jsonl).
2. **GPU scheduling:** run vLLM with `--gpu-memory-utilization 0.6` (or
   serialize) so Laya can keep its GPU path.
3. **Generation-quality eval** before any vLLM promotion to primary routing —
   measure, don't vibes.

## Methodology

- Decision runs: `evaluation/runner.evaluate_case` with each provider over
  `evaluation/datasets/decision.jsonl` (26) and `security.jsonl` (20);
  per-type means, p95 latency, and miss IDs recorded. Scored identically to
  the CI gates in `tests/test_evaluation_datasets.py`.
- Generation runs: fresh `LLMRouter` per call against one-entry chains
  (Gemini `gemini-3.6-flash` vs vLLM `Qwen/Qwen2.5-0.5B-Instruct`), three
  fixed prompts (one-word, JSON headline/about, 3 tailored bullets from a
  fixed candidate/JD pair); wall time plus `INFERENCE_METRICS` telemetry
  (input/output tokens, failure flag) recorded. n=1 per cell — latency figures
  are indicative, quality findings are from full-output inspection.
