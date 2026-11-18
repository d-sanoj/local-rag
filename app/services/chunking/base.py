"""Chunker base class and shared text helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.core.exceptions import IndexingError
from app.models.chunk import Chunk
from app.models.document import Document

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_WORD_RE = re.compile(r"\S+")


def word_list(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def word_count(text: str) -> int:
    return len(word_list(text))


def split_sentences(text: str) -> list[str]:
    """Split text into sentences; falls back to newlines, then the whole text."""
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_RE.split(text)
    out: list[str] = []
    for part in parts:
        for line in part.splitlines():
            line = line.strip()
            if line:
                out.append(line)
    return out


def chunk_word_list(words: list[str], size: int, overlap: int) -> list[str]:
    """Fixed-size windows over a word list, with overlap. Size/overlap in words."""
    if not words:
        return []
    if size <= 0:
        raise ValueError("chunk size must be > 0")
    overlap = max(0, min(overlap, size - 1))
    step = size - overlap
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def chunk_text_recursive(text: str, size_words: int, overlap_words: int) -> list[str]:
    """Recursive chunking: paragraphs, then sentences, then words.

    Paragraphs are accumulated until the target size; an oversized
    paragraph is split into sentences; an oversized sentence into words.
    """
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    def flush() -> None:
        nonlocal current, current_words
        if current:
            chunks.append(" ".join(current))
            current, current_words = [], 0

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for paragraph in paragraphs:
        para_words = word_count(paragraph)
        if para_words <= size_words:
            if current_words + para_words > size_words and current:
                # Carry overlap: last `overlap_words` words of the flushed chunk.
                tail = word_list(" ".join(current))[-overlap_words:] if overlap_words else []
                flush()
                current = tail[:]
                current_words = len(tail)
            current.append(paragraph)
            current_words += para_words
            continue
        # Oversized paragraph: split into sentences.
        flush()
        for sentence in split_sentences(paragraph):
            sent_words = word_count(sentence)
            if sent_words <= size_words:
                if current_words + sent_words > size_words and current:
                    tail = word_list(" ".join(current))[-overlap_words:] if overlap_words else []
                    flush()
                    current = tail[:]
                    current_words = len(tail)
                current.append(sentence)
                current_words += sent_words
            else:
                flush()
                chunks.extend(chunk_word_list(word_list(sentence), size_words, overlap_words))
    flush()
    return [c for c in chunks if c.strip()]


class BaseChunker(ABC):
    """One chunker per file type. Returns chunks with text + metadata."""

    extensions: tuple[str, ...] = ()

    @abstractmethod
    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        """Chunk a file's raw bytes into retrievable units."""

    def _decode(self, content: bytes) -> str:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")

    def _make_chunks(
        self, document: Document, texts: list[str], metadatas: list[dict] | None = None
    ) -> list[Chunk]:
        out: list[Chunk] = []
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            meta = dict(metadatas[i]) if metadatas and i < len(metadatas) else {}
            meta.setdefault("file_type", document.file_type)
            out.append(
                Chunk.create(
                    document_id=document.id,
                    source=document.path,
                    index=i,
                    text=text.strip(),
                    **meta,
                )
            )
        return out


def read_file_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise IndexingError(f"cannot read {path}: {exc}") from exc
