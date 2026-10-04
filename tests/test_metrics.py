from applyjin.inference.metrics import RuntimeMetrics


def test_runtime_metrics_snapshot_tracks_p95():
    metrics = RuntimeMetrics()
    metrics.increment("requests")
    metrics.observe_latency(3)
    metrics.observe_latency(1)
    metrics.observe_latency(2)
    snapshot = metrics.snapshot()
    assert snapshot["counters"] == {"requests": 1}
    assert snapshot["latency_p95_ms"] == 3
    assert "applyjin_requests 1" in metrics.prometheus_text()