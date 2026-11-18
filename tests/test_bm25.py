"""BM25 tests — ranking, parameters, persistence."""

from __future__ import annotations

from app.repositories.bm25_repository import BM25Index, BM25Repository, tokenize


def test_tokenize():
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_bm25_ranks_relevant_first():
    index = BM25Index()
    index.build(
        [
            ("a", "the quick brown fox jumps over the lazy dog"),
            ("b", "vector databases store embeddings for retrieval"),
            ("c", "the lazy dog sleeps all day long"),
        ]
    )
    ranked = index.score("vector retrieval embeddings")
    assert ranked[0][0] == "b"
    assert ranked[0][1] > 0


def test_bm25_no_match_scores_nothing():
    index = BM25Index()
    index.build([("a", "cats and dogs"), ("b", "birds and fish")])
    assert index.score("quantum chromodynamics") == []


def test_bm25_empty_corpus():
    index = BM25Index()
    assert index.score("anything") == []
    assert index.size == 0


def test_bm25_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "bm25.json")
    index = BM25Index()
    index.build([("a", "hello world"), ("b", "hello there world")])
    index.save(path)
    loaded = BM25Index.load(path)
    assert loaded.size == 2
    assert loaded.score("hello world")[0][0] in ("a", "b")


def test_bm25_repository_rebuild_and_search(tmp_path):
    repo = BM25Repository(str(tmp_path / "bm25.json"))
    repo.rebuild(
        [
            ("x", "local rag runs on your mac"),
            ("y", "chroma stores vectors locally"),
            ("z", "the cat sat on the mat"),
        ]
    )
    assert repo.index.size == 3
    results = repo.search("local rag mac", top_k=2)
    assert results[0][0] == "x"
    # Reloaded from disk, same result.
    repo2 = BM25Repository(str(tmp_path / "bm25.json"))
    assert repo2.index.size == 3
    assert repo2.search("local rag mac", top_k=1)[0][0] == "x"
