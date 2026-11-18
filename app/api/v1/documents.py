"""Documents endpoints — list, inspect, sync, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import AppServices, get_services
from app.models.schemas import DocumentInfo, SyncResult

router = APIRouter()


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents(services: AppServices = Depends(get_services)) -> list[DocumentInfo]:
    return [
        DocumentInfo(
            id=d.id,
            path=d.path,
            file_type=d.file_type,
            chunk_count=d.chunk_count,
            sha256=d.sha256,
            indexed_at=d.indexed_at,
        )
        for d in services.manifest_repo.list_all()
    ]


@router.post("/documents/sync", response_model=SyncResult)
def sync_documents(services: AppServices = Depends(get_services)) -> SyncResult:
    result = services.sync_service.sync()
    services.retrieval_service.rebuild_bm25_cache()
    return result


@router.get("/documents/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str, services: AppServices = Depends(get_services)) -> DocumentInfo:
    document = services.manifest_repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    return DocumentInfo(
        id=document.id,
        path=document.path,
        file_type=document.file_type,
        chunk_count=document.chunk_count,
        sha256=document.sha256,
        indexed_at=document.indexed_at,
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, services: AppServices = Depends(get_services)) -> None:
    document = services.manifest_repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    services.indexing_service.remove_document(document)
    services.retrieval_service.rebuild_bm25_cache()
