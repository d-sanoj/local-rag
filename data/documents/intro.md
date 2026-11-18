# local-rag

local-rag is a local Retrieval-Augmented Generation service. It reads
documents from one folder on your machine, builds a searchable index of
them, and answers questions over those documents with citations. Nothing
leaves your machine: the embeddings, the reranker, the vector database
and the language model all run locally.

## How it works

You put files in `data/documents/`. The service chunks them, embeds the
chunks with a small local model, and stores them in ChromaDB. When you ask
a question, it retrieves the most relevant chunks, reranks them with a
cross-encoder, and asks a local LLM to answer from those chunks only.

## Retrieval

The default retrieval strategy is hybrid: dense vector search plus BM25
sparse search, fused with Reciprocal Rank Fusion. The reranker is a small
cross-encoder that scores each (query, chunk) pair and reorders the top
candidates. MMR can be enabled for diversity.

## Folder sync

Edit, add or delete files in `data/documents/` and the index follows. A
file watcher re-indexes changed files live, and a startup scan catches
anything that changed while the service was down. The manifest is stored
in SQLite and records each file's SHA-256 hash, so a changed file is
always detected.
