"""API tests — full HTTP round trips with the real service graph and an
in-memory vector repo (no ChromaDB, no models)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AppServices
from app.main import create_app
from tests.conftest import InMemoryVectorRepo, make_settings


@pytest.fixture
def client(tmp_path):
    settings = make_settings(tmp_path)
    services = AppServices(settings, vector_repo=InMemoryVectorRepo())
    # Index one document through the real pipeline.
    docs = Path(settings.documents_dir)
    path = docs / "guide.md"
    path.write_text(
        "# Local RAG\n\nLocal RAG answers questions over your own documents. "
        "It uses hybrid retrieval and a cross-encoder reranker.\n",
        encoding="utf-8",
    )
    services.indexing_service.index_file(str(path), "guide.md")
    services.retrieval_service.rebuild_bm25_cache()
    app = create_app(settings, services=services)
    with TestClient(app) as client:
        yield client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 1
    assert body["chunks"] == 1
    assert body["embedding_provider"] == "dummy"
    # The echo provider is always available, so the status is ok here.
    assert body["llm_available"] is True
    assert body["status"] == "ok"


def test_stats(client):
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 1
    assert body["chunks"] == 1
    assert body["bm25_documents"] == 1


def test_list_documents(client):
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["path"] == "guide.md"
    assert docs[0]["chunk_count"] == 1


def test_search_returns_ranked_chunks(client):
    response = client.post(
        "/api/v1/search",
        json={"query": "hybrid retrieval reranker", "strategy": "hybrid", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "hybrid"
    assert len(body["results"]) >= 1
    assert "hybrid retrieval" in body["results"][0]["text"]
    assert body["results"][0]["rank"] == 1


def test_query_returns_answer_with_sources(client):
    response = client.post(
        "/api/v1/query",
        json={"question": "What is local RAG?", "strategy": "hybrid", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What is local RAG?"
    assert body["answer"]  # echo provider returns a canned answer
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["source"] == "guide.md"


def test_search_validation_error(client):
    response = client.post("/api/v1/search", json={"query": ""})
    assert response.status_code == 422


def test_get_unknown_document_404(client):
    response = client.get("/api/v1/documents/does-not-exist")
    assert response.status_code == 404


def test_delete_document(client):
    docs = client.get("/api/v1/documents").json()
    doc_id = docs[0]["id"]
    response = client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 204
    assert client.get("/api/v1/documents").json() == []
    assert client.get("/api/v1/stats").json()["chunks"] == 0


def test_manual_sync(client):
    response = client.post("/api/v1/documents/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 1
    assert body["added"] == []  # nothing changed since indexing
