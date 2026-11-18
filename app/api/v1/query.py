"""Query endpoint — retrieve → rerank → generate, with citations."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppServices, get_services
from app.models.schemas import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, services: AppServices = Depends(get_services)) -> QueryResponse:
    return services.query_service.query(request)
