from evaluation.benchmarks.vllm_benchmark import summarize


def test_vllm_benchmark_summary_reports_failures_and_percentiles():
    report = summarize(
        [
            {"status": "ok", "ttft_ms": 10, "tpot_ms": 2, "latency_ms": 20, "tokens": 5},
            {"status": "error", "error": "TimeoutError", "latency_ms": 30},
        ],
        elapsed_seconds=1,
    )
    assert report["failures"] == 1
    assert report["failure_rate"] == 0.5
    assert report["tokens_per_second"] == 5