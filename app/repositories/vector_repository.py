"""Vector repository — interface plus the ChromaDB implementation.

The interface is the contract; ChromaDB is the default embedded store
(persistent, local, no server). Swapping the store means implementing this
protocol, not touching the services.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.logging import get_logger
from app.models.chunk import Chunk

logger = get_logger(__name__)


class VectorRepository(Protocol):
    """Contract for the vector store."""

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None: ...
    def delete_by_document(self, document_id: str) -> None: ...
    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...
    def count(self) -> int: ...
    def get_all(self) -> list[dict[str, Any]]: ...


class ChromaVectorRepository:
    """ChromaDB persistent client. Collection name is fixed per service."""

    def __init__(self, persist_dir: str, collection_name: str = "local_rag"):
        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(name=collection_name)
        logger.info("ChromaDB collection '%s' at %s", collection_name, persist_dir)

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "document_id": c.document_id,
                    "source": c.source,
                    "chunk_index": c.index,
                    **{k: str(v) for k, v in c.metadata.items()},
                }
                for c in chunks
            ],
        )

    def delete_by_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for i, chunk_id in enumerate(ids):
            meta = dict(metas[i]) if i < len(metas) and metas[i] else {}
            out.append(
                {
                    "id": chunk_id,
                    "document_id": meta.get("document_id", ""),
                    "source": meta.get("source", ""),
                    "text": docs[i] if i < len(docs) else "",
                    "distance": dists[i] if i < len(dists) else 0.0,
                    "metadata": meta,
                }
            )
        return out

    def count(self) -> int:
        return self._collection.count()

    def get_all(self) -> list[dict[str, Any]]:
        results = self._collection.get(include=["documents", "metadatas"])
        out: list[dict[str, Any]] = []
        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        for i, chunk_id in enumerate(ids):
            meta = dict(metas[i]) if i < len(metas) and metas[i] else {}
            out.append(
                {
                    "id": chunk_id,
                    "document_id": meta.get("document_id", ""),
                    "source": meta.get("source", ""),
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": meta,
                }
            )
        return out
