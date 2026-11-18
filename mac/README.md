# Local RAG — macOS app

A native macOS app (SwiftUI) that is the GUI for local-rag. It talks to the
local-rag service over HTTP — it does not bundle the Python service or
Ollama. Start the service first, then open the app.

## What it does

- **Chat** — ask a question about your documents. Answers come back with
  their sources (citations) listed underneath, each with the file, the
  passage, and its score. Chat history is kept locally.
- **Search** — the retrieval playground. Pick a strategy (dense, sparse,
  or hybrid), toggle cross-encoder reranking and MMR, set top-k, and
  optionally filter by file type. See the ranked chunks with scores.
- **Documents** — what is in the vector database: file, chunk count,
  indexed date. Sync forces a re-scan of the folder; delete removes a
  document (and its chunks) from the index.
- **Stats** — document and chunk counts, vector store and BM25 sizes,
  folders, and model status (embeddings, reranker, Ollama, watcher).
- **Connection** — a status indicator in the sidebar (green / amber /
  red). If the service is not reachable, the app shows exactly how to
  start it instead of failing silently. The service address is
  configurable (default `http://localhost:8000`).

## Run it

Prerequisites: macOS 14+, Xcode 15+.

1. Start the service from the repo root:
   ```bash
   ./run.sh        # http://localhost:8000
   ```
   (First run installs the Python dependencies. Ollama + `ollama pull
   llama3.2:3b` is needed for answers; search works without it.)
2. Open `mac/LocalRAG.xcodeproj` in Xcode and press Run (⌘R).
3. If the service runs on a different host or port, change the address
   in the app (gear icon, top right) — or in the connection screen if
   it cannot reach the service at all.

Put files to ask about in the service's `data/documents/` folder. The
app never uploads files — the service's folder watcher indexes them.

## Structure

```
mac/
├── LocalRAG.xcodeproj/     Xcode project
└── LocalRAG/
    ├── LocalRAGApp.swift   App entry point
    ├── Info.plist
    ├── Assets.xcassets/    App icon (placeholder set — add sizes before release)
    └── app/                MVC
        ├── Models/         API models (match the server's Pydantic schemas),
        │                   chat messages and sessions
        ├── Services/       LocalRAGClient (URLSession, all API calls),
        │                   SettingsStore (service address), ChatHistoryStore
        ├── Controllers/    AppController (health), ChatController,
        │                   SearchController, DocumentsController
        └── Views/          ContentView (sidebar), ChatView, SearchView,
                            DocumentsView, StatsView, ConnectionView
```

No third-party dependencies — Foundation + SwiftUI only.

## API contract

The app speaks the local-rag v1 API (see `app/models/schemas.py` in the
service). Every call is a plain JSON request/response; the service does
not stream:

| Call | Shape |
| --- | --- |
| `GET /health` | `HealthResponse` — status, `llm_available`, models + loaded flags, document/chunk counts, `watcher_running`, `sync_status` |
| `GET /api/v1/stats` | `StatsResponse` — folders, document/chunk counts, vector store + BM25 sizes |
| `POST /api/v1/query` | `{question, strategy, rerank, mmr, top_k, filters?}` → `{answer, sources[{rank, source, chunk_id, text, score}], retrieval_stats}` |
| `POST /api/v1/search` | `{query, strategy, rerank, mmr, top_k, filters?}` → `{results[{chunk_id, document_id, source, text, score, rank}], retrieval_stats}` |
| `GET /api/v1/documents` | `[DocumentInfo]` — id, path, file_type, chunk_count, sha256, indexed_at |
| `POST /api/v1/documents/sync` | `SyncResult` — added / updated / removed / skipped_unsupported, counts |
| `DELETE /api/v1/documents/{id}` | 204 on success, 404 when missing |

Errors follow FastAPI's `{"detail": "..."}` shape, which the app shows
as-is.

## Honest note

This app was written and structurally checked on a Linux machine with no
Swift toolchain, so it has not been compiled here. The first Xcode build
on a Mac is the real verification — if it fails, the error will be in
the Swift code or the project file, not in the API contract above.
