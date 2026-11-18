"""Health + stats endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppServices, get_services
from app.models.schemas import HealthResponse, StatsResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(services: AppServices = Depends(get_services)) -> HealthResponse:
    llm_available = services.generation_service.provider.is_available()
    degraded = not llm_available or not services.embedding_service.loaded
    return HealthResponse(
        status="degraded" if degraded else "ok",
        llm_available=llm_available,
        ollama_model=services.settings.ollama_model,
        embedding_provider=services.settings.embedding_provider,
        embedding_model=services.settings.embedding_model,
        embedding_loaded=services.embedding_service.loaded,
        reranker_provider=services.settings.reranker_provider,
        reranker_model=services.settings.reranker_model,
        reranker_loaded=services.reranking_service.loaded,
        documents=len(services.manifest_repo.list_all()),
        chunks=services.vector_repo.count(),
        watcher_running=services.watcher.running,
        sync_status=services.sync_service.status,
    )


@router.get("/api/v1/stats", response_model=StatsResponse)
def stats(services: AppServices = Depends(get_services)) -> StatsResponse:
    return StatsResponse(
        documents_folder=services.settings.documents_dir,
        documents=len(services.manifest_repo.list_all()),
        chunks=services.vector_repo.count(),
        vector_store_documents=services.vector_repo.count(),
        bm25_documents=services.bm25_repo.index.size,
        vector_db_dir=services.settings.vector_db_dir,
    )
