"""Search endpoint — ranked chunks only, no generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppServices, get_services
from app.models.schemas import SearchRequest, SearchResponse

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, services: AppServices = Depends(get_services)) -> SearchResponse:
    return services.query_service.search(request)
