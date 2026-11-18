"""Text chunkers (.md, .txt) — three selectable strategies.

- ``recursive``: paragraphs, then sentences, then words (with overlap).
- ``section``: split on markdown headings, carry the heading, split long
  sections at sentence boundaries (max ``section_max_words``). This is the
  approach from the section-chunking experiment that reached 91% strict
  recall@5 (vs 73% for fixed 200-word windows).
- ``fixed``: fixed-size word windows with overlap.
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import (
    BaseChunker,
    chunk_text_recursive,
    chunk_word_list,
    split_sentences,
    word_count,
    word_list,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class TextChunker(BaseChunker):
    extensions = ("md", "txt", "markdown")

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        text = self._decode(content)
        strategy = self.settings.text_chunk_strategy
        if strategy == "section":
            return self._chunk_section(document, text)
        if strategy == "fixed":
            return self._chunk_fixed(document, text)
        return self._chunk_recursive(document, text)

    def _chunk_recursive(self, document: Document, text: str) -> list[Chunk]:
        texts = chunk_text_recursive(
            text, self.settings.chunk_size_words, self.settings.chunk_overlap_words
        )
        return self._make_chunks(document, texts)

    def _chunk_fixed(self, document: Document, text: str) -> list[Chunk]:
        texts = chunk_word_list(
            word_list(text),
            self.settings.chunk_size_words,
            self.settings.chunk_overlap_words,
        )
        return self._make_chunks(document, texts)

    def _chunk_section(self, document: Document, text: str) -> list[Chunk]:
        """One chunk per markdown section, heading carried, long sections
        split at sentence boundaries to at most ``section_max_words``."""
        max_words = self.settings.section_max_words
        sections: list[tuple[str, str]] = []  # (heading, body)
        matches = list(_HEADING_RE.finditer(text))
        if not matches:
            # No headings: fall back to recursive chunking.
            return self._chunk_recursive(document, text)
        # Text before the first heading, if any.
        first = matches[0]
        if first.start() > 0 and text[: first.start()].strip():
            sections.append(("", text[: first.start()]))
        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((heading, text[start:end]))

        texts: list[str] = []
        metadatas: list[dict] = []
        for heading, body in sections:
            body = body.strip()
            if not body and not heading:
                continue
            prefix = f"{heading}\n" if heading else ""
            if word_count(body) <= max_words:
                texts.append(prefix + body)
                metadatas.append({"heading": heading} if heading else {})
                continue
            # Long section: split at sentence boundaries, keep heading on each.
            current: list[str] = []
            current_words = 0
            for sentence in split_sentences(body):
                sent_words = word_count(sentence)
                if current_words + sent_words > max_words and current:
                    texts.append(prefix + " ".join(current))
                    metadatas.append({"heading": heading} if heading else {})
                    current, current_words = [], 0
                current.append(sentence)
                current_words += sent_words
            if current:
                texts.append(prefix + " ".join(current))
                metadatas.append({"heading": heading} if heading else {})
        return self._make_chunks(document, texts, metadatas)
