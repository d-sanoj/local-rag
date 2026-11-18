"""Image chunker (.png, .jpg, .jpeg, .webp, .gif, .bmp, .tiff).

OCR with Tesseract (via pytesseract). The chunk text is the OCR text plus
image metadata; if OCR finds nothing, a chunk noting the image with no
extractable text is stored so the file is still visible in the index.
"""

from __future__ import annotations

import io

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker


class ImageChunker(BaseChunker):
    extensions = ("png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "tif")

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        from PIL import Image

        image = Image.open(io.BytesIO(content))
        width, height = image.size
        text = self._ocr(image)
        if text:
            chunk_text = f"[Image: {document.path}]\n{text}"
        else:
            chunk_text = (
                f"[Image: {document.path} — no extractable text found by OCR. "
                f"Dimensions: {width}x{height}.]"
            )
        return self._make_chunks(
            document,
            [chunk_text],
            [{"width": width, "height": height, "ocr_chars": len(text)}],
        )

    @staticmethod
    def _ocr(image) -> str:
        import pytesseract

        try:
            return (pytesseract.image_to_string(image) or "").strip()
        except Exception:  # noqa: BLE001 — OCR failure means "no text", not a crash
            return ""
