"""Shared fixtures: temp settings, an in-memory vector repo, fake services."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document


def make_settings(tmp_path: Path, **overrides) -> Settings:
    kwargs = {
        "documents_dir": str(tmp_path / "documents"),
        "vector_db_dir": str(tmp_path / "chroma"),
        "manifest_db_path": str(tmp_path / "manifest.db"),
        "bm25_path": str(tmp_path / "bm25.json"),
        "embedding_provider": "dummy",
        "reranker_provider": "dummy",
        "llm_provider": "echo",
        "watcher_enabled": False,
        "text_chunk_strategy": "section",
    }
    kwargs.update(overrides)
    settings = Settings(**kwargs)
    os.makedirs(settings.documents_dir, exist_ok=True)
    return settings


class InMemoryVectorRepo:
    """VectorRepository backed by a dict; cosine similarity for query."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        for chunk, emb in zip(chunks, embeddings, strict=True):
            self._store[chunk.id] = {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "source": chunk.source,
                "text": chunk.text,
                "metadata": {
                    "document_id": chunk.document_id,
                    "source": chunk.source,
                    **chunk.metadata,
                },
                "embedding": emb,
            }

    def delete_by_document(self, document_id: str) -> None:
        for key in [k for k, v in self._store.items() if v["document_id"] == document_id]:
            del self._store[key]

    def query(self, query_embedding, top_k, where=None):
        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b, strict=True))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb) if na and nb else 0.0

        items = list(self._store.values())
        if where:
            items = [
                i
                for i in items
                if all(i["metadata"].get(k) == v for k, v in where.items() if k != "$and")
            ]
        scored = sorted(items, key=lambda i: cosine(query_embedding, i["embedding"]), reverse=True)
        return [
            {
                "id": item["id"],
                "document_id": item["document_id"],
                "source": item["source"],
                "text": item["text"],
                "distance": 1.0 - cosine(query_embedding, item["embedding"]),
                "metadata": item["metadata"],
                "embedding": item["embedding"],
            }
            for item in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self._store)

    def get_all(self):
        return [
            {
                "id": v["id"],
                "document_id": v["document_id"],
                "source": v["source"],
                "text": v["text"],
                "metadata": v["metadata"],
            }
            for v in self._store.values()
        ]


def make_document(path: str, content: bytes = b"") -> Document:
    import hashlib

    return Document.from_path(path, f"/tmp/{path}", hashlib.sha256(content).hexdigest(), 0.0)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def vector_repo():
    return InMemoryVectorRepo()
