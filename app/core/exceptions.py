"""Domain exceptions. Controllers translate these to HTTP statuses."""

from __future__ import annotations


class LocalRAGError(Exception):
    """Base class for all local-rag errors."""


class UnsupportedFileTypeError(LocalRAGError):
    """Raised when no chunker exists for a file extension."""


class DocumentNotFoundError(LocalRAGError):
    """Raised when a document id is not in the index."""


class OllamaUnavailableError(LocalRAGError):
    """Raised when the Ollama server cannot be reached."""


class ModelNotLoadedError(LocalRAGError):
    """Raised when a required local model is not loaded/available."""


class EmbeddingError(LocalRAGError):
    """Raised when embedding generation fails."""


class IndexingError(LocalRAGError):
    """Raised when a file cannot be indexed (corrupt, unreadable, ...)."""
