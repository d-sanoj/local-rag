#!/bin/sh
# Start local-rag. Run from the repo root.
# First run: creates a venv, installs dependencies, and starts the server.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt

echo "Starting local-rag on http://localhost:8000 (docs at /docs)..."
exec .venv/bin/uvicorn app.main:app --host "${LOCAL_RAG_HOST:-0.0.0.0}" --port "${LOCAL_RAG_PORT:-8000}"
