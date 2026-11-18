"""Sync tests — add / update / remove / unsupported, against a temp folder."""

from __future__ import annotations

from pathlib import Path

from app.repositories.bm25_repository import BM25Repository
from app.repositories.manifest_repository import ManifestRepository
from app.services.chunking.registry import ChunkerRegistry
from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import IndexingService
from app.services.sync_service import SyncService
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
    sync = SyncService(settings, indexing, manifest_repo)
    return settings, vector_repo, manifest_repo, sync


def _write(documents_dir: Path, name: str, content: str) -> Path:
    path = documents_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_sync_adds_new_files(tmp_path):
    settings, vector_repo, manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    _write(docs, "a.md", "# Hello\n\nThis is a test document about cats.")
    _write(docs, "b.txt", "Dogs are loyal animals.")
    result = sync.sync()
    assert result.added == ["a.md", "b.txt"]
    assert result.documents == 2
    assert vector_repo.count() == 2
    assert len(manifest_repo.list_all()) == 2


def test_sync_updates_changed_files(tmp_path):
    settings, vector_repo, _manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    path = _write(docs, "a.md", "# Hello\n\nOriginal content here.")
    sync.sync()
    path.write_text("# Hello\n\nCompletely different content now.", encoding="utf-8")
    result = sync.sync()
    assert result.updated == ["a.md"]
    assert result.added == []
    assert vector_repo.count() == 1  # old chunks replaced, not duplicated


def test_sync_removes_deleted_files(tmp_path):
    settings, vector_repo, manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    _write(docs, "a.md", "# A\n\nContent A.")
    path_b = _write(docs, "b.md", "# B\n\nContent B.")
    sync.sync()
    assert vector_repo.count() == 2
    path_b.unlink()
    result = sync.sync()
    assert result.removed == ["b.md"]
    assert vector_repo.count() == 1
    assert len(manifest_repo.list_all()) == 1


def test_sync_skips_unsupported(tmp_path):
    settings, vector_repo, _manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    _write(docs, "a.md", "# A\n\nContent.")
    _write(docs, "weird.xyz", "nonsense")
    result = sync.sync()
    assert result.added == ["a.md"]
    assert result.skipped_unsupported == ["weird.xyz"]
    assert vector_repo.count() == 1


def test_sync_idempotent(tmp_path):
    settings, vector_repo, _manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    _write(docs, "a.md", "# A\n\nContent.")
    sync.sync()
    result = sync.sync()
    assert result.added == [] and result.updated == [] and result.removed == []
    assert vector_repo.count() == 1


def test_index_one_and_remove_one(tmp_path):
    settings, vector_repo, manifest_repo, sync = _build(tmp_path)
    docs = Path(settings.documents_dir)
    path = _write(docs, "a.md", "# A\n\nContent.")
    sync.index_one(str(path))
    assert vector_repo.count() == 1
    sync.remove_one(str(path))
    assert vector_repo.count() == 0
    assert manifest_repo.list_all() == []
