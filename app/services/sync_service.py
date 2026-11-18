"""Folder sync — the service reads ONLY from one configured folder.

- ``sync()`` scans the folder, compares each file against the manifest
  (SHA-256 + mtime), and adds new files, re-indexes changed files, and
  removes files that disappeared. Unsupported extensions are skipped with
  a warning, never a crash.
- ``FolderWatcher`` is a watchdog observer that re-indexes a file on
  create/modify and removes its chunks on delete/move, debounced so a
  burst of editor saves becomes one re-index.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable

from app.core.config import Settings
from app.core.exceptions import UnsupportedFileTypeError
from app.core.logging import get_logger
from app.models.schemas import SyncResult
from app.repositories.manifest_repository import ManifestRepository
from app.services.indexing_service import IndexingService, sha256_file

logger = get_logger(__name__)


class SyncService:
    def __init__(
        self,
        settings: Settings,
        indexing_service: IndexingService,
        manifest_repo: ManifestRepository,
    ):
        self.settings = settings
        self.documents_dir = os.path.abspath(settings.documents_dir)
        self.indexing_service = indexing_service
        self.manifest_repo = manifest_repo
        self._lock = threading.Lock()
        self.status = "idle"
        self.last_result: SyncResult | None = None
        # Called after any index change (sync, watcher) so the retrieval
        # layer can refresh its in-memory chunk cache. Wired in deps.py.
        self.on_index_change: Callable[[], None] | None = None

    def sync(self) -> SyncResult:
        """One full pass over the folder. Thread-safe: concurrent calls are
        serialised on a lock."""
        with self._lock:
            self.status = "syncing"
            try:
                result = self._sync_once()
            finally:
                self.status = "idle"
            self.last_result = result
            self._notify_change()
            return result

    def _notify_change(self) -> None:
        if self.on_index_change is not None:
            self.on_index_change()

    def _sync_once(self) -> SyncResult:
        os.makedirs(self.documents_dir, exist_ok=True)
        result = SyncResult()
        seen: set[str] = set()
        changed = False
        for root, dirs, files in os.walk(self.documents_dir):
            dirs.sort()
            for filename in sorted(files):
                absolute = os.path.join(root, filename)
                relative = os.path.relpath(absolute, self.documents_dir)
                extension = relative.rsplit(".", 1)[-1].lower() if "." in relative else ""
                if not self.indexing_service.chunker_registry.is_supported(extension):
                    result.skipped_unsupported.append(relative)
                    # Do NOT add to `seen`: a file renamed to an unsupported
                    # extension must be removed from the index below.
                    continue
                seen.add(relative)
                existing = self.manifest_repo.get_by_path(relative)
                file_hash = sha256_file(absolute)
                if existing is None:
                    self.indexing_service.index_file(absolute, relative, rebuild_bm25=False)
                    result.added.append(relative)
                    changed = True
                elif existing.sha256 != file_hash:
                    self.indexing_service.index_file(absolute, relative, rebuild_bm25=False)
                    result.updated.append(relative)
                    changed = True
        # Files that disappeared from the folder.
        for document in self.manifest_repo.list_all():
            if document.path not in seen:
                self.indexing_service.remove_document(document, rebuild_bm25=False)
                result.removed.append(document.path)
                changed = True
        if changed:
            self.indexing_service.rebuild_bm25()
        result.documents = len(self.manifest_repo.list_all())
        result.chunks = self.indexing_service.vector_repo.count()
        logger.info(
            "Sync done: +%d ~%d -%d (skipped %d unsupported)",
            len(result.added),
            len(result.updated),
            len(result.removed),
            len(result.skipped_unsupported),
        )
        return result

    def index_one(self, absolute_path: str) -> None:
        """Re-index a single file (watcher path)."""
        relative = os.path.relpath(absolute_path, self.documents_dir)
        with self._lock:
            self.indexing_service.index_file(absolute_path, relative)
        self._notify_change()

    def remove_one(self, absolute_path: str) -> None:
        """Remove one file's chunks (watcher path)."""
        relative = os.path.relpath(absolute_path, self.documents_dir)
        with self._lock:
            document = self.manifest_repo.get_by_path(relative)
            if document is not None:
                self.indexing_service.remove_document(document)
        self._notify_change()


class FolderWatcher:
    """Watchdog observer on the documents folder, debounced."""

    def __init__(self, settings: Settings, sync_service: SyncService):
        self.settings = settings
        self.sync_service = sync_service
        self.documents_dir = os.path.abspath(settings.documents_dir)
        self.debounce_seconds = settings.watcher_debounce_seconds
        self._observer = None
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self.running = False

    def start(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        sync_service = self.sync_service
        debounce = self.debounce_seconds
        timers = self._timers
        lock = self._lock

        class Handler(FileSystemEventHandler):
            def _schedule(self, path: str, kind: str) -> None:
                if os.path.isdir(path):
                    return
                with lock:
                    old = timers.pop(path, None)
                    if old is not None:
                        old.cancel()

                    def _run() -> None:
                        with lock:
                            timers.pop(path, None)
                        try:
                            if kind == "delete":
                                sync_service.remove_one(path)
                            else:
                                if os.path.exists(path):
                                    sync_service.index_one(path)
                        except UnsupportedFileTypeError:
                            logger.debug("Watcher: unsupported file, skipping %s", path)
                        except Exception as exc:  # noqa: BLE001 — never kill the watcher on one file
                            logger.warning("Watcher: failed to handle %s: %s", path, exc)

                    timer = threading.Timer(debounce, _run)
                    timers[path] = timer
                    timer.start()

            def on_created(self, event) -> None:
                self._schedule(event.src_path, "create")

            def on_modified(self, event) -> None:
                self._schedule(event.src_path, "modify")

            def on_deleted(self, event) -> None:
                self._schedule(event.src_path, "delete")

            def on_moved(self, event) -> None:
                self._schedule(event.src_path, "delete")
                self._schedule(event.dest_path, "create")

        os.makedirs(self.documents_dir, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(Handler(), self.documents_dir, recursive=True)
        self._observer.start()
        self.running = True
        logger.info("Watching %s for changes (debounce %.1fs)", self.documents_dir, debounce)

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
        self.running = False
        logger.info("Folder watcher stopped")
