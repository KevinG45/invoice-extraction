"""
Invoice QA Chain — multi-strategy RAG pipeline.

Routes every query through the router to pick the best retrieval
strategy (sql | bm25 | vector | hybrid), fetches context, then
calls Ollama to generate a grounded answer.
"""

import logging
from typing import Any, Dict, List

import ollama

from core.config import (
    BM25_INDEX_PATH,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    RAG_TOP_K,
)
from rag.router import route_query
from rag.sql_retriever import sql_retrieve
from rag.bm25_retriever import BM25Retriever
from rag.indexer import query_chunks

logger = logging.getLogger(__name__)

# ── System prompt for the final LLM call ──────────────────────────────────
_SYSTEM_PROMPT = (
    "You are a finance assistant for an invoice management system. "
    "Answer based only on the provided context. If the answer is not "
    "in the context, say so. Do not make up numbers or dates."
)


# ── Internal helpers ──────────────────────────────────────────────────────

def _get_ollama_client() -> ollama.Client:
    client = ollama.Client(host=LLM_BASE_URL)
    return client


def _bm25_search(query: str, top_k: int = 5) -> List[dict]:
    """Load the BM25 index and return search results."""
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
    retriever.load_index()
    return retriever.search(query, top_k=top_k)


def _vector_search(query: str, top_k: int = 5) -> List[dict]:
    """Query ChromaDB and return results."""
    return query_chunks(query, n_results=top_k)


def _format_sql_context(sql_result: dict) -> str:
    """Format SQL retriever output into a readable context string."""
    if "error" in sql_result:
        return f"SQL query failed: {sql_result['error']}\nGenerated SQL: {sql_result.get('sql', 'N/A')}"

    lines = [f"SQL: {sql_result['sql']}", f"Rows returned: {sql_result['row_count']}", ""]
    for row in sql_result.get("results", []):
        lines.append(str(row))
    return "\n".join(lines)


