"""Request/response schemas for the API (v1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RetrievalStrategy = Literal["dense", "sparse", "hybrid"]


class Filters(BaseModel):
    """Optional metadata filters for search/query."""

    source: str | None = Field(default=None, description="Exact source path (relative)")
    file_type: str | None = Field(default=None, description="Extension without dot, e.g. 'pdf'")
    indexed_after: datetime | None = None
    indexed_before: datetime | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    strategy: RetrievalStrategy = "hybrid"
    rerank: bool = True
    mmr: bool = False
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Filters | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    source: str
    text: str
    score: float
    rank: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    strategy: str
    reranked: bool
    results: list[SearchResult]
    retrieval_stats: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    strategy: RetrievalStrategy = "hybrid"
    rerank: bool = True
    mmr: bool = False
    top_k: int = Field(default=5, ge=1, le=50)
    filters: Filters | None = None


class Source(BaseModel):
    rank: int
    source: str
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]
    retrieval_stats: dict[str, Any] = Field(default_factory=dict)


class DocumentInfo(BaseModel):
    id: str
    path: str
    file_type: str
    chunk_count: int
    sha256: str
    indexed_at: datetime


class SyncResult(BaseModel):
    added: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    skipped_unsupported: list[str] = Field(default_factory=list)
    documents: int = 0
    chunks: int = 0


class StatsResponse(BaseModel):
    documents_folder: str
    documents: int
    chunks: int
    vector_store_documents: int
    bm25_documents: int
    vector_db_dir: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_available: bool
    ollama_model: str
    embedding_provider: str
    embedding_model: str
    embedding_loaded: bool
    reranker_provider: str
    reranker_model: str
    reranker_loaded: bool
    documents: int
    chunks: int
    watcher_running: bool
    sync_status: str
