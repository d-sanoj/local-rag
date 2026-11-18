"""Code chunker (.py, .js, .ts, .jsx, .tsx, .java, .go, .rb, .rs, .c, .cpp, .h).

Splits on top-level function/class boundaries with a robust regex heuristic
(no AST dependency), keeping each block's docstring/comment with it. Blocks
over the size limit fall back to recursive text chunking. Files with no
recognisable blocks fall back entirely to recursive chunking.
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker, chunk_text_recursive, word_count

# Extension -> pattern for a top-level block start. The pattern is tried
# only for its own language: trying every pattern and keeping the most
# matches favours the most permissive one, not the right one.
_JS_PATTERN = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)"
    r"|^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)"
    r"|^(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(",
    re.MULTILINE,
)
_C_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_*\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{",
    re.MULTILINE,
)
_BLOCK_PATTERNS: dict[str, re.Pattern] = {
    "py": re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "js": _JS_PATTERN,
    "ts": _JS_PATTERN,
    "jsx": _JS_PATTERN,
    "tsx": _JS_PATTERN,
    "java": re.compile(
        r"^(?:public|private|protected)?\s*(?:static\s+|final\s+|abstract\s+)*"
        r"(?:class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|^(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        re.MULTILINE,
    ),
    "go": re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "rs": re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "rb": re.compile(r"^(?:def|class|module)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
    "c": _C_PATTERN,
    "cpp": _C_PATTERN,
    "h": _C_PATTERN,
    "hpp": _C_PATTERN,
}


class CodeChunker(BaseChunker):
    extensions = (
        "py",
        "js",
        "ts",
        "jsx",
        "tsx",
        "java",
        "go",
        "rb",
        "rs",
        "c",
        "cpp",
        "h",
        "hpp",
    )

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        text = self._decode(content)
        blocks = self._split_blocks(text, document.file_type)
        if not blocks:
            texts = chunk_text_recursive(
                text, self.settings.chunk_size_words, self.settings.chunk_overlap_words
            )
            return self._make_chunks(document, texts)
        texts: list[str] = []
        metadatas: list[dict] = []
        for name, kind, block_text in blocks:
            if word_count(block_text) <= self.settings.section_max_words:
                texts.append(block_text)
                metadatas.append({"symbol": name, "kind": kind})
            else:
                for piece in chunk_text_recursive(
                    block_text,
                    self.settings.chunk_size_words,
                    self.settings.chunk_overlap_words,
                ):
                    texts.append(piece)
                    metadatas.append({"symbol": name, "kind": kind})
        return self._make_chunks(document, texts, metadatas)

    def _split_blocks(self, text: str, extension: str) -> list[tuple[str, str, str]]:
        """Return [(name, kind, block_text)] for top-level definitions,
        using only the pattern for this file's language."""
        pattern = _BLOCK_PATTERNS.get(extension)
        if pattern is None:
            return []
        found: list[tuple[int, str, str]] = []
        for match in pattern.finditer(text):
            name = next((g for g in match.groups() if g), "unknown")
            kind = "class" if "class" in match.group(0) else "function"
            found.append((match.start(), name, kind))
        if not found:
            return []
        blocks: list[tuple[str, str, str]] = []
        for i, (start, name, kind) in enumerate(found):
            end = found[i + 1][0] if i + 1 < len(found) else len(text)
            block_text = text[start:end].rstrip()
            # Drop a leading file header (imports, license) from the first block.
            if i == 0 and start > 0:
                header = text[:start].strip()
                if header:
                    blocks.append(("", "header", header))
            if block_text.strip():
                blocks.append((name, kind, block_text))
        return blocks
