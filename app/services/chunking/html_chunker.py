"""HTML chunker (.html, .htm) — strip tags/scripts, chunk by heading/paragraph."""

from __future__ import annotations

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker, chunk_text_recursive, word_count


class HtmlChunker(BaseChunker):
    extensions = ("html", "htm")

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        # Walk headings and paragraphs in document order.
        sections: list[tuple[str, list[str]]] = []
        current_heading = ""
        current_paras: list[str] = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = element.get_text(" ", strip=True)
            if not text:
                continue
            if element.name.startswith("h"):
                if current_paras:
                    sections.append((current_heading, current_paras))
                current_heading, current_paras = text, []
            else:
                current_paras.append(text)
        if current_paras:
            sections.append((current_heading, current_paras))
        if not sections:  # No structure found: use the whole visible text.
            body = soup.get_text("\n", strip=True)
            if not body:
                return []
            sections.append(("", [body]))

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
