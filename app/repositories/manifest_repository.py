"""Manifest repository — SQLite record of what is indexed.

One row per file in the watched folder: path, SHA-256, mtime, chunk count.
Sync compares the folder against this manifest to find added / changed /
removed files. SQLite is used (not a JSON file) so concurrent reads during
a sync are safe.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    absolute_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    mtime REAL NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL
);
"""


class ManifestRepository:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        with sqlite3.connect(db_path) as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert(self, document: Document) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, path, absolute_path, file_type, sha256, mtime, chunk_count, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     sha256=excluded.sha256, mtime=excluded.mtime,
                     chunk_count=excluded.chunk_count, indexed_at=excluded.indexed_at""",
                (
                    document.id,
                    document.path,
                    document.absolute_path,
                    document.file_type,
                    document.sha256,
                    document.mtime,
                    document.chunk_count,
                    document.indexed_at.isoformat(),
                ),
            )
            conn.commit()

    def get(self, document_id: str) -> Document | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return self._row_to_document(row) if row else None

    def get_by_path(self, path: str) -> Document | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE path = ?", (path,)).fetchone()
        return self._row_to_document(row) if row else None

    def list_all(self) -> list[Document]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY path").fetchall()
        return [self._row_to_document(r) for r in rows]

    def delete(self, document_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            path=row["path"],
            absolute_path=row["absolute_path"],
            file_type=row["file_type"],
            sha256=row["sha256"],
            mtime=row["mtime"],
            chunk_count=row["chunk_count"],
            indexed_at=datetime.fromisoformat(row["indexed_at"]),
        )
