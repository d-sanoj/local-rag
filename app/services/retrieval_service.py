"""Retrieval service — dense, sparse, and hybrid (RRF) search.

- ``dense``: vector similarity via the vector repository.
- ``sparse``: BM25 over chunk texts.
- ``hybrid`` (default): dense + sparse fused with Reciprocal Rank Fusion.
Results are normalised to a common shape; scores are the raw per-strategy
scores (dense distance converted to similarity, BM25 score, or RRF score).
Metadata filters (source, file type, date range) apply to dense search
directly and to sparse/hybrid results after retrieval.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import Filters
from app.repositories.bm25_repository import BM25Repository
from app.repositories.vector_repository import VectorRepository
from app.services.embedding_service import EmbeddingService
from app.services.reranking_service import reciprocal_rank_fusion

logger = get_logger(__name__)


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        vector_repo: VectorRepository,
        bm25_repo: BM25Repository,
    ):
        self.settings = settings
        self.embedding_service = embedding_service
        self.vector_repo = vector_repo
        self.bm25_repo = bm25_repo
        # chunk_id -> chunk record, for BM25 hits (BM25 stores no text).
        self._chunk_texts: dict[str, dict[str, Any]] = {}

    def rebuild_bm25_cache(self) -> None:
        """Rebuild the in-memory chunk lookup from the vector store."""
        self._chunk_texts = {c["id"]: c for c in self.vector_repo.get_all()}

    def search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        filters: Filters | None = None,
        fetch_k: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return (results, stats). Each result: id, document_id, source, text,
        score, metadata. ``fetch_k`` is how many candidates each leg returns
        before fusion (defaults to max(top_k * 4, rerank_top_n))."""
        if fetch_k is None:
            fetch_k = max(top_k * 4, self.settings.rerank_top_n)
        stats: dict[str, Any] = {"strategy": strategy}
        if strategy == "dense":
            results = self._dense(query, fetch_k, filters)
            stats["dense_candidates"] = len(results)
        elif strategy == "sparse":
            results = self._sparse(query, fetch_k, filters)
            stats["sparse_candidates"] = len(results)
        else:
            dense = self._dense(query, fetch_k, filters)
            sparse = self._sparse(query, fetch_k, filters)
            fused = reciprocal_rank_fusion(
                [[c["id"] for c in dense], [c["id"] for c in sparse]],
                k=self.settings.rrf_k,
            )
            by_id = {c["id"]: c for c in dense + sparse}
            results = []
            for chunk_id, rrf_score in fused:
                item = dict(by_id[chunk_id])
                item["score"] = rrf_score
                results.append(item)
            stats["dense_candidates"] = len(dense)
            stats["sparse_candidates"] = len(sparse)
            stats["fused_candidates"] = len(results)
        results = self._apply_filters(results, filters)
        return results[:top_k], stats

    def _dense(self, query: str, top_k: int, filters: Filters | None) -> list[dict[str, Any]]:
        query_embedding = self.embedding_service.embed_query(query)
        where = self._chroma_where(filters)
        hits = self.vector_repo.query(query_embedding, top_k, where=where)
        out = []
        for hit in hits:
            item = dict(hit)
            # Chroma returns a distance; convert to a similarity score.
            item["score"] = 1.0 / (1.0 + hit.get("distance", 0.0))
            out.append(item)
        return out

    def _sparse(self, query: str, top_k: int, filters: Filters | None) -> list[dict[str, Any]]:
        scored = self.bm25_repo.search(query, top_k * 2)
        out = []
        for chunk_id, score in scored:
            record = self._chunk_texts.get(chunk_id)
            if record is None:
                continue
            item = dict(record)
            item["score"] = score
            out.append(item)
        return self._apply_filters(out, filters)[:top_k]

    @staticmethod
    def _chroma_where(filters: Filters | None) -> dict[str, Any] | None:
        if filters is None:
            return None
        clauses: list[dict[str, Any]] = []
        if filters.source:
            clauses.append({"source": filters.source})
        if filters.file_type:
            clauses.append({"file_type": filters.file_type})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _apply_filters(
        results: list[dict[str, Any]], filters: Filters | None
    ) -> list[dict[str, Any]]:
        if filters is None:
            return results
        out = []
        for item in results:
            meta = item.get("metadata", {}) or {}
            if filters.source and item.get("source") != filters.source:
                continue
            if filters.file_type and meta.get("file_type") != filters.file_type:
                continue
            if filters.indexed_after or filters.indexed_before:
                indexed_at = meta.get("indexed_at")
                if indexed_at:
                    try:
                        when = datetime.fromisoformat(indexed_at)
                        if filters.indexed_after and when < filters.indexed_after:
                            continue
                        if filters.indexed_before and when > filters.indexed_before:
                            continue
                    except ValueError:
                        pass
            out.append(item)
        return out
