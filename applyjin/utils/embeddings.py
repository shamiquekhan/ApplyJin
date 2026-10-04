"""Embeddings with a graceful local fallback.

Primary: sentence-transformers `all-MiniLM-L6-v2` (local, no API).
Fallback: deterministic hashed bag-of-words vector — lower semantic quality
but keeps the pipeline runnable with zero heavy dependencies (tests, CI).
Both produce normalized vectors, so cosine similarity works uniformly.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_DIM = 512


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EmbeddingFunction(Protocol):
    def embed(self, text: str) -> list[float]: ...

    @property
    def backend(self) -> str: ...


class SentenceTransformerEmbeddings:
    """Real semantic embeddings via sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._name = model_name

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in vector]

    @property
    def backend(self) -> str:
        return f"sentence-transformers:{self._name}"


class HashedEmbeddings:
    """Deterministic hashed bag-of-words fallback (no dependencies)."""

    def __init__(self, dim: int = _DIM) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in _tokens(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    @property
    def backend(self) -> str:
        return f"hashed-bow:{self._dim}"


_default: EmbeddingFunction | None = None


class ONNXEmbeddings:
    """Real semantic embeddings via ChromaDB's bundled ONNX MiniLM model.

    No torch/sentence-transformers required — chromadb ships an ONNX
    all-MiniLM-L6-v2 that downloads once (~80MB) then runs locally.
    """

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._fn = ONNXMiniLM_L6_V2()
        self._name = "onnx-MiniLM-L6-v2"

    def embed(self, text: str) -> list[float]:
        # chromadb's function expects a list of documents and returns
        # numpy arrays; normalize to plain lists of floats.
        vectors = self._fn([text])
        vec = [float(x) for x in vectors[0]]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    @property
    def backend(self) -> str:
        return f"onnx:{self._name}"


def get_embeddings() -> EmbeddingFunction:
    """Best available backend: MiniLM (torch) > MiniLM (ONNX) > hashed."""
    global _default
    if _default is None:
        try:
            _default = SentenceTransformerEmbeddings()
        except Exception:  # noqa: BLE001 — torch may be missing
            try:
                _default = ONNXEmbeddings()
            except Exception:  # noqa: BLE001 — chromadb may be missing
                _default = HashedEmbeddings()
    return _default


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity for equal-length vectors (dot of normalized)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))
