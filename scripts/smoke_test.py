#!/usr/bin/env python3
"""End-to-end smoke test for local-rag — the same check CI runs.

Starts from a RUNNING service (start it first, e.g. with ./run.sh or the
CI workflow). It then:

1. waits for /health,
2. triggers a folder sync and waits for every example file to be indexed,
3. for each example with a question, asks it via /search and /query and
   checks the right file comes back (with real models this uses hybrid,
   the default; with dummy embeddings it uses sparse/BM25, because the
   dummy dense vectors are a bag-of-words hash, not semantic, and hybrid
   fusion over them is noise — see the comment in main()),
4. checks all three retrieval strategies (dense / sparse / hybrid) and MMR,
5. optionally asserts the REAL embedding/reranker models are loaded
   (--expect-real-models).

Exit code 0 means every check passed; anything else means the pipeline is
broken somewhere and the per-example table below says where.

Usage (dummy providers, local dev):

    LOCAL_RAG_DOCUMENTS_DIR=data/examples \\
    LOCAL_RAG_EMBEDDING_PROVIDER=dummy \\
    LOCAL_RAG_RERANKER_PROVIDER=dummy \\
    LOCAL_RAG_LLM_PROVIDER=echo \\
    LOCAL_RAG_WATCHER_ENABLED=false \\
    python -m uvicorn app.main:app --port 8000 &
    python scripts/smoke_test.py

Usage (real models, what CI runs):

    python scripts/smoke_test.py --expect-real-models
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUESTIONS = REPO_ROOT / "scripts" / "smoke_questions.json"


class SmokeFailure(Exception):
    """One check failed; message is the row shown in the table."""


def _request(
    base_url: str, method: str, path: str, payload: dict | None = None, timeout: float = 120.0
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300]
        raise SmokeFailure(f"HTTP {exc.code} on {method} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"cannot reach {method} {path}: {exc.reason}") from exc


def _wait_for_health(base_url: str, timeout: float) -> dict:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            return _request(base_url, "GET", "/health", timeout=10.0)
        except SmokeFailure as exc:
            last_error = str(exc)
            time.sleep(2.0)
    raise SmokeFailure(f"service did not answer /health within {timeout:.0f}s ({last_error})")


def _wait_for_documents(base_url: str, expected: set[str], timeout: float) -> dict:
    """Poll /documents until every expected file is indexed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = _request(base_url, "GET", "/api/v1/documents", timeout=30.0)
        by_path = {d["path"]: d for d in docs}
        if expected <= set(by_path) and all(by_path[p]["chunk_count"] >= 1 for p in expected):
            return by_path
        time.sleep(2.0)
    missing = sorted(expected - set(by_path))
    empty = sorted(p for p in expected if p in by_path and by_path[p]["chunk_count"] < 1)
    raise SmokeFailure(
        f"indexing incomplete after {timeout:.0f}s (missing={missing}, zero-chunk={empty})"
    )


