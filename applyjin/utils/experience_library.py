"""Experience library: RAG over the base resume's bullets and projects.

Primary: ChromaDB persistent collection with sentence-transformers
embeddings. Fallback: in-memory cosine ranking with the local embedding
backend (hashed or MiniLM) — same interface, zero native deps. The
library is a factual bullet store; the tailor may only rephrase these,
never extend them.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Optional

from applyjin.config import DATA_DIR
from applyjin.models import Bullet, ResumeDocument
from applyjin.utils.embeddings import cosine_similarity, get_embeddings

logger = logging.getLogger("applyjin.experience_library")

CHROMA_DIR = DATA_DIR / "chroma_db"
COLLECTION = "experience_bullets"
FALLBACK_PATH = DATA_DIR / "experience_library.json"
_TOKEN_RE = re.compile(r"[a-z0-9+#./-]+", re.IGNORECASE)


class ExperienceLibrary:
    """Bullet-level vector store over resume experience and projects."""

    def __init__(self, use_chroma: bool = True) -> None:
        self._emb = get_embeddings()
        self._chroma = None
        self._collection = None
        self._fallback_docs: dict[str, str] = {}
        self._fallback_meta: dict[str, dict] = {}
        if use_chroma:
            self._init_chroma()

    # ------------------------------------------------------- backends

    def _init_chroma(self) -> None:
        try:
            import chromadb

            # Default embedding function = ChromaDB's bundled ONNX MiniLM:
            # real semantic embeddings with zero torch dependency.
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self._chroma = client
            self._collection = client.get_or_create_collection(
                name=COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            logger.debug("ChromaDB experience library ready at %s", CHROMA_DIR)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ChromaDB unavailable (%s) — using JSON fallback", exc)
            self._chroma = None
            self._load_fallback()

    @property
    def backend(self) -> str:
        if self._collection is not None:
            return "chromadb"
        return f"fallback:{self._emb.backend}"

    # ------------------------------------------------------- indexing

    def index_resume(self, resume: ResumeDocument) -> int:
        """Index every experience/project bullet. Replaces existing entries."""
        bullets = [b for b in resume.bullets if b.text.strip()]
        if not bullets:
            return 0
        for b in bullets:
            b.skills = b.skills or _detect_skills(b.text, resume.skills)

        if self._collection is not None:
            # Upsert handles both insert and replace by id.
            self._collection.upsert(
                ids=[b.id for b in bullets],
                documents=[b.text for b in bullets],
                metadatas=[
                    {
                        "skill_tags": ", ".join(b.skills),
                        "company": b.company or "",
                        "role": b.role or "",
                    }
                    for b in bullets
                ],
            )
        self._fallback_docs = {b.id: b.text for b in bullets}
        self._fallback_meta = {
            b.id: {
                "skill_tags": ", ".join(b.skills),
                "company": b.company or "",
                "role": b.role or "",
            }
            for b in bullets
        }
        if self._collection is None:
            self._save_fallback()
        return len(bullets)

    # ------------------------------------------------------- retrieval

    def query(self, query_text: str, n_results: int = 10) -> list[dict]:
        """Top-N bullets relevant to the query. Returns dicts with text/meta."""
        if not query_text.strip():
            return []
        dense: dict[str, tuple[float, str, dict]] = {}
        if self._collection is not None:
            count = self._collection.count()
            if count == 0:
                return []
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(max(n_results * 3, 20), count),
            )
            docs = results["documents"][0] if results.get("documents") else []
            metas = (results.get("metadatas") or [[]])[0] or []
            ids = (results.get("ids") or [[]])[0] or []
            distances = (results.get("distances") or [[]])[0] or []
            for index, (item_id, document, metadata) in enumerate(zip(ids, docs, metas)):
                distance = float(distances[index]) if index < len(distances) else 1.0
                dense[item_id] = (max(0.0, 1.0 - distance), document, metadata or {})

        if not self._fallback_docs and not dense:
            return []
        if not dense:
            query_vec = self._emb.embed(query_text)
            dense = {
                bid: (cosine_similarity(query_vec, self._emb.embed(text)), text, self._fallback_meta.get(bid, {}))
                for bid, text in self._fallback_docs.items()
            }
        lexical = {
            item_id: _lexical_score(query_text, text)
            for item_id, text in self._fallback_docs.items()
        }
        lexical_rank = {
            item_id: rank for rank, item_id in enumerate(
                sorted(lexical, key=lexical.get, reverse=True), 1
            ) if lexical[item_id] > 0
        }
        ids = set(dense) | set(lexical_rank)
        scored = []
        for item_id in ids:
            if item_id in dense:
                dense_score, text, metadata = dense[item_id]
            else:
                text = self._fallback_docs[item_id]
                metadata = self._fallback_meta.get(item_id, {})
                dense_score = 0.0
            hybrid = 0.6 * dense_score + 0.4 * (1.0 / lexical_rank[item_id] if item_id in lexical_rank else 0.0)
            scored.append((hybrid, item_id, text, metadata))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "id": bid,
                "text": text,
                "metadata": metadata,
                "score": score,
            }
            for score, bid, text, metadata in scored[:n_results]
        ]

    # ------------------------------------------------------- fallback io

    def _load_fallback(self) -> None:
        if FALLBACK_PATH.exists():
            payload = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
            self._fallback_docs = payload.get("docs", {})
            self._fallback_meta = payload.get("meta", {})

    def _save_fallback(self) -> None:
        FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        FALLBACK_PATH.write_text(
            json.dumps(
                {"docs": self._fallback_docs, "meta": self._fallback_meta},
                indent=2,
            ),
            encoding="utf-8",
        )


def _detect_skills(bullet_text: str, known_skills: list[str]) -> list[str]:
    lowered = bullet_text.lower()
    return [s for s in known_skills if s.lower() in lowered]


def _lexical_score(query: str, document: str) -> float:
    """Small BM25-like lexical signal for exact technology terminology."""
    query_terms = set(_TOKEN_RE.findall(query.lower()))
    document_terms = _TOKEN_RE.findall(document.lower())
    if not query_terms or not document_terms:
        return 0.0
    matches = sum(document_terms.count(term) for term in query_terms)
    return matches / math.sqrt(len(document_terms))
