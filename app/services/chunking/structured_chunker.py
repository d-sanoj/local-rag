"""Structured-data chunker (.csv, .json).

One chunk per row (CSV) or per record (JSON), with the field names carried
in the chunk text so the values stay interpretable on their own.
"""

from __future__ import annotations

import csv
import io
import json

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker


class StructuredChunker(BaseChunker):
    extensions = ("csv", "json")

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        if document.file_type == "csv":
            return self._chunk_csv(document, content)
        return self._chunk_json(document, content)

    def _chunk_csv(self, document: Document, content: bytes) -> list[Chunk]:
        text = self._decode(content)
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return []
        texts: list[str] = []
        metadatas: list[dict] = []
        for row_number, row in enumerate(reader, start=1):
            parts = [f"{k}: {v}" for k, v in row.items() if v not in (None, "")]
            if not parts:
                continue
            texts.append(", ".join(parts))
            metadatas.append({"row": row_number})
        return self._make_chunks(document, texts, metadatas)

    def _chunk_json(self, document: Document, content: bytes) -> list[Chunk]:
        data = json.loads(self._decode(content))
        texts: list[str] = []
        metadatas: list[dict] = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                texts.append(self._record_text(item))
                metadatas.append({"record": i})
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    for i, item in enumerate(value if isinstance(value, list) else [value]):
                        texts.append(f"{key}: {self._record_text(item)}")
                        metadatas.append({"key": key, "record": i})
                else:
                    texts.append(f"{key}: {value}")
                    metadatas.append({"key": key})
        else:
            texts.append(str(data))
        return self._make_chunks(document, texts, metadatas)

    @staticmethod
    def _record_text(item: object) -> str:
        if isinstance(item, dict):
            return ", ".join(f"{k}: {v}" for k, v in item.items())
        if isinstance(item, list):
            return json.dumps(item)
        return str(item)
