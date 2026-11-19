# Streamlit GUI for local-rag

A web UI for the local-rag service. It is a **client** of the service API:
it talks to the service over HTTP (default `http://localhost:8000`) and
does not import the service code or run the service itself.

## Run it

```sh
# Start the service first (in another terminal)
./run.sh

# Then, from the repo root:
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Open http://localhost:8501. If the service runs on another host or port,
set the Service URL in the sidebar.

## Features

- **Chat** — ask a question, get an answer with its sources/citations
  (filename, chunk excerpt, score). Conversation history is kept in the
  session.
- **Search** — retrieval playground: strategy picker (Dense / Sparse /
  Hybrid), rerank and MMR toggles, top-k control, ranked chunks.
- **Documents** — indexed files with chunk counts, a Sync button, delete
  per document. Files are added by putting them in the service's documents
  folder (`data/documents/` by default) — the app does not upload files.
- **Health & stats** — service status, model status, document/chunk counts.

If the service is not reachable, the app says so plainly and tells you to
start it with `./run.sh`.

## Files

- `app.py` — the UI (Streamlit only; all API calls go through the client).
- `api_client.py` — the HTTP client for the local-rag API. Pure httpx, no
  Streamlit import, so it can be tested on its own.
- `requirements.txt` — `streamlit` + `httpx`. Kept separate from the
  service's `requirements.txt` so the service stays lean.
