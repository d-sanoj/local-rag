"""Example module for the local-rag sample documents.

It exists so the code chunker has something to split on function and
class boundaries.
"""


def reciprocal_rank_fusion(ranked_lists, k=60):
    """Fuse ranked id lists with Reciprocal Rank Fusion.

    Each list contributes 1 / (k + rank) per document. Documents that
    appear high in several lists score highest.
    """
    scores = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class BM25:
    """Classic BM25 ranking over a small corpus.

    The parameters k1 and b control term-frequency saturation and document
    length normalisation. The defaults here are k1=1.5 and b=0.75, the
    standard values used in most retrieval systems.
    """

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b

    def score(self, query_terms, doc_terms, avg_length):
        """Score one document against the query terms."""
        score = 0.0
        for term in set(query_terms):
            tf = doc_terms.count(term)
            if tf == 0:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * len(doc_terms) / avg_length)
            score += (tf * (self.k1 + 1)) / denom
        return score
