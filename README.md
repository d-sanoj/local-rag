# local-rag

local-rag is a local Retrieval-Augmented Generation service. It reads
documents from one folder on your machine, builds a searchable index of
them, and answers questions over those documents with citations. Nothing
leaves your machine: the embeddings, the reranker, the vector database and
the language model all run locally.

## How it works

You put files in `data/documents/`. The service chunks them, embeds the
chunks with a small local model, and stores them in ChromaDB. When you ask
a question, it retrieves the most relevant chunks (hybrid dense + sparse
search, fused with Reciprocal Rank Fusion), reranks them with a
cross-encoder, optionally diversifies with MMR, and asks a local LLM
(Ollama, llama3.2:3b) to answer from those chunks only, citing its sources.

Edit, add or delete files in `data/documents/` and the index follows:
a file watcher re-indexes changed files live, and a startup scan catches
anything that changed while the service was down.

## Chunking

One chunker per file type, dispatched by extension:

| Type | Files | Strategy |
| --- | --- | --- |
| Text | `.md`, `.txt` | Recursive, section-aware, or fixed windows (configurable) |
| Code | `.py`, `.js`, `.ts`, `.java`, `.go`, `.rb`, `.rs`, `.c`, `.cpp` | Function/class boundaries, recursive fallback |
| PDF | `.pdf` | Per page, then recursive |
| Word | `.docx` | By heading, then recursive |
| HTML | `.html`, `.htm` | By heading/paragraph |
| Structured | `.csv`, `.json` | One chunk per row / record, field names carried |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, ... | OCR (Tesseract) |
| Video / audio | `.mp4`, `.mov`, `.mp3`, `.wav`, ... | Transcription (faster-whisper), timestamped segments |

Section-aware chunking is the default for text: one chunk per markdown
section, heading carried, long sections split at sentence boundaries.
On a 22-question test over a real blog corpus it reached 91% strict
recall@5, against 73% for fixed 200-word windows.

## Retrieval and reranking

- **Dense:** vector similarity (ChromaDB).
- **Sparse:** BM25 (k1=1.5, b=0.75), persisted and rebuilt on every sync.
- **Hybrid (default):** dense + sparse fused with Reciprocal Rank Fusion (k=60).
- **Reranking:** cross-encoder scores (query, chunk) pairs and reorders the
  top candidates. Optional MMR (lambda=0.7) for diversity.
- **Filters:** by source file, file type, and indexed date range.

## Models (small, local, best for RAG at this size)

| Role | Model | Size | Why |
| --- | --- | --- | --- |
| Embeddings | BAAI/bge-small-en-v1.5 | ~130MB, 384-dim | Strong retrieval for its size |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | ~90MB | Fast, standard small reranker |
| Generation | llama3.2:3b via Ollama | ~2GB | Most reliable small local LLM on a Mac |
| OCR | Tesseract | — | System install, no model download |
| Transcription | faster-whisper `base` | ~150MB | Small, good balance |

All three model choices are configurable (`.env`), and the LLM sits behind
an `LLMProvider` interface, so swapping Ollama for another local runtime is
a small change. The embedding model and reranker download from HuggingFace
on first use and cache locally.

## Quick start (Mac)

