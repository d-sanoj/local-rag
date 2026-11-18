"""App entrypoint — builds the FastAPI app and wires the lifespan.

Startup: build the service graph, run the first folder sync in the
background (so the server answers /health immediately), and start the
folder watcher. Shutdown: stop the watcher.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import AppServices
from app.api.v1 import documents, health, query, search
from app.core.config import Settings, settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(app.state.settings.log_level)
    if app.state.services is None:
        # Production path: build the graph, sync in the background, watch.
        services = AppServices(app.state.settings)
        app.state.services = services

        def _initial_sync() -> None:
            try:
                services.sync_service.sync()
                services.retrieval_service.rebuild_bm25_cache()
            except Exception as exc:  # noqa: BLE001 — startup must not die on a bad file
                logger.warning("Initial sync failed: %s", exc)

        threading.Thread(target=_initial_sync, daemon=True, name="initial-sync").start()
        if app.state.settings.watcher_enabled:
            try:
                services.watcher.start()
            except Exception as exc:  # noqa: BLE001 — watcher failure must not kill startup
                logger.warning("Folder watcher failed to start: %s", exc)
        logger.info(
            "local-rag listening on %s:%d",
            app.state.settings.host,
            app.state.settings.port,
        )
    yield
    services = app.state.services
    if services is not None:
        services.watcher.stop()


def create_app(
    app_settings: Settings | None = None, services: AppServices | None = None
) -> FastAPI:
    """Build the app. Pass ``services`` in tests to inject fakes instead of
    the real ChromaDB / model-backed graph."""
    app = FastAPI(
        title="local-rag",
        description="Local Retrieval-Augmented Generation over one folder. "
        "Private, offline, runs on your Mac.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings or settings
    app.state.services = services
    app.include_router(health.router)
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