def _source_rank(results: list[dict], filename: str) -> int | None:
    for i, result in enumerate(results, start=1):
        if filename in result.get("source", ""):
            return i
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument(
        "--expect-real-models",
        action="store_true",
        help="fail unless the real embedding/reranker models are loaded",
    )
    parser.add_argument(
        "--expect-ocr",
        action="store_true",
        help="assert the OCR retrieval check (only when tesseract is installed)",
    )
    parser.add_argument("--health-timeout", type=float, default=180.0)
    parser.add_argument("--sync-timeout", type=float, default=600.0)
    parser.add_argument(
        "--output", default="", help="also write the per-example results as JSON here"
    )
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    examples = questions["examples"]
    expected_files = {e["file"] for e in examples}
    retrieval_examples = [e for e in examples if e.get("retrieval")]

    rows: list[dict] = []
    failures: list[str] = []

    def record(entry: dict, ok: bool, detail: str) -> None:
        rows.append({**entry, "ok": ok, "detail": detail})
        if not ok:
            failures.append(f"{entry['file']}: {detail}")

    print(f"Smoke test against {args.base_url} — {len(examples)} example files")
    print(f"  providers expected: {'REAL models' if args.expect_real_models else 'as configured'}")

    # 1. Health ------------------------------------------------------------
    try:
        health = _wait_for_health(args.base_url, args.health_timeout)
        print(
            f"  health: status={health['status']} "
            f"embedding={health['embedding_provider']} "
            f"reranker={health['reranker_provider']} "
            f"llm_available={health['llm_available']}"
        )
    except SmokeFailure as exc:
        print(f"FAIL health: {exc}")
        return 1

    # 2. Sync + indexing ---------------------------------------------------
    try:
        sync = _request(args.base_url, "POST", "/api/v1/documents/sync", {}, timeout=600.0)
        print(
            f"  sync: +{len(sync.get('added', []))} ~{len(sync.get('updated', []))} "
            f"-{len(sync.get('removed', []))} "
            f"skipped_unsupported={sync.get('skipped_unsupported', [])} "
            f"documents={sync.get('documents')} chunks={sync.get('chunks')}"
        )
        by_path = _wait_for_documents(args.base_url, expected_files, args.sync_timeout)
    except SmokeFailure as exc:
        print(f"FAIL sync/indexing: {exc}")
        return 1

    # Which strategy the per-example check uses depends on the embedding
    # provider. Dummy embeddings are a bag-of-words hash, not semantic, so
    # hybrid fusion over them is noise and can bury a short chunk (the CSV
    # row) even though it is indexed and findable. With dummy providers the
    # check therefore uses sparse (BM25) — deterministic, exact-term — and
    # with real models (CI) it uses hybrid, the default path.
    retrieval_strategy = "hybrid" if health.get("embedding_provider") != "dummy" else "sparse"
    print(
        f"  per-example retrieval strategy: {retrieval_strategy} "
        f"(embedding provider: {health.get('embedding_provider')})"
    )

    for entry in examples:
        chunks = by_path[entry["file"]]["chunk_count"]
        record(entry, chunks >= 1, f"indexed, {chunks} chunk(s)")

    # 3. Retrieval per example ---------------------------------------------
    for entry in retrieval_examples:
        filename = entry["file"]
        question = entry["question"]
        if entry.get("requires") == "ocr" and not args.expect_ocr:
            # No tesseract in this environment: the image still indexes, but
            # there is no OCR text to retrieve. Skip honestly, don't fake it.
            record(entry, True, "SKIP retrieval — OCR not asserted in this run (pass --expect-ocr)")
            continue
        try:
            search = _request(
                args.base_url,
                "POST",
                "/api/v1/search",
                {"query": question, "strategy": retrieval_strategy, "rerank": True, "top_k": 5},
                timeout=180.0,
            )
            rank = _source_rank(search.get("results", []), filename)
            if rank is None:
                record(
                    entry,
                    False,
                    f"search: {filename} not in top 5 "
                    f"(got {[r.get('source') for r in search.get('results', [])]})",
                )
                continue
            query = _request(
                args.base_url,
                "POST",
                "/api/v1/query",
                {"question": question, "strategy": retrieval_strategy, "rerank": True, "top_k": 5},
                timeout=180.0,
            )
            if not query.get("answer", "").strip():
                record(entry, False, "query: empty answer")
                continue
            qrank = _source_rank(query.get("sources", []), filename)
            if qrank is None:
                record(entry, False, f"query: answer returned but {filename} not in sources")
                continue
            record(
                entry,
                True,
                f"{retrieval_strategy} search rank #{rank}, query sources rank #{qrank}",
            )
        except SmokeFailure as exc:
            record(entry, False, str(exc))

    # 4. Strategy + MMR coverage -------------------------------------------
    probe = retrieval_examples[0]["question"]
    probe_file = retrieval_examples[0]["file"]
    for strategy in ("dense", "sparse", "hybrid"):
        try:
            res = _request(
                args.base_url,
                "POST",
                "/api/v1/search",
                {"query": probe, "strategy": strategy, "rerank": False, "top_k": 5},
                timeout=180.0,
            )
            results = res.get("results", [])
            rank = _source_rank(results, probe_file)
            ok = bool(results) and rank is not None
            record(
                {"file": f"strategy:{strategy}", "type": "check"},
                ok,
                f"{len(results)} results, {probe_file} at rank #{rank}",
            )
        except SmokeFailure as exc:
            record({"file": f"strategy:{strategy}", "type": "check"}, False, str(exc))
    try:
        res = _request(
            args.base_url,
            "POST",
            "/api/v1/search",
            {"query": probe, "strategy": "hybrid", "rerank": True, "mmr": True, "top_k": 5},
            timeout=180.0,
        )
        record(
            {"file": "mmr:true", "type": "check"},
            bool(res.get("results")),
            f"{len(res.get('results', []))} results",
        )
    except SmokeFailure as exc:
        record({"file": "mmr:true", "type": "check"}, False, str(exc))

    # 5. Real-model assertion (CI) ------------------------------------------
    if args.expect_real_models:
        health = _request(args.base_url, "GET", "/health", timeout=10.0)
        checks = [
            ("embedding_provider", health.get("embedding_provider"), "sentence-transformers"),
            ("embedding_loaded", health.get("embedding_loaded"), True),
            ("reranker_provider", health.get("reranker_provider"), "cross-encoder"),
            ("reranker_loaded", health.get("reranker_loaded"), True),
        ]
        for name, got, want in checks:
            record(
                {"file": f"model:{name}", "type": "check"},
                got == want,
                f"got {got!r}, want {want!r}",
            )
        print(
            f"  models: embedding={health['embedding_provider']} "
            f"loaded={health['embedding_loaded']}; "
            f"reranker={health['reranker_provider']} "
            f"loaded={health['reranker_loaded']}"
        )

    # Report ----------------------------------------------------------------
    print()
    print(f"{'file':<32} {'type':<6} {'result':<5} detail")
    for row in rows:
        result = "SKIP" if row["detail"].startswith("SKIP") else ("PASS" if row["ok"] else "FAIL")
        print(f"{row['file']:<32} {row.get('type', ''):<6} {result:<5} {row['detail']}")
    passed = sum(1 for r in rows if r["ok"] and not r["detail"].startswith("SKIP"))
    skipped = sum(1 for r in rows if r["detail"].startswith("SKIP"))
    print(f"\n{passed}/{len(rows)} checks passed ({skipped} skipped)")
    if args.output:
        Path(args.output).write_text(
            json.dumps(
                {
                    "base_url": args.base_url,
                    "passed": passed,
                    "total": len(rows),
                    "failures": failures,
                    "rows": rows,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"results written to {args.output}")
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
