"""Word chunker (.docx) — chunk by paragraph, grouped under headings."""

from __future__ import annotations

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker, chunk_text_recursive, word_count

_HEADING_STYLES = {"Heading 1", "Heading 2", "Heading 3", "Title"}


class DocxChunker(BaseChunker):
    extensions = ("docx",)

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        import io

        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(content))
        sections: list[tuple[str, list[str]]] = []
        current_heading = ""
        current_paras: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style.name in _HEADING_STYLES:
                if current_paras:
                    sections.append((current_heading, current_paras))
                current_heading, current_paras = text, []
            else:
                current_paras.append(text)
        if current_paras:
            sections.append((current_heading, current_paras))

        texts: list[str] = []
        metadatas: list[dict] = []
        for heading, paras in sections:
            body = "\n\n".join(paras)
            prefix = f"{heading}\n" if heading else ""
            if word_count(body) <= self.settings.section_max_words:
                texts.append(prefix + body)
                metadatas.append({"heading": heading} if heading else {})
            else:
                for piece in chunk_text_recursive(
                    body,
                    self.settings.chunk_size_words,
                    self.settings.chunk_overlap_words,
                ):
                    texts.append(prefix + piece)
                    metadatas.append({"heading": heading} if heading else {})
        return self._make_chunks(document, texts, metadatas)