def _format_bm25_context(results: List[dict]) -> str:
    """Format BM25 results into a readable context string."""
    if not results:
        return "No BM25 results found."
    lines = []
    for r in results:
        parts = [f"Source: {r.get('source_file', 'unknown')}"]
        if r.get("invoice_id"):
            parts.append(f"Invoice: {r['invoice_id']}")
        if r.get("vendor_name"):
            parts.append(f"Vendor: {r['vendor_name']}")
        if r.get("invoice_date"):
            parts.append(f"Date: {r['invoice_date']}")
        if r.get("total_amount"):
            parts.append(f"Total: {r['total_amount']}")
        parts.append(f"Score: {r.get('score', 0)}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_vector_context(results: List[dict]) -> str:
    """Format ChromaDB vector results into a readable context string."""
    if not results:
        return "No vector results found."
    parts = []
    for r in results:
        source = r.get("metadata", {}).get("source_file", "unknown")
        text = r.get("text", "")
        parts.append(f"[Source: {source}]\n{text}")
    return "\n\n---\n\n".join(parts)


def _extract_sources_sql(sql_result: dict) -> List[str]:
    sources = set()
    for row in sql_result.get("results", []):
        sf = row.get("source_file")
        if sf:
            sources.add(sf)
    return sorted(sources)


def _extract_sources_bm25(results: List[dict]) -> List[str]:
    return sorted({r.get("source_file", "unknown") for r in results if r.get("source_file")})


def _extract_sources_vector(results: List[dict]) -> List[str]:
    sources = set()
    for r in results:
        sf = r.get("metadata", {}).get("source_file")
        if sf:
            sources.add(sf)
    return sorted(sources)


def _merge_hybrid(bm25_results: List[dict], vector_results: List[dict]) -> tuple:
    """Merge BM25 + vector results, deduplicate by source_file.

    Returns (context_string, sources_list).
    """
    seen = set()
    bm25_parts = []
    for r in bm25_results:
        sf = r.get("source_file", "unknown")
        if sf not in seen:
            seen.add(sf)
            parts = [f"Source: {sf}"]
            if r.get("invoice_id"):
                parts.append(f"Invoice: {r['invoice_id']}")
            if r.get("vendor_name"):
                parts.append(f"Vendor: {r['vendor_name']}")
            if r.get("invoice_date"):
                parts.append(f"Date: {r['invoice_date']}")
            if r.get("total_amount"):
                parts.append(f"Total: {r['total_amount']}")
            bm25_parts.append(" | ".join(parts))

    vector_parts = []
    for r in vector_results:
        sf = r.get("metadata", {}).get("source_file", "unknown")
        if sf not in seen:
            seen.add(sf)
            text = r.get("text", "")
            vector_parts.append(f"[Source: {sf}]\n{text}")

    context_sections = []
    if bm25_parts:
        context_sections.append("BM25 matches:\n" + "\n".join(bm25_parts))
    if vector_parts:
        context_sections.append("Vector matches:\n" + "\n\n".join(vector_parts))

    context = "\n\n---\n\n".join(context_sections) if context_sections else "No results found."
    return context, sorted(seen - {"unknown"})


# ── Public API ────────────────────────────────────────────────────────────

def answer(query: str) -> dict:
    """Answer a question about invoices using multi-strategy RAG.

    Steps:
        1. Route the query to pick a retrieval strategy.
        2. Retrieve context using the chosen strategy.
        3. Build a grounded prompt and call Ollama.
        4. Return the answer with metadata.

    Returns
    -------
    dict with keys: answer, strategy, reasoning, sources, context_used
    """
    # Step 1 — Route
    route = route_query(query)
    strategy = route["strategy"]
    reasoning = route["reasoning"]

    logger.info("Query routed: strategy=%s, reasoning=%s", strategy, reasoning)

    # Step 2 — Retrieve context based on strategy
    sources: List[str] = []
    context = ""

    if strategy == "sql":
        sql_result = sql_retrieve(query)
        context = _format_sql_context(sql_result)
        sources = _extract_sources_sql(sql_result)

    elif strategy == "bm25":
        bm25_results = _bm25_search(query, top_k=RAG_TOP_K)
        context = _format_bm25_context(bm25_results)
        sources = _extract_sources_bm25(bm25_results)

    elif strategy == "vector":
        vector_results = _vector_search(query, top_k=RAG_TOP_K)
        context = _format_vector_context(vector_results)
        sources = _extract_sources_vector(vector_results)

    elif strategy == "hybrid":
        bm25_results = _bm25_search(query, top_k=RAG_TOP_K)
        vector_results = _vector_search(query, top_k=RAG_TOP_K)
        context, sources = _merge_hybrid(bm25_results, vector_results)

    # Step 3 — Build prompt and call Ollama
    user_message = f"CONTEXT:\n{context}\n\nQUESTION: {query}"

    try:
        client = _get_ollama_client()
        response = client.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            options={"temperature": LLM_TEMPERATURE},
        )
        answer_text = response["message"]["content"].strip()
    except Exception as e:
        logger.error("LLM generation failed: %s", e)
        answer_text = f"LLM generation failed ({e}). Raw context:\n{context}"

    # Step 4 — Return result
    result = {
        "answer": answer_text,
        "strategy": strategy,
        "reasoning": reasoning,
        "sources": sources,
        "context_used": context,
    }

    logger.info("QA done — strategy=%s, sources=%d, answer_len=%d",
                strategy, len(sources), len(answer_text))
    return result


# ── Backward-compatible class wrapper ─────────────────────────────────────
# agent.py, frontend/app.py, and api/main.py instantiate InvoiceQAChain
# and call .index_invoice() / .ask().  Keep them working.

class InvoiceQAChain:
    """Thin wrapper that preserves the old class-based interface."""

    def index_invoice(self, data: Dict[str, Any], filename: str = "unknown") -> int:
        from rag.chunker import chunk_invoice
        from rag.indexer import index_chunks
        chunks = chunk_invoice(data, filename=filename)
        return index_chunks(chunks)

    def ask(self, question: str) -> Dict[str, Any]:
        return answer(question)
