"""Embedding service — turns chunk text into vectors.

Provider interface so the model can be swapped. Default is
BAAI/bge-small-en-v1.5 via sentence-transformers (~130MB, 384-dim). The
model downloads from HuggingFace on first use and caches locally. A
deterministic dummy provider exists for tests and for running the service
without downloading models.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import EmbeddingError, ModelNotLoadedError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DummyEmbeddingProvider:
    """Deterministic hash-based embeddings. For tests only — not semantic."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimension
            for word in text.lower().split():
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[h % self.dimension] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class SentenceTransformerEmbeddingProvider:
    """BAAI/bge-small-en-v1.5 (or the configured model) via sentence-transformers.

    The heavy imports happen lazily inside ``embed`` so the service can
    start (and report health) without torch installed.
    """

    def __init__(self, model_name: str, dimension: int = 384):
        self.model_name = model_name
        self.dimension = dimension
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ModelNotLoadedError(
                    "sentence-transformers is not installed; run `pip install -r requirements.txt`"
                ) from exc
            logger.info("Loading embedding model %s ...", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model %s loaded", self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._load()
            vectors = model.encode(texts, normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        except ModelNotLoadedError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"embedding failed: {exc}") from exc


class EmbeddingService:
    """Owns the provider; the rest of the app only talks to this class."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.embedding_provider == "dummy":
            self.provider: EmbeddingProvider = DummyEmbeddingProvider(settings.embedding_dimension)
            self.loaded = True
        else:
            self.provider = SentenceTransformerEmbeddingProvider(
                settings.embedding_model, settings.embedding_dimension
            )
            self.loaded = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.provider.embed(texts)
        self.loaded = True
        return vectors

    def embed_query(self, query: str) -> list[float]:
        # bge models expect an instruction prefix for queries.
        if self.settings.embedding_model.startswith("BAAI/bge-"):
            query = f"Represent this sentence for searching relevant passages: {query}"
        return self.embed([query])[0]
