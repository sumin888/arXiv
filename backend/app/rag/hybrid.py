"""
Reciprocal Rank Fusion (RRF) merges ranked lists from vector and lexical search
without requiring comparable score scales.
"""

from collections import defaultdict

from app.config import settings


def reciprocal_rank_fusion(
    vector_ranked_ids: list[int],
    fts_ranked_ids: list[int],
    k: int | None = None,
) -> list[tuple[int, float]]:
    k = k if k is not None else settings.rrf_k
    scores: dict[int, float] = defaultdict(float)
    for rank, chunk_id in enumerate(vector_ranked_ids, start=1):
        scores[chunk_id] += 1.0 / (k + rank)
    for rank, chunk_id in enumerate(fts_ranked_ids, start=1):
        scores[chunk_id] += 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return ordered
