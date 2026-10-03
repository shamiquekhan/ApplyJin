"""Deterministic train/held-out dataset splitting for model experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def split_jsonl(
    source: Path,
    train_path: Path,
    heldout_path: Path,
    *,
    heldout_fraction: float = 0.2,
    seed: str = "applyjin-v1",
) -> tuple[int, int]:
    """Split cases by stable case id so reruns never reshuffle evaluation data."""
    if not 0.0 < heldout_fraction < 1.0:
        raise ValueError("heldout_fraction must be between 0 and 1")
    train: list[str] = []
    heldout: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        case_id = str(case.get("id", line))
        digest = hashlib.sha256(f"{seed}:{case_id}".encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        (heldout if bucket < heldout_fraction else train).append(json.dumps(case, sort_keys=True))
    train_path.parent.mkdir(parents=True, exist_ok=True)
    heldout_path.parent.mkdir(parents=True, exist_ok=True)
    train_path.write_text("\n".join(train) + ("\n" if train else ""), encoding="utf-8")
    heldout_path.write_text("\n".join(heldout) + ("\n" if heldout else ""), encoding="utf-8")
    return len(train), len(heldout)