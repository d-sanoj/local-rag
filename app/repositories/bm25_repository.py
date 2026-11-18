"""BM25 repository — sparse retrieval over chunk texts.

Classic BM25 (k1=1.5, b=0.75 by default, matching the earlier retriever
experiment). The index is persisted as JSON so it survives restarts, and
rebuilt from the vector store after every sync.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """In-memory BM25 over a corpus of (chunk_id, text) pairs."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_lengths: list[int] = []
        self.term_freqs: list[Counter] = []
        self.doc_freq: Counter = Counter()
        self.avgdl: float = 0.0

    @property
    def size(self) -> int:
        return len(self.doc_ids)

    def build(self, documents: list[tuple[str, str]]) -> None:
        """Build the index from (chunk_id, text) pairs."""
        self.doc_ids = [doc_id for doc_id, _ in documents]
        self.doc_lengths = []
        self.term_freqs = []
        self.doc_freq = Counter()
        total_length = 0
        for _doc_id, text in documents:
            tokens = tokenize(text)
            freqs = Counter(tokens)
            self.term_freqs.append(freqs)
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)
            for term in freqs:
                self.doc_freq[term] += 1
        self.avgdl = total_length / len(documents) if documents else 0.0

    def _idf(self, term: str) -> float:
        n = len(self.doc_ids)
        df = self.doc_freq.get(term, 0)
        # Robertson's IDF with the standard +1 smoothing.
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[tuple[str, float]]:
        """Score every document for the query; returns (chunk_id, score) desc."""
        if not self.doc_ids:
            return []
        query_terms = tokenize(query)
        scores = [0.0] * len(self.doc_ids)
        for term in set(query_terms):
            idf = self._idf(term)
            for i, freqs in enumerate(self.term_freqs):
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                dl = self.doc_lengths[i]
                denom = (
                    tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                    if self.avgdl
                    else tf + self.k1
                )
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        ranked = sorted(
            ((self.doc_ids[i], scores[i]) for i in range(len(self.doc_ids))),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [(doc_id, score) for doc_id, score in ranked if score > 0]

    def save(self, path: str) -> None:
        payload = {
            "k1": self.k1,
            "b": self.b,
            "doc_ids": self.doc_ids,
            "doc_lengths": self.doc_lengths,
            "term_freqs": [dict(c) for c in self.term_freqs],
            "doc_freq": dict(self.doc_freq),
            "avgdl": self.avgdl,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, path: str) -> BM25Index:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        index = cls(k1=payload["k1"], b=payload["b"])
        index.doc_ids = payload["doc_ids"]
        index.doc_lengths = payload["doc_lengths"]
        index.term_freqs = [Counter(d) for d in payload["term_freqs"]]
        index.doc_freq = Counter(payload["doc_freq"])
        index.avgdl = payload["avgdl"]
        return index


class BM25Repository:
    """Owns one BM25Index: build from chunks, persist, reload, score."""

    def __init__(self, persist_path: str, k1: float = 1.5, b: float = 0.75):
        self.persist_path = persist_path
        self.index = BM25Index(k1=k1, b=b)
        if os.path.exists(persist_path):
            try:
                self.index = BM25Index.load(persist_path)
                logger.info("BM25 index loaded from %s (%d docs)", persist_path, self.index.size)
            except Exception as exc:  # noqa: BLE001 — corrupted snapshot: rebuild from scratch
                logger.warning("BM25 snapshot unreadable (%s); rebuilding", exc)

    def rebuild(self, documents: list[tuple[str, str]]) -> None:
        self.index.build(documents)
        self.index.save(self.persist_path)
        logger.info("BM25 index rebuilt: %d chunks", self.index.size)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        return self.index.score(query)[:top_k]
