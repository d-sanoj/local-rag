"""Dependency injection — one place that builds the service graph.

Services are constructed once at startup and stored on ``app.state``.
Controllers get them from here; tests override these dependencies with
fakes via FastAPI's dependency_overrides.
"""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings
from app.repositories.bm25_repository import BM25Repository
from app.repositories.manifest_repository import ManifestRepository
from app.repositories.vector_repository import ChromaVectorRepository, VectorRepository
from app.services.chunking.registry import ChunkerRegistry
from app.services.embedding_service import EmbeddingService
from app.services.generation_service import GenerationService
from app.services.indexing_service import IndexingService
from app.services.query_service import QueryService
from app.services.reranking_service import RerankingService
from app.services.retrieval_service import RetrievalService
from app.services.sync_service import FolderWatcher, SyncService


class AppServices:
    """The whole service graph, built once at startup.

    Pass ``vector_repo`` to use a different vector store (tests use an
    in-memory one so they run without ChromaDB installed)."""

    def __init__(self, settings: Settings, vector_repo: VectorRepository | None = None):
        self.settings = settings
        self.embedding_service = EmbeddingService(settings)
        self.reranking_service = RerankingService(settings)
        self.vector_repo = vector_repo or ChromaVectorRepository(settings.vector_db_dir)
        self.bm25_repo = BM25Repository(settings.bm25_path, k1=settings.bm25_k1, b=settings.bm25_b)
        self.manifest_repo = ManifestRepository(settings.manifest_db_path)
        self.chunker_registry = ChunkerRegistry(settings)
        self.indexing_service = IndexingService(
            settings,
            self.chunker_registry,
            self.embedding_service,
            self.vector_repo,
            self.bm25_repo,
            self.manifest_repo,
        )
        self.retrieval_service = RetrievalService(
            settings, self.embedding_service, self.vector_repo, self.bm25_repo
        )
        self.retrieval_service.rebuild_bm25_cache()
        self.generation_service = GenerationService(settings)
        self.query_service = QueryService(
            settings,
            self.retrieval_service,
            self.reranking_service,
            self.generation_service,
        )
        self.sync_service = SyncService(settings, self.indexing_service, self.manifest_repo)
        self.sync_service.on_index_change = self.retrieval_service.rebuild_bm25_cache
        self.watcher = FolderWatcher(settings, self.sync_service)


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
