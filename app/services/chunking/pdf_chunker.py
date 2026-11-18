"""PDF chunker (.pdf) — extract text per page, chunk by page then section."""

from __future__ import annotations

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker, chunk_text_recursive


class PdfChunker(BaseChunker):
    extensions = ("pdf",)

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        texts: list[str] = []
        metadatas: list[dict] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            for piece in chunk_text_recursive(
                page_text,
                self.settings.chunk_size_words,
                self.settings.chunk_overlap_words,
            ):
                texts.append(piece)
                metadatas.append({"page": page_number})
        return self._make_chunks(document, texts, metadatas)
