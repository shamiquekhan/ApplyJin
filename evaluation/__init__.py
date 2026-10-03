"""ApplyJin AI evaluation harness.

A first-class component, not merely pytest tests: every model, prompt,
retrieval or policy change is evaluated against versioned golden datasets
and compared against a baseline report with regression gates.

Run:
  python -m evaluation.run --dataset evaluation/datasets/all_cases.jsonl \
      --system applyjin --report evaluation/reports/latest.json
Compare:
  python -m evaluation.compare --baseline evaluation/reports/baseline.json \
      --candidate evaluation/reports/latest.json
"""
