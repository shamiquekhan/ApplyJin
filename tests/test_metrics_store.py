from hermes.inference.metrics_store import MetricsStore


def test_metrics_store_persists_only_allowed_metadata(tmp_path):
    store = MetricsStore(tmp_path / "metrics.sqlite3")
    store.record(
        kind="generation",
        model="local",
        action="GENERATE",
        latency_ms=12.5,
        metadata={"input_tokens": 10, "raw_resume": "must not persist"},
    )
    assert store.summary() == {
        "events": 1,
        "average_latency_ms": 12.5,
        "generate": 1,
        "review": 0,
        "skip": 0,
    }
    stored = store.conn.execute("SELECT metadata_json FROM inference_metrics").fetchone()[0]
    assert "raw_resume" not in stored
    store.close()