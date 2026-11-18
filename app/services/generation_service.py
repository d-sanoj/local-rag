"""Generation service — turns retrieved chunks into an answer with citations.

Provider interface so the LLM can be swapped. Default is Ollama
(llama3.2:3b) on localhost:11434 — the easiest small local LLM on a Mac.
An echo provider exists for tests and for running without Ollama.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.config import Settings
from app.core.exceptions import OllamaUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the "
    "provided context. If the context does not contain the answer, say so "
    "plainly instead of guessing. Cite every factual claim with the source "
    "number in square brackets, e.g. [1], [2], matching the numbered sources."
)


def build_prompt(question: str, sources: list[dict[str, Any]]) -> str:
    """Assemble the grounded prompt: numbered sources, then the question."""
    context_lines = []
    for i, source in enumerate(sources, start=1):
        context_lines.append(f"[{i}] ({source.get('source', '')})\n{source.get('text', '')}")
    context = "\n\n".join(context_lines)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer (with citations):"
    )


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str: ...
    def is_available(self) -> bool: ...


class EchoLLMProvider:
    """Returns a canned, citation-shaped answer. Tests and no-Ollama runs."""

    def generate(self, prompt: str) -> str:
        return (
            "Based on the retrieved context, here is what I found. "
            "See the sources below for the passages this is drawn from. [1]"
        )

    def is_available(self) -> bool:
        return True


class OllamaLLMProvider:
    """Ollama /api/generate. Non-streaming — the query endpoint is sync."""

    def __init__(self, base_url: str, model: str, temperature: float = 0.1):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def is_available(self) -> bool:
        import httpx

        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            return response.status_code == 200
        except Exception:  # noqa: BLE001 — any Ollama failure is "unavailable"
            return False

    def generate(self, prompt: str) -> str:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                },
                timeout=300.0,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(
                f"cannot reach Ollama at {self.base_url} — is it running? "
                f"Start it with `ollama serve` and pull the model with "
                f"`ollama pull {self.model}`"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaUnavailableError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc


class GenerationService:
    """Owns the LLM provider; the rest of the app only talks to this class."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.llm_provider == "echo":
            self.provider: LLMProvider = EchoLLMProvider()
        else:
            self.provider = OllamaLLMProvider(
                settings.ollama_base_url,
                settings.ollama_model,
                settings.llm_temperature,
            )

    def generate_answer(self, question: str, sources: list[dict[str, Any]]) -> str:
        prompt = build_prompt(question, sources)
        return self.provider.generate(prompt)
