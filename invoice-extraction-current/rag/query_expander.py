"""
Query Expander — enhances retrieval by transforming the user's query
before it hits the vector store.

Techniques:
    1. HyDE (Hypothetical Document Embeddings) — asks the LLM to generate
       a hypothetical answer, then embeds *that* instead of the raw query.
       This closes the vocabulary gap between questions and documents.

    2. Query decomposition — splits multi-part questions into sub-queries
       so each part can be retrieved independently.
"""

import logging
from typing import List, Optional

import ollama

from core.config import LLM_BASE_URL, LLM_MODEL, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


# ── HyDE ──────────────────────────────────────────────────────────────────

_HYDE_SYSTEM_PROMPT = (
    "You are a helpful assistant for an invoice management system. "
    "Given a question about invoices, write a short paragraph that would "
    "appear in an invoice document and directly answers the question. "
    "Use realistic invoice language — vendor names, amounts, dates, "
    "line items, GSTIN numbers, etc. Do NOT say 'I don't know'. "
    "Just write the hypothetical invoice text."
)


def generate_hypothetical_document(query: str, max_retries: int = 3) -> Optional[str]:
    """Generate a hypothetical document that answers the query (HyDE).

    The hypothetical document is used for embedding instead of the raw
    query, because documents and hypothetical answers share more vocabulary
    than documents and questions.

    Args:
        query: The user's natural-language question.
        max_retries: Number of retry attempts for Ollama connection.

    Returns:
        A hypothetical answer string, or None if LLM call fails.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            client = ollama.Client(host=LLM_BASE_URL)
            response = client.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _HYDE_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                options={"temperature": 0.3, "num_predict": 150},
            )
            hyde_text = response["message"]["content"].strip()
            logger.info("HyDE generated (%d chars) for query: '%.60s...'",
                         len(hyde_text), query)
            return hyde_text
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning("HyDE attempt %d failed, retrying: %s", attempt + 1, e)
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.warning("HyDE generation failed after %d retries: %s", max_retries, e)
                return None


def expand_query_for_vector(query: str) -> str:
    """Return an expanded query string for vector search.

    Tries HyDE first. If it fails, returns the original query unchanged.
    The result should be used as input to the embedding model for vector
    similarity search.
    """
    hyde = generate_hypothetical_document(query)
    if hyde:
        # Combine original query + hypothetical doc for richer embedding
        return f"{query}\n\n{hyde}"
    return query


# ── Query Decomposition ───────────────────────────────────────────────────

_DECOMPOSE_SYSTEM_PROMPT = (
    "You are a query decomposition assistant for an invoice database. "
    "Given a complex question, break it into 2-4 simple sub-questions "
    "that can each be answered independently. "
    "Return ONLY the sub-questions, one per line, no numbering or bullets."
)


def decompose_query(query: str, max_retries: int = 3) -> List[str]:
    """Break a complex question into simpler sub-queries.

    Used for multi-part questions like:
    "What is the total amount and who is the vendor for invoice GST-001?"
    -> ["What is the total amount for invoice GST-001?",
        "Who is the vendor for invoice GST-001?"]

    Returns the original query as a single-element list if decomposition
    fails or the question is already simple.
    """
    import time
    
    # Safety check for None/empty query
    if not query:
        return []
    
    # Quick heuristic: skip decomposition for short/simple queries
    if len(query.split()) < 8 or " and " not in query.lower():
        return [query]

    for attempt in range(max_retries):
        try:
            client = ollama.Client(host=LLM_BASE_URL)
            response = client.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                options={"temperature": 0, "num_predict": 200},
            )
            raw = response["message"]["content"].strip()
            sub_queries = [line.strip().lstrip("0123456789.-) ")
                           for line in raw.split("\n")
                           if line.strip() and len(line.strip()) > 5]

            if sub_queries:
                logger.info("Decomposed query into %d sub-queries", len(sub_queries))
                return sub_queries
            return [query]  # No valid sub-queries found
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning("Decomposition attempt %d failed, retrying: %s", attempt + 1, e)
                time.sleep(2 ** attempt)
            else:
                logger.warning("Query decomposition failed after %d retries: %s", max_retries, e)

    return [query]
