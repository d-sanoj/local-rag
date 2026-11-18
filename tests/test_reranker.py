"""Reranking service tests (dummy provider — no model download)."""

from __future__ import annotations

from app.services.reranking_service import RerankingService
from tests.conftest import make_settings


def test_reranking_service_dummy(tmp_path):
    settings = make_settings(tmp_path, reranker_provider="dummy")
    service = RerankingService(settings)
    assert service.loaded is True
    chunks = [{"text": "alpha"}, {"text": "beta"}]
    out = service.rerank("query", chunks)
    assert len(out) == 2
    assert out[0]["score"] >= out[1]["score"]


def test_reranking_service_empty(tmp_path):
    settings = make_settings(tmp_path, reranker_provider="dummy")
    service = RerankingService(settings)
    assert service.rerank("query", []) == []
