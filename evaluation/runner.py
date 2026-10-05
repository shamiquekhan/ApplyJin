"""Offline JSONL evaluation runner for decision and safety regression cases."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from evaluation.evaluators.claims import aggregate_claim_results, evaluate_claim_case
from evaluation.evaluators.correctness import evaluate_classification, evaluate_gating
from evaluation.evaluators.performance import percentile
from evaluation.evaluators.safety import evaluate_adversarial
from evaluation.evaluators.grounding import evaluate_grounding
from evaluation.evaluators.trajectory import evaluate_trajectory
from applyjin.inference.heuristic_provider import HeuristicDecisionProvider
from applyjin.inference.schemas import DecisionQuestion, DecisionRequest


def evaluate_case(case: dict, provider: HeuristicDecisionProvider) -> dict:
    started = time.perf_counter()
    case_type = case.get("type", "classification")
    if case_type in {"malformed", "tool_failure"}:
        try:
            question = case.get("question", "classification")
            request = DecisionRequest(
                state=str(case.get("state", "")),
                questions={question: DecisionQuestion(**case["decision_question"])},
            )
            provider.decide(request)
        except Exception as exc:  # noqa: BLE001 - failures are evaluation data
            return {
                "id": case.get("id", ""),
                "type": case_type,
                "actual": "failure",
                "expected": "failure",
                "score": 1.0,
                "error": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        return {
            "id": case.get("id", ""),
            "type": case_type,
            "actual": "success",
            "expected": "failure",
            "score": 0.0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    if case_type == "claim":
        metrics = evaluate_claim_case(case)
        metrics["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return metrics
    if case_type == "grounding":
        metrics = evaluate_grounding(
            str(case.get("output", "")), list(case.get("allowed_evidence", []))
        )
        metrics["score"] = metrics["groundedness"]
        return {"id": case.get("id", ""), "type": case_type, **metrics, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
    if case_type == "trajectory":
        metrics = evaluate_trajectory(list(case.get("expected_steps", [])), list(case.get("actual_steps", [])))
        metrics["score"] = (metrics["trajectory_recall"] + metrics["trajectory_precision"]) / 2
        return {"id": case.get("id", ""), "type": case_type, **metrics, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
    question = case.get("question", "classification")
    request = DecisionRequest(
        state=str(case.get("state", "")),
        questions={question: DecisionQuestion(**case["decision_question"])},
    )
    result = provider.decide(request)
    answer = result.answers[question].value
    expected = str(case.get("expected", ""))
    if case_type == "adversarial":
        metrics = evaluate_adversarial(expected.lower() == "true", answer.lower() == "true")
    elif case_type == "gating":
        metrics = evaluate_gating(expected, answer)
    else:
        metrics = evaluate_classification(expected, answer)
    metrics["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return {"id": case.get("id", ""), "type": case_type, "actual": answer, **metrics}


def run(dataset: Path) -> dict:
    provider = HeuristicDecisionProvider()
    results = [evaluate_case(json.loads(line), provider) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    scores = [float(item.get("score", 0.0)) for item in results]
    safety = [float(item.get("score", 0.0)) for item in results if item["type"] == "adversarial"]
    report = {"cases": len(results), "correctness": sum(scores) / len(scores) if scores else 0.0, "safety": sum(safety) / len(safety) if safety else 0.0, "p95_latency_ms": percentile([float(item["latency_ms"]) for item in results], 95), "results": results}
    claim_results = [item for item in results if item["type"] == "claim"]
    if claim_results:
        report["grounding"] = aggregate_claim_results(claim_results)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ApplyJin's offline evaluation harness")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.dataset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"ApplyJin Evaluation: {report['cases']} cases, correctness={report['correctness']:.1%}, p95={report['p95_latency_ms']:.2f}ms")
    grounding = report.get("grounding")
    if grounding:
        print(
            f"Grounding: escape_rate={grounding['escape_rate']:.1%} "
            f"({grounding['escapes']}/{grounding['adversarial_cases']}), "
            f"false_reject_rate={grounding['false_reject_rate']:.1%} "
            f"({grounding['false_rejects']}/{grounding['honest_cases']})"
        )


if __name__ == "__main__":
    main()
