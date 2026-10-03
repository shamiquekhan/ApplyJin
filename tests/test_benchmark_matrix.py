from evaluation.benchmarks.matrix import build_matrix, quantization_gate


def test_matrix_covers_context_concurrency_and_prefix_cache():
    matrix = build_matrix(["small"], contexts=[1024, 4096], concurrencies=[1, 2], outputs=[128])
    assert len(matrix) == 16
    assert any(case.prefix_caching for case in matrix)


def test_quantization_gate_rejects_quality_regression():
    result = quantization_gate(
        {"quality": 0.95, "p95_latency_ms": 100},
        {"quality": 0.90, "p95_latency_ms": 90},
    )
    assert result["accepted"] is False