"""Query service — the orchestration: retrieve → rerank → (MMR) → generate.

This is the only place that knows the full pipeline. Controllers call it;
they never call the retrieval or generation services directly.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    Source,
)
from app.services.generation_service import GenerationService
from app.services.reranking_service import RerankingService, maximal_marginal_relevance
from app.services.retrieval_service import RetrievalService

logger = get_logger(__name__)


class QueryService:
    def __init__(
        self,
        settings: Settings,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        generation_service: GenerationService,
    ):
        self.settings = settings
        self.retrieval_service = retrieval_service
        self.reranking_service = reranking_service
        self.generation_service = generation_service

    def search(self, request: SearchRequest) -> SearchResponse:
        results, stats = self._retrieve(request)
        return SearchResponse(
            query=request.query,
            strategy=request.strategy,
            reranked=request.rerank,
            results=[
                SearchResult(
                    chunk_id=r["id"],
                    document_id=r.get("document_id", ""),
                    source=r.get("source", ""),
                    text=r.get("text", ""),
                    score=float(r.get("score", 0.0)),
                    rank=i + 1,
                    metadata=r.get("metadata", {}),
                )
                for i, r in enumerate(results)
            ],
            retrieval_stats=stats,
        )

    def query(self, request: QueryRequest) -> QueryResponse:
        results, stats = self._retrieve(request)
        answer = self.generation_service.generate_answer(request.question, results)
        sources = [
            Source(
                rank=i + 1,
                source=r.get("source", ""),
                chunk_id=r["id"],
                text=r.get("text", ""),
                score=float(r.get("score", 0.0)),
                metadata=r.get("metadata", {}),
            )
            for i, r in enumerate(results)
        ]
        return QueryResponse(
            question=request.question,
            answer=answer,
            sources=sources,
            retrieval_stats=stats,
        )

    def _retrieve(
        self, request: SearchRequest | QueryRequest
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        query_text = request.query if isinstance(request, SearchRequest) else request.question
        # Fetch more candidates than top_k when reranking is on, so the
        # reranker has something to reorder.
        fetch_k = self.settings.rerank_top_n if request.rerank else request.top_k
        results, stats = self.retrieval_service.search(
            query_text,
            strategy=request.strategy,
            top_k=fetch_k,
            filters=request.filters,
            fetch_k=fetch_k,
        )
        stats["candidates"] = len(results)
        if request.rerank and results:
            results = self.reranking_service.rerank(query_text, results)
            stats["reranked"] = True
        if request.mmr and results:
            query_embedding = self.retrieval_service.embedding_service.embed_query(query_text)
            results = maximal_marginal_relevance(
                query_embedding,
                results,
                lambda_=self.settings.mmr_lambda,
                top_k=request.top_k,
            )
            stats["mmr"] = True
        results = results[: request.top_k]
        stats["returned"] = len(results)
        return results, stats
