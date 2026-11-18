"""Chunk model — one retrievable unit produced by a chunker."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field


def chunk_id_for(document_id: str, index: int) -> str:
    """Stable chunk id: sha256 of document id + chunk index."""
    return hashlib.sha256(f"{document_id}:{index}".encode()).hexdigest()[:32]


class Chunk(BaseModel):
    """A single chunk of a document, ready to embed and store."""

    id: str
    document_id: str
    source: str = Field(description="Path relative to the documents folder")
    index: int = Field(description="Chunk index within its document")
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        document_id: str,
        source: str,
        index: int,
        text: str,
        **metadata: Any,
    ) -> Chunk:
        return cls(
            id=chunk_id_for(document_id, index),
            document_id=document_id,
            source=source,
            index=index,
            text=text,
            metadata=metadata,
        )
