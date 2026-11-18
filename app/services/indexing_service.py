"""Indexing service — one file in, chunks + embeddings + vector rows out."""

from __future__ import annotations

import hashlib
import os

from app.core.config import Settings
from app.core.exceptions import IndexingError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.models.document import Document
from app.repositories.bm25_repository import BM25Repository
from app.repositories.manifest_repository import ManifestRepository
from app.repositories.vector_repository import VectorRepository
from app.services.chunking.base import read_file_bytes
from app.services.chunking.registry import ChunkerRegistry
from app.services.embedding_service import EmbeddingService

logger = get_logger(__name__)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IndexingService:
    """Indexes a single file: chunk → embed → upsert → manifest → BM25."""

    def __init__(
        self,
        settings: Settings,
        chunker_registry: ChunkerRegistry,
        embedding_service: EmbeddingService,
        vector_repo: VectorRepository,
        bm25_repo: BM25Repository,
        manifest_repo: ManifestRepository,
    ):
        self.settings = settings
        self.chunker_registry = chunker_registry
        self.embedding_service = embedding_service
        self.vector_repo = vector_repo
        self.bm25_repo = bm25_repo
        self.manifest_repo = manifest_repo

    def index_file(
        self, absolute_path: str, relative_path: str, rebuild_bm25: bool = True
    ) -> Document:
        """(Re-)index one file. Deletes its old chunks first, so a re-index
        never leaves stale chunks behind. Pass ``rebuild_bm25=False`` when
        indexing many files in a row and call :meth:`rebuild_bm25` once at
        the end instead."""
        extension = relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else ""
        if not self.chunker_registry.is_supported(extension):
            raise UnsupportedFileTypeError(f".{extension} is not a supported type")
        file_hash = sha256_file(absolute_path)
        mtime = os.path.getmtime(absolute_path)
        document = Document.from_path(relative_path, absolute_path, file_hash, mtime)
        content = read_file_bytes(absolute_path)
        chunker = self.chunker_registry.get(extension)
        try:
            chunks = chunker.chunk(document, content)
        except Exception as exc:
            raise IndexingError(f"chunking {relative_path} failed: {exc}") from exc
        if not chunks:
            logger.warning("No chunks produced for %s — indexed as empty", relative_path)
        # Remove stale chunks, then insert the new ones.
        self.vector_repo.delete_by_document(document.id)
        if chunks:
            embeddings = self.embedding_service.embed([c.text for c in chunks])
            self.vector_repo.upsert(chunks, embeddings)
        document.chunk_count = len(chunks)
        self.manifest_repo.upsert(document)
        if rebuild_bm25:
            self.rebuild_bm25()
        logger.info("Indexed %s: %d chunks", relative_path, len(chunks))
        return document

    def remove_document(self, document: Document, rebuild_bm25: bool = True) -> None:
        self.vector_repo.delete_by_document(document.id)
        self.manifest_repo.delete(document.id)
        if rebuild_bm25:
            self.rebuild_bm25()
        logger.info("Removed %s from the index", document.path)

    def rebuild_bm25(self) -> None:
        records = self.vector_repo.get_all()
        self.bm25_repo.rebuild([(r["id"], r["text"]) for r in records])


def build_document(absolute_path: str, documents_dir: str) -> Document:
    """Build a Document record (no indexing) for a path in the folder."""
    relative_path = os.path.relpath(absolute_path, documents_dir)
    return Document.from_path(
        relative_path,
        absolute_path,
        sha256_file(absolute_path),
        os.path.getmtime(absolute_path),
    )
