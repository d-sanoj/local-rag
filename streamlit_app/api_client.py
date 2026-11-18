"""HTTP client for the local-rag API.

Pure httpx — no Streamlit import here, so this module can be tested on
its own against a running service. The Streamlit UI in app.py is the only
place that imports streamlit.
"""

from __future__ import annotations

import httpx


class LocalRAGError(Exception):
    """The service answered with an error, or could not be reached."""


class LocalRAGClient:
    """Thin wrapper over the local-rag v1 API (see the service README)."""

    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            # trust_env=False: the service is local (localhost by default),
            # so this client must never route through an HTTP proxy. (Some
            # environments export a NO_PROXY list with bracketed IPv6 entries
            # that httpx cannot parse at all.)
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.request(method, url, json=payload)
        except httpx.ConnectError as exc:
            raise LocalRAGError(
                f"cannot reach the service at {self.base_url} — "
                "is it running? Start it with `./run.sh` from the repo root."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LocalRAGError(f"request to {path} timed out") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text[:300])
            except ValueError:
                detail = response.text[:300]
            raise LocalRAGError(f"{method} {path} failed ({response.status_code}): {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise LocalRAGError(f"{method} {path} returned non-JSON") from exc

    def health(self) -> dict:
        return self._request("GET", "/health")

    def stats(self) -> dict:
        return self._request("GET", "/api/v1/stats")

    def search(
        self,
        query: str,
        strategy: str = "hybrid",
        rerank: bool = True,
        mmr: bool = False,
        top_k: int = 5,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/search",
            {"query": query, "strategy": strategy, "rerank": rerank, "mmr": mmr, "top_k": top_k},
        )

    def query(
        self,
        question: str,
        strategy: str = "hybrid",
        rerank: bool = True,
        mmr: bool = False,
        top_k: int = 5,
    ) -> dict:
        return self._request(
            "POST",
            "/api/v1/query",
            {
                "question": question,
                "strategy": strategy,
                "rerank": rerank,
                "mmr": mmr,
                "top_k": top_k,
            },
        )

    def list_documents(self) -> list[dict]:
        result = self._request("GET", "/api/v1/documents")
        return result if isinstance(result, list) else []

    def sync(self) -> dict:
        return self._request("POST", "/api/v1/documents/sync", {})

    def delete_document(self, document_id: str) -> None:
        self._request("DELETE", f"/api/v1/documents/{document_id}")
