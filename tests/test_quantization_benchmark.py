from evaluation.benchmarks.matrix import quantization_gate


def test_quantization_gate_accepts_within_tolerance():
    result = quantization_gate(
        {"quality": 0.95, "p95_latency_ms": 100},
        {"quality": 0.94, "p95_latency_ms": 110},
    )
    assert result["accepted"] is True