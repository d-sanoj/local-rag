"""Configuration for local-rag.

All settings come from environment variables (or a ``.env`` file in the
project root) with the defaults below. No setting is read from anywhere
else — in particular, the only document source is ``documents_dir``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no third-party dependency)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            os.environ.setdefault(key, value)


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """Every tunable of the service, with production-safe defaults."""

    # -- the one and only document source ---------------------------------
    documents_dir: str = _env("LOCAL_RAG_DOCUMENTS_DIR", "data/documents")
    # -- local stores ------------------------------------------------------
    vector_db_dir: str = _env("LOCAL_RAG_VECTOR_DB_DIR", "data/chroma")
    manifest_db_path: str = _env("LOCAL_RAG_MANIFEST_DB", "data/manifest.db")
    bm25_path: str = _env("LOCAL_RAG_BM25_PATH", "data/bm25.json")
    # -- embedding model ---------------------------------------------------
    embedding_provider: str = _env("LOCAL_RAG_EMBEDDING_PROVIDER", "sentence-transformers")
    embedding_model: str = _env("LOCAL_RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    embedding_dimension: int = _env_int("LOCAL_RAG_EMBEDDING_DIMENSION", 384)
    # -- reranker ----------------------------------------------------------
    reranker_provider: str = _env("LOCAL_RAG_RERANKER_PROVIDER", "cross-encoder")
    reranker_model: str = _env("LOCAL_RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    # -- generation LLM ----------------------------------------------------
    llm_provider: str = _env("LOCAL_RAG_LLM_PROVIDER", "ollama")
    ollama_base_url: str = _env("LOCAL_RAG_OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = _env("LOCAL_RAG_OLLAMA_MODEL", "llama3.2:3b")
    llm_temperature: float = _env_float("LOCAL_RAG_LLM_TEMPERATURE", 0.1)
    # -- chunking ----------------------------------------------------------
    text_chunk_strategy: str = _env("LOCAL_RAG_TEXT_CHUNK_STRATEGY", "section")
    chunk_size_words: int = _env_int("LOCAL_RAG_CHUNK_SIZE_WORDS", 200)
    chunk_overlap_words: int = _env_int("LOCAL_RAG_CHUNK_OVERLAP_WORDS", 40)
    section_max_words: int = _env_int("LOCAL_RAG_SECTION_MAX_WORDS", 400)
    media_segment_seconds: int = _env_int("LOCAL_RAG_MEDIA_SEGMENT_SECONDS", 45)
    whisper_model: str = _env("LOCAL_RAG_WHISPER_MODEL", "base")
    # -- retrieval ---------------------------------------------------------
    default_top_k: int = _env_int("LOCAL_RAG_DEFAULT_TOP_K", 5)
    rerank_top_n: int = _env_int("LOCAL_RAG_RERANK_TOP_N", 20)
    mmr_lambda: float = _env_float("LOCAL_RAG_MMR_LAMBDA", 0.7)
    rrf_k: int = _env_int("LOCAL_RAG_RRF_K", 60)
    bm25_k1: float = _env_float("LOCAL_RAG_BM25_K1", 1.5)
    bm25_b: float = _env_float("LOCAL_RAG_BM25_B", 0.75)
    # -- folder watcher ----------------------------------------------------
    watcher_enabled: bool = _env_bool("LOCAL_RAG_WATCHER_ENABLED", True)
    watcher_debounce_seconds: float = _env_float("LOCAL_RAG_WATCHER_DEBOUNCE_SECONDS", 1.0)
    # -- server ------------------------------------------------------------
    host: str = _env("LOCAL_RAG_HOST", "0.0.0.0")
    port: int = _env_int("LOCAL_RAG_PORT", 8000)
    log_level: str = _env("LOCAL_RAG_LOG_LEVEL", "INFO")


settings = Settings()
