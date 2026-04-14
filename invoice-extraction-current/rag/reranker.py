"""
Re-ranker for RAG retrieval results.

Uses a cross-encoder model to re-score retrieved chunks against
the original query, improving precision before sending to the LLM.

Falls back to a lightweight keyword-overlap scorer if the
cross-encoder model is unavailable.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Lazy-loaded cross-encoder ─────────────────────────────────────────────
_cross_encoder = None
_cross_encoder_available: Optional[bool] = None


def _load_cross_encoder():
    """Try to load a lightweight cross-encoder for re-ranking."""
    global _cross_encoder, _cross_encoder_available

    if _cross_encoder_available is not None:
        return _cross_encoder_available

    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        _cross_encoder_available = True
        logger.info("Cross-encoder loaded: cross-encoder/ms-marco-MiniLM-L-6-v2")
    except Exception as e:
        _cross_encoder_available = False
        logger.warning("Cross-encoder unavailable (%s), using keyword fallback", e)

    return _cross_encoder_available


def _keyword_overlap_score(query: str, text: str) -> float:
    """Simple keyword overlap score as fallback re-ranker.

    Returns a 0-1 score based on what fraction of query tokens
    appear in the document text.
    """
    # FIXED: Handle None values gracefully
    if not query or not text:
        return 0.0
    
    q_tokens = set(query.lower().split())
    d_tokens = set(text.lower().split())

    if not q_tokens:
        return 0.0

    overlap = q_tokens & d_tokens
    return len(overlap) / len(q_tokens)


def rerank(query: str, results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """Re-rank a list of retrieval results by relevance to query.

    Each result dict must have a 'text' key. The function adds/updates
    a 'rerank_score' key and returns results sorted by that score.

    Args:
        query: The user's original question.
        results: List of dicts with at least a 'text' key.
        top_k: Max results to return after re-ranking.

    Returns:
        Top-K results sorted by re-rank score (highest first).
    """
    if not results:
        return []

    # FIXED: Ensure text is never None (handle missing/None text fields)
    texts = [r.get("text") or "" for r in results]

    if _load_cross_encoder() and _cross_encoder is not None:
        # Cross-encoder: score each (query, document) pair
        pairs = [(query, t) for t in texts]
        scores = _cross_encoder.predict(pairs)

        for result, score in zip(results, scores):
            result["rerank_score"] = round(float(score), 4)
    else:
        # Fallback: keyword overlap scoring
        for result, text in zip(results, texts):
            result["rerank_score"] = round(_keyword_overlap_score(query, text), 4)

    # Sort by rerank_score descending, return top_k
    ranked = sorted(results, key=lambda r: r.get("rerank_score", 0), reverse=True)
    return ranked[:top_k]


def reciprocal_rank_fusion(
    *result_lists: List[Dict[str, Any]],
    k: int = 60,
    top_n: int = 10,
    id_key: str = "source_file",
) -> List[Dict[str, Any]]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF score for a document = sum over all lists of 1 / (k + rank_in_list).
    This is a well-known fusion method that doesn't require score normalization.

    Args:
        *result_lists: Variable number of ranked result lists.
        k: RRF constant (default 60, standard value from the paper).
        top_n: Number of fused results to return.
        id_key: Metadata key to use for deduplication.

    Returns:
        Top-N fused results sorted by RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}

    for result_list in result_lists:
        for rank, result in enumerate(result_list):
            # Build a document ID from metadata
            meta = result.get("metadata", {})
            doc_id = meta.get(id_key, "") or result.get(id_key, "")
            chunk_type = meta.get("chunk_type", "")
            line_num = meta.get("line_number", "")
            unique_id = f"{doc_id}::{chunk_type}::{line_num}"

            rrf_scores[unique_id] = rrf_scores.get(unique_id, 0.0) + (1.0 / (k + rank + 1))

            if unique_id not in doc_map:
                doc_map[unique_id] = result

    # Sort by RRF score
    ranked_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    fused = []
    for uid in ranked_ids[:top_n]:
        result = doc_map[uid].copy()
        result["rrf_score"] = round(rrf_scores[uid], 6)
        fused.append(result)

    return fused
