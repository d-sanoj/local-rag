"""Retrieval tests — dense, sparse, hybrid against a small indexed corpus."""

from __future__ import annotations

from pathlib import Path

from app.repositories.bm25_repository import BM25Repository
from app.repositories.manifest_repository import ManifestRepository
from app.services.chunking.registry import ChunkerRegistry
from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import IndexingService
from app.services.retrieval_service import RetrievalService
from tests.conftest import InMemoryVectorRepo, make_settings


def _build(tmp_path: Path):
    settings = make_settings(tmp_path)
    vector_repo = InMemoryVectorRepo()
    bm25_repo = BM25Repository(settings.bm25_path, k1=settings.bm25_k1, b=settings.bm25_b)
    manifest_repo = ManifestRepository(settings.manifest_db_path)
    indexing = IndexingService(
        settings,
        ChunkerRegistry(settings),
        EmbeddingService(settings),
        vector_repo,
        bm25_repo,
        manifest_repo,
    )
    retrieval = RetrievalService(settings, EmbeddingService(settings), vector_repo, bm25_repo)
    return settings, vector_repo, indexing, retrieval


def _index(tmp_path: Path, files: dict[str, str]):
    settings, _vector_repo, indexing, retrieval = _build(tmp_path)
    docs = Path(settings.documents_dir)
    for name, content in files.items():
        path = docs / name
        path.write_text(content, encoding="utf-8")
        indexing.index_file(str(path), name)
    retrieval.rebuild_bm25_cache()
    return retrieval


def test_sparse_finds_exact_terms(tmp_path):
    retrieval = _index(
        tmp_path,
        {
            "cats.md": "# Cats\n\nCats are independent animals that sleep a lot.",
            "dogs.md": "# Dogs\n\nDogs are loyal animals that love walks.",
        },
    )
    results, stats = retrieval.search("cats sleep", strategy="sparse", top_k=2)
    assert results[0]["source"] == "cats.md"
    assert stats["strategy"] == "sparse"


def test_hybrid_returns_both_legs(tmp_path):
    retrieval = _index(
        tmp_path,
        {
            "cats.md": "# Cats\n\nCats are independent animals that sleep a lot.",
            "dogs.md": "# Dogs\n\nDogs are loyal animals that love walks.",
        },
    )
    results, stats = retrieval.search("loyal animals walks", strategy="hybrid", top_k=2)
    assert len(results) == 2
    assert stats["dense_candidates"] >= 1
    assert stats["sparse_candidates"] >= 1
    assert results[0]["source"] == "dogs.md"


def test_dense_uses_embeddings(tmp_path):
    retrieval = _index(
        tmp_path,
        {
            "cats.md": "# Cats\n\nCats are independent animals that sleep a lot.",
            "dogs.md": "# Dogs\n\nDogs are loyal animals that love walks.",
        },
    )
    results, _ = retrieval.search("cats", strategy="dense", top_k=1)
    assert len(results) == 1
    assert "score" in results[0]


def test_filter_by_source(tmp_path):
    retrieval = _index(
        tmp_path,
        {
            "cats.md": "# Cats\n\nCats are independent animals.",
            "dogs.md": "# Dogs\n\nDogs are loyal animals.",
        },
    )
    from app.models.schemas import Filters

    results, _ = retrieval.search(
        "animals", strategy="hybrid", top_k=5, filters=Filters(source="dogs.md")
    )
    assert all(r["source"] == "dogs.md" for r in results)
    assert len(results) == 1
