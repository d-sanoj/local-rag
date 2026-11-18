"""Reranking — cross-encoder scoring, Reciprocal Rank Fusion, MMR.

- ``reciprocal_rank_fusion`` merges dense and sparse rankings (RRF, k=60).
- ``CrossEncoderReranker`` scores (query, chunk) pairs with
  cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, standard small reranker).
- ``maximal_marginal_relevance`` reorders for diversity (lambda=0.7).
- ``DummyReranker`` keeps input order with decreasing scores (tests).
"""

from __future__ import annotations

import math
from typing import Any, Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Fuse ranked id lists with RRF. Returns (id, score) sorted desc."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def maximal_marginal_relevance(
    query_embedding: list[float],
    candidates: list[dict[str, Any]],
    lambda_: float = 0.7,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """MMR: greedily pick candidates that are relevant AND dissimilar to
    already-picked ones. Candidates carry an ``embedding`` key when available;
    without embeddings it falls back to the input order."""
    if not candidates:
        return []
    if top_k is None:
        top_k = len(candidates)
    if not any(c.get("embedding") for c in candidates):
        return candidates[:top_k]
    selected: list[dict[str, Any]] = []
    remaining = list(candidates)
    while remaining and len(selected) < top_k:
        best, best_score = None, -float("inf")
        for cand in remaining:
            emb = cand.get("embedding") or []
            relevance = _cosine(query_embedding, emb) if emb else 0.0
            redundancy = 0.0
            for picked in selected:
                pemb = picked.get("embedding") or []
                if pemb:
                    redundancy = max(redundancy, _cosine(emb, pemb))
            score = lambda_ * relevance - (1 - lambda_) * redundancy
            if score > best_score:
                best, best_score = cand, score
        selected.append(best)  # type: ignore[arg-type]
        remaining.remove(best)
    return selected


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class DummyReranker:
    """Keeps order, assigns decreasing scores. Tests only."""

    def rerank(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for i, chunk in enumerate(chunks):
            item = dict(chunk)
            item["score"] = 1.0 - (i * 0.01)
            out.append(item)
        return out


class CrossEncoderReranker:
    """cross-encoder/ms-marco-MiniLM-L-6-v2 via sentence-transformers."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self.loaded = False

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker %s ...", self.model_name)
            self._model = CrossEncoder(self.model_name)
            self.loaded = True
            logger.info("Reranker %s loaded", self.model_name)
        return self._model

    def rerank(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not chunks:
            return []
        model = self._load()
        pairs = [(query, c.get("text", "")) for c in chunks]
        scores = model.predict(pairs)
        scored = sorted(
            (dict(c, score=float(s)) for c, s in zip(chunks, scores, strict=True)),
            key=lambda c: c["score"],
            reverse=True,
        )
        return scored


class RerankingService:
    """Owns the reranker; the rest of the app only talks to this class."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.reranker_provider == "dummy":
            self.reranker: Reranker = DummyReranker()
            self.loaded = True
        else:
            self.reranker = CrossEncoderReranker(settings.reranker_model)
            self.loaded = False

    def rerank(self, query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = self.reranker.rerank(query, chunks)
        self.loaded = True
        return result
