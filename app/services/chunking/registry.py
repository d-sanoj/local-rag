"""Chunker registry — dispatches a file to its chunker by extension."""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import UnsupportedFileTypeError
from app.services.chunking.base import BaseChunker
from app.services.chunking.code_chunker import CodeChunker
from app.services.chunking.docx_chunker import DocxChunker
from app.services.chunking.html_chunker import HtmlChunker
from app.services.chunking.image_chunker import ImageChunker
from app.services.chunking.media_chunker import MediaChunker
from app.services.chunking.pdf_chunker import PdfChunker
from app.services.chunking.structured_chunker import StructuredChunker
from app.services.chunking.text_chunker import TextChunker


class ChunkerRegistry:
    """Maps file extensions to chunkers. Unknown extensions raise a clear error."""

    def __init__(self, settings: Settings):
        self._chunkers: dict[str, BaseChunker] = {}
        for chunker_cls in (
            TextChunker,
            CodeChunker,
            PdfChunker,
            DocxChunker,
            HtmlChunker,
            StructuredChunker,
            ImageChunker,
            MediaChunker,
        ):
            chunker = chunker_cls(settings)
            for ext in chunker.extensions:
                self._chunkers[ext] = chunker

    @property
    def supported_extensions(self) -> set[str]:
        return set(self._chunkers)

    def is_supported(self, extension: str) -> bool:
        return extension.lower() in self._chunkers

    def get(self, extension: str) -> BaseChunker:
        chunker = self._chunkers.get(extension.lower())
        if chunker is None:
            raise UnsupportedFileTypeError(
                f"no chunker for '.{extension}' — supported: "
                f"{', '.join(sorted(self.supported_extensions))}"
            )
        return chunker
