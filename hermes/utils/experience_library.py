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
from pathlib import Path
from typing import Optional

from hermes.config import DATA_DIR
from hermes.models import Bullet, ResumeDocument
from hermes.utils.embeddings import cosine_similarity, get_embeddings

logger = logging.getLogger("hermes.experience_library")

CHROMA_DIR = DATA_DIR / "chroma_db"
COLLECTION = "experience_bullets"
FALLBACK_PATH = DATA_DIR / "experience_library.json"


class ExperienceLibrary:
    """Bullet-level vector store over resume experience and projects."""

    def __init__(self, use_chroma: bool = True) -> None:
        self._emb = get_embeddings()
        self._chroma = None
        self._collection = None
        if use_chroma:
            self._init_chroma()
        self._fallback_docs: dict[str, str] = {}
        self._fallback_meta: dict[str, dict] = {}

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
        else:
            self._fallback_docs = {b.id: b.text for b in bullets}
            self._fallback_meta = {
                b.id: {
                    "skill_tags": ", ".join(b.skills),
                    "company": b.company or "",
                    "role": b.role or "",
                }
                for b in bullets
            }
            self._save_fallback()
        return len(bullets)

    # ------------------------------------------------------- retrieval

    def query(self, query_text: str, n_results: int = 10) -> list[dict]:
        """Top-N bullets relevant to the query. Returns dicts with text/meta."""
        if not query_text.strip():
            return []
        if self._collection is not None:
            count = self._collection.count()
            if count == 0:
                return []
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, count),
            )
            docs = results["documents"][0] if results.get("documents") else []
            metas = (results.get("metadatas") or [[]])[0] or []
            ids = (results.get("ids") or [[]])[0] or []
            return [
                {"id": i, "text": d, "metadata": m or {}}
                for i, d, m in zip(ids, docs, metas)
            ]

        if not self._fallback_docs:
            return []
        query_vec = self._emb.embed(query_text)
        scored = [
            (cosine_similarity(query_vec, self._emb.embed(text)), bid, text)
            for bid, text in self._fallback_docs.items()
        ]
        scored.sort(reverse=True)
        return [
            {
                "id": bid,
                "text": text,
                "metadata": self._fallback_meta.get(bid, {}),
                "score": score,
            }
            for score, bid, text in scored[:n_results]
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
