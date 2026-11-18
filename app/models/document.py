"""Document model — one row per file in the watched folder."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field


def document_id_for(relative_path: str) -> str:
    """Stable id for a document: sha256 of its path relative to the folder."""
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:32]


class Document(BaseModel):
    """A file in the documents folder, as recorded in the manifest."""

    id: str = Field(description="sha256 of the path relative to the documents folder")
    path: str = Field(description="Path relative to the documents folder")
    absolute_path: str
    file_type: str = Field(description="Lowercase extension without the dot, e.g. 'pdf'")
    sha256: str = Field(description="SHA-256 of the file bytes at index time")
    mtime: float = Field(description="Filesystem mtime at index time")
    chunk_count: int = 0
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_path(
        cls, relative_path: str, absolute_path: str, sha256: str, mtime: float
    ) -> Document:
        return cls(
            id=document_id_for(relative_path),
            path=relative_path,
            absolute_path=absolute_path,
            file_type=relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else "",
            sha256=sha256,
            mtime=mtime,
        )
