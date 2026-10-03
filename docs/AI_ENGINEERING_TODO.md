# ApplyJin AI Engineering Upgrade

This backlog tracks the local, measurable AI system. The offline heuristic path
is the availability baseline; optional model services are never required for
ordinary CLI use or tests.

## Completed

- [x] Typed decision provider, deterministic policy, fallback, and hashed traces
- [x] Laya adapter and retrieval-backed resume tailoring with guardrails
- [x] Provider-neutral async LLM contract and optional vLLM adapter
- [x] Evidence-budgeted context with untrusted-content delimiters
- [x] Dependency-free retry and circuit-breaker primitives
- [x] Verification gate blocks unsupported tailored resumes before tracking
- [x] Offline JSONL evaluation runner, reports, and basic regression gate
- [x] Retrieval ranking metrics and dependency-free decision runtime metrics
- [x] Utility-weighted generation routing with configurable failover ordering
- [x] Claim extraction and evidence references for generated resumes
- [x] Evaluation cases for malformed input and invalid tool/model responses
- [x] Dependency-free Prometheus exposition for runtime metrics
- [x] Privacy-preserving SQLite persistence for inference metrics
- [x] Reproducible vLLM benchmark command for TTFT, TPOT, latency, throughput, and failures
- [x] Failure taxonomy and evaluation coverage for grounding and trajectory
- [x] Delimit scraped job descriptions as untrusted decision-model input
- [x] Expose hashed decision traces for human review
- [x] Benchmark matrix and quantization quality-gate framework
- [x] Deterministic held-out dataset split for model experiments
- [x] Fail-closed decision fallback routes unavailable policy to human review
- [x] Token-aware context budgeting wired into resume generation
- [x] Normalize routing utility terms before provider selection
- [x] Freeze reproducible baseline metadata and measured reports
- [x] Add typed decision labels and minimum-confidence review gates
- [x] Keep deterministic fit scoring primary while Laya handles bounded decisions
- [x] Add typed metric/date checks to claim verification
- [x] Declare vLLM in the optional local-inference dependency set
- [x] Run initial Qwen 0.5B vLLM measurements on the GTX 1650
- [x] Add executable FP16 versus NF4 4-bit comparison command
- [x] Add held-out QLoRA experiment command and separated synthetic cases
- [x] Run FP16 versus NF4 comparison on the GTX 1650
- [x] Run held-out QLoRA smoke comparison on the GTX 1650

## Next Priority

- [ ] Expand the evaluation dataset with larger labelled and adversarial sets
- [x] Export Prometheus metrics through the web application endpoint

## Audit Follow-Ups

- [x] Fail-closed decision handling and deterministic-fit ownership
- [x] Token-aware context integration in resume generation
- [x] Typed verification for generated metrics and dates
- [ ] Consolidate LiteLLM and vLLM behind the canonical `LLMProvider`
- [ ] Replace hard-coded routing estimates with measured model-registry data
- [ ] Add hybrid BM25 plus dense retrieval and reranking
- [ ] Expand typed verification to companies, titles, skills, and certifications
- [ ] Add token usage, TTFT, TPOT, queue, retry, and provider telemetry
- [ ] Add stratified A/B analysis by job family, seniority, board, and fit

## Model Operations

- [ ] Expand the vLLM benchmark matrix across context lengths and prefix-cache modes
- [ ] Expand FP16 versus NF4 quality evaluation beyond the smoke prompt
- [ ] Run prefix-caching and concurrency matrix on target hardware
- [ ] Scale held-out LoRA/QLoRA comparisons beyond the smoke experiment

## Product Safety

- [ ] Mark company pages as untrusted
- [x] Delimit retrieved RAG content and job text in Copilot prompts
- [x] Delimit uploaded resume content at the generation boundary
- [x] Keep policy and human submission outside model-generated content
- [x] Expose claim evidence and verification warnings in the review API
- [x] Add failure taxonomy and human-review fallback to the generation verification boundary