Prerequisites: Python 3.11+, [Ollama](https://ollama.com/download),
[Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
(`brew install tesseract`), and ffmpeg for video/audio
(`brew install ffmpeg`).

```sh
git clone https://github.com/d-sanoj/local-rag.git
cd local-rag

# Generation model (Ollama must be running)
ollama pull llama3.2:3b

# Start the service (creates a venv, installs deps, serves on :8000)
./run.sh
```

Then put your files in `data/documents/` and ask questions:

```sh
curl -X POST http://localhost:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is local-rag?", "strategy": "hybrid", "rerank": true}'
```

API docs: http://localhost:8000/docs

## Streamlit GUI

A web UI for the service lives in `streamlit_app/`. It is a client of the
API above — it does not import the service code or run the service itself.

```sh
# Start the service first (in another terminal)
./run.sh

# Then, from the repo root:
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Open http://localhost:8501. Four tabs: **Chat** (answers with citations),
**Search** (retrieval playground — strategy, rerank, MMR, top-k), **Documents**
(list, sync, delete), and **Health & stats**. If the service is not
reachable, the app says so and tells you to start it with `./run.sh`. If
the service runs on another host or port, set the Service URL in the
sidebar.

## API

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | Status, LLM availability, models loaded, index counts |
| POST | `/api/v1/query` | Answer a question with citations |
| POST | `/api/v1/search` | Ranked chunks only, no generation |
| GET | `/api/v1/documents` | Indexed files with chunk counts |
| POST | `/api/v1/documents/sync` | Trigger a manual folder sync |
| GET | `/api/v1/documents/{id}` | One document's metadata |
| DELETE | `/api/v1/documents/{id}` | Remove a document and its chunks |
| GET | `/api/v1/stats` | Document/chunk counts, folder path |

`query` and `search` accept `strategy` (`dense` | `sparse` | `hybrid`),
`rerank` (true/false), `mmr` (true/false), `top_k`, and `filters`
(`source`, `file_type`, `indexed_after`, `indexed_before`).

## Architecture

```
app/
  core/          config, logging, exceptions
  models/        Document, Chunk, API schemas
  repositories/  VectorRepository (ChromaDB), BM25Repository, ManifestRepository (SQLite)
  services/
    chunking/    one chunker per file type + registry
    embedding_service.py   (sentence-transformers, dummy provider for tests)
    retrieval_service.py   (dense / sparse / hybrid + RRF)
    reranking_service.py   (cross-encoder, RRF, MMR)
    indexing_service.py    (file -> chunks -> embeddings -> store)
    sync_service.py        (folder scan + watchdog watcher)
    generation_service.py  (LLMProvider: Ollama, echo for tests)
    query_service.py       (orchestration: retrieve -> rerank -> generate)
  api/v1/        health, query, search, documents (controllers only)
```

MVC: models hold the data shapes, repositories own persistence, services
own the logic, controllers only translate HTTP to service calls. The vector
store, the embedding model, the reranker and the LLM are all behind
interfaces, so each can be swapped without touching the pipeline.

## Folder sync semantics

- The service reads **only** from `data/documents/` (or
  `LOCAL_RAG_DOCUMENTS_DIR`). No other data source exists.
- **Startup sync:** every file is compared against a SQLite manifest
  (path, SHA-256, mtime, chunk count). New files are indexed, changed
  files are re-indexed (old chunks deleted first), removed files have
  their chunks deleted.
- **Live watcher:** a watchdog observer re-indexes a file on create/modify
  and removes its chunks on delete/move, debounced to 1 second.
- **Manual sync:** `POST /api/v1/documents/sync` runs the same scan.

## Use cases

- **Private document Q&A** — ask questions over your own notes, contracts,
  or research without uploading them anywhere.
- **Offline research** — works on a plane; the whole pipeline is local.
- **Codebase Q&A** — point the folder at a repo and ask where things are
  implemented and why.
- **A local RAG sandbox** — a working, measurable baseline for retrieval
  experiments: swap a chunker, a retriever, or a reranker and measure the
  difference on your own questions.

## Tests

```sh
make test    # pytest — chunkers, BM25, RRF, reranker, sync, API
make lint    # ruff check + format
```

Tests mock the embedding model, reranker, and LLM, so they run anywhere
without downloading models. The model-backed path (real embeddings and
generation) is verified on a Mac with Ollama running.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull
request to `main`, in three jobs:

| Job | What it checks |
| --- | --- |
| `lint` | `ruff check` + `ruff format --check` on `app`, `tests`, `scripts`, `streamlit_app` |
| `unit-tests` | `pytest` (48 tests, dummy providers — no model downloads) |
| `e2e` | The accurate check: boots the real service with the **real** embedding model (bge-small-en-v1.5) and reranker (cross-encoder), indexes the example documents in `data/examples/`, and asserts each one is retrievable by a question about it |

The `e2e` job is what replaces downloading the repo and checking it by
hand. It runs `scripts/smoke_test.py`, which prints a per-example
PASS/FAIL table (also uploaded as an artifact) and exits non-zero on any
failure. Answer generation uses the echo LLM in CI — no Ollama download;
the real Ollama path is verified on a Mac.

Two things the smoke test is explicit about, so a green run means what it
says:

- **Retrieval strategy depends on the embedding provider.** With the real
  models (CI) the per-example check uses `hybrid`, the default. With the
  dummy embeddings (local runs) it uses `sparse` (BM25): dummy vectors are
  a bag-of-words hash, not semantic, so hybrid fusion over them is noise
  and can bury a short chunk that is indexed and findable.
- **OCR is only asserted where tesseract is installed.** CI installs it
  and passes `--expect-ocr`, so the image example's retrieval is checked
  there. Without it the image is still asserted indexed, and the retrieval
  check is reported as SKIP, not faked.

The example data (`data/examples/`, see its `README.md`) covers every
file type the RAG supports: `.md`, `.txt`, `.py`, `.pdf`, `.docx`,
`.html`, `.csv`, `.json`, `.png` (OCR), `.wav` and `.mp4` (transcription).
The audio/video examples are a tone and a test pattern (no speech
synthesis on a CI runner), so the smoke test only asserts they are indexed
— it never claims a question retrieves spoken words from them.

Run the same checks locally:

```sh
make lint          # ruff
make test          # pytest
make smoke         # end-to-end smoke test (needs the service running)
```

For the smoke test, point the service at the examples and use the dummy
providers (or the real ones — see `scripts/smoke_test.py --help`). Use
fresh stores in /tmp so the run never touches your real index:

```sh
LOCAL_RAG_DOCUMENTS_DIR=data/examples \
LOCAL_RAG_VECTOR_DB_DIR=/tmp/local-rag-smoke/chroma \
LOCAL_RAG_MANIFEST_DB=/tmp/local-rag-smoke/manifest.db \
LOCAL_RAG_BM25_PATH=/tmp/local-rag-smoke/bm25.json \
LOCAL_RAG_EMBEDDING_PROVIDER=dummy \
LOCAL_RAG_RERANKER_PROVIDER=dummy \
LOCAL_RAG_LLM_PROVIDER=echo \
LOCAL_RAG_WATCHER_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --port 8000 &
.venv/bin/python scripts/smoke_test.py
```
