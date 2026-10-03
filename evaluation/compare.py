"""Compare evaluation reports and enforce configurable regression thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(baseline: dict, candidate: dict, max_drop: float = 0.02, max_latency_increase: float = 0.20) -> dict:
    correctness_delta = candidate.get("correctness", 0.0) - baseline.get("correctness", 0.0)
    latency_base = baseline.get("p95_latency_ms", 0.0)
    latency_delta = ((candidate.get("p95_latency_ms", 0.0) - latency_base) / latency_base) if latency_base else 0.0
    return {"correctness_delta": correctness_delta, "p95_latency_change": latency_delta, "passed": correctness_delta >= -max_drop and latency_delta <= max_latency_increase}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ApplyJin evaluation reports")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
