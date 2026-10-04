"""SQLite persistence for privacy-preserving inference events."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from applyjin.config import DATA_DIR


class MetricsStore:
    """Persist operational metadata without storing prompts or documents."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or DATA_DIR / "metrics.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inference_metrics (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                model TEXT NOT NULL,
                backend TEXT NOT NULL,
                action TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def record(
        self,
        *,
        kind: str,
        model: str = "",
        backend: str = "",
        action: str = "",
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key in {"input_tokens", "output_tokens", "retrieved_chunks", "discarded_chunks", "fallback_used"}
        }
        self.conn.execute(
            "INSERT INTO inference_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                datetime.utcnow().isoformat(),
                kind,
                model,
                backend,
                action,
                float(latency_ms),
                json.dumps(safe_metadata, sort_keys=True),
            ),
        )
        self.conn.commit()

    def summary(self) -> dict[str, int | float]:
        row = self.conn.execute(
            "SELECT COUNT(*), COALESCE(AVG(latency_ms), 0), "
            "SUM(CASE WHEN action = 'GENERATE' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN action = 'REVIEW' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN action = 'SKIP' THEN 1 ELSE 0 END) "
            "FROM inference_metrics"
        ).fetchone()
        return {
            "events": int(row[0]),
            "average_latency_ms": round(float(row[1]), 2),
            "generate": int(row[2] or 0),
            "review": int(row[3] or 0),
            "skip": int(row[4] or 0),
        }

    def close(self) -> None:
        self.conn.close()