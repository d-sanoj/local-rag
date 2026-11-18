"""RRF fusion and MMR tests."""

from __future__ import annotations

from app.services.reranking_service import (
    DummyReranker,
    maximal_marginal_relevance,
    reciprocal_rank_fusion,
)


def test_rrf_prefers_docs_high_in_both_lists():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], k=60)
    ids = [doc_id for doc_id, _ in fused]
    # a and b appear in both lists, so they outrank c and d.
    assert set(ids[:2]) == {"a", "b"}
    assert ids[0] in ("a", "b")


def test_rrf_single_list_keeps_order():
    fused = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    assert [doc_id for doc_id, _ in fused] == ["x", "y", "z"]


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_mmr_diversifies():
    # Query embedding points at dimension 0. Candidate A is identical to
    # the query, B is orthogonal, C is a near-duplicate of A.
    # With a low lambda (diversity matters more than relevance), the second
    # pick should be the diverse one (b), not the near-duplicate (c).
    query = [1.0, 0.0, 0.0]
    candidates = [
        {"id": "a", "embedding": [1.0, 0.0, 0.0]},
        {"id": "c", "embedding": [0.99, 0.01, 0.0]},
        {"id": "b", "embedding": [0.0, 1.0, 0.0]},
    ]
    picked = maximal_marginal_relevance(query, candidates, lambda_=0.3, top_k=2)
    assert picked[0]["id"] == "a"
    assert picked[1]["id"] == "b"


def test_mmr_without_embeddings_keeps_order():
    candidates = [{"id": "a"}, {"id": "b"}]
    assert maximal_marginal_relevance([1.0], candidates) == candidates


def test_dummy_reranker_keeps_order_with_scores():
    reranker = DummyReranker()
    chunks = [{"text": "one"}, {"text": "two"}]
    out = reranker.rerank("query", chunks)
    assert out[0]["text"] == "one"
    assert out[0]["score"] > out[1]["score"]
