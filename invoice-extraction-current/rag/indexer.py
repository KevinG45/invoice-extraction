"""
ChromaDB Indexer — stores invoice chunks as vector embeddings
for retrieval-augmented generation (RAG).

Uses sentence-transformers (all-MiniLM-L6-v2) for local embeddings.
No paid API calls — everything runs on-device.
"""

import hashlib
import json
import logging
import concurrent.futures
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from core.config import CHROMA_DIR, CHROMA_COLLECTION, EMBEDDING_MODEL, OUTPUTS_DIR
from rag.chunker import chunk_invoice

logger = logging.getLogger(__name__)

# FIXED: Bug #13, #35 — Timeouts and caching configuration
VECTOR_QUERY_TIMEOUT_SEC = 15  # Hard 15s limit on vector queries


# ── Query embedding cache (Bug #13, #35) ────────────────────────────────────
_embedding_model = None

def _get_raw_embedding_model():
    """Get the raw sentence-transformers model for caching."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Loaded raw embedding model for caching: %s", EMBEDDING_MODEL)
    return _embedding_model


@lru_cache(maxsize=200)
def _embed_query_cached(query_text: str) -> Tuple[float, ...]:
    """
    FIXED: Bug #13, #35 — LRU-cached embedding generation.
    
    Returns embedding as tuple (hashable for lru_cache).
    Cache eliminates re-embedding for repeated/similar queries.
    """
    # Safety check for None
    if not query_text:
        return tuple()
    model = _get_raw_embedding_model()
    # Normalize for better cache hits
    normalized = query_text.lower().strip()
    embedding = model.encode(normalized)
    return tuple(embedding.tolist())

# ── Lazy singleton ─────────────────────────────────────────────────────────
_client: Optional[chromadb.ClientAPI] = None
_collection = None
_embed_fn = None


def _get_embedding_function():
    """Load sentence-transformers embedding model (lazy)."""
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        logger.info("Loaded embedding model: %s", EMBEDDING_MODEL)
    return _embed_fn


def _get_collection():
    """Get or create the ChromaDB collection (lazy)."""
    global _client, _collection
    if _collection is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        ef = _get_embedding_function()
        _collection = _client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection '%s' ready (dir: %s, count: %d)",
                     CHROMA_COLLECTION, CHROMA_DIR, _collection.count())
    return _collection


def _chunk_id(text: str, source: str) -> str:
    """Generate a deterministic chunk ID for deduplication."""
    h = hashlib.sha256(f"{source}::{text}".encode("utf-8")).hexdigest()[:16]
    return f"inv_{h}"


def _indexed_source_files() -> set:
    """Return the set of source_file values already in the collection."""
    collection = _get_collection()
    if collection.count() == 0:
        return set()
    # Fetch all metadata to extract unique source_files
    all_data = collection.get(include=["metadatas"])
    sources = set()
    for meta in (all_data.get("metadatas") or []):
        sf = (meta or {}).get("source_file")
        if sf:
            sources.add(sf)
    return sources


def index_chunks(chunks: List[Dict[str, Any]]) -> int:
    """
    Add chunks to the ChromaDB collection.

    Uses deterministic IDs so re-indexing the same invoice
    upserts rather than duplicates.

    Args:
        chunks: List of dicts with 'text' and 'metadata' keys.

    Returns:
        Number of chunks indexed.
    """
    if not chunks:
        return 0

    collection = _get_collection()

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        text = chunk["text"]
        meta = chunk.get("metadata", {})

        # ChromaDB metadata must be flat strings/ints/floats/bools
        flat_meta = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                flat_meta[k] = v
            else:
                flat_meta[k] = str(v)

        doc_id = _chunk_id(text, flat_meta.get("source_file", "unknown"))
        ids.append(doc_id)
        documents.append(text)
        metadatas.append(flat_meta)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info("Indexed %d chunks into collection '%s' (total: %d)",
                len(ids), CHROMA_COLLECTION, collection.count())
    return len(ids)


def index_all() -> Dict[str, int]:
    """
    Read every JSON file in outputs/extractions/, chunk each one,
    and index into ChromaDB. Skips files already indexed.

    Returns:
        Dict with keys: indexed, skipped, failed, total_chunks.
    """
    json_files = sorted(OUTPUTS_DIR.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in %s", OUTPUTS_DIR)
        return {"indexed": 0, "skipped": 0, "failed": 0, "total_chunks": 0}

    already_indexed = _indexed_source_files()
    logger.info("Found %d JSON files; %d source_files already indexed",
                len(json_files), len(already_indexed))

    indexed = 0
    skipped = 0
    failed = 0
    total_chunks = 0

    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            source_file = (data.get("metadata") or {}).get("source_file", "")
            if not source_file:
                logger.warning("SKIP %s (no metadata.source_file)", path.name)
                skipped += 1
                continue

            if source_file in already_indexed:
                logger.debug("SKIP %s (already indexed)", source_file)
                skipped += 1
                continue

            chunks = chunk_invoice(data, filename=path.name)
            n = index_chunks(chunks)
            total_chunks += n
            indexed += 1
            logger.info("OK %s -> %d chunks", source_file, n)

        except Exception as exc:
            logger.error("FAIL %s: %s", path.name, exc)
            failed += 1

    return {
        "indexed": indexed,
        "skipped": skipped,
        "failed": failed,
        "total_chunks": total_chunks,
    }


def query_chunks(query_text: str, n_results: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Query the ChromaDB collection for relevant chunks.
    
    FIXED: Bug #13, #35 — Added timeout guard and embedding cache.

    Args:
        query_text: Natural-language query.
        n_results: Max number of chunks to return.
        use_cache: If True, use LRU-cached embeddings (default).

    Returns:
        List of dicts with 'text', 'metadata', and 'distance' keys,
        sorted by relevance (lowest distance first).
    """
    collection = _get_collection()

    if collection.count() == 0:
        logger.warning("ChromaDB collection is empty — no invoices indexed yet")
        return []

    def _do_query():
        """Execute the query, optionally using cached embeddings."""
        if use_cache:
            # Use cached embedding
            embedding = _embed_query_cached(query_text)
            return collection.query(
                query_embeddings=[list(embedding)],
                n_results=min(n_results, collection.count()),
            )
        else:
            # Use ChromaDB's built-in embedding
            return collection.query(
                query_texts=[query_text],
                n_results=min(n_results, collection.count()),
            )

    # FIXED: Bug #13, #35 — Wrap query in timeout guard
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_query)
            try:
                results = future.result(timeout=VECTOR_QUERY_TIMEOUT_SEC)
            except concurrent.futures.TimeoutError:
                logger.error("ChromaDB query timed out after %ds", VECTOR_QUERY_TIMEOUT_SEC)
                return []
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return []

    formatted = []
    # FIXED: Bug IDX-1 — Safer unpacking with None checks
    docs = (results.get("documents") or [[]])[0] if results.get("documents") else []
    metas = (results.get("metadatas") or [[]])[0] if results.get("metadatas") else []
    dists = (results.get("distances") or [[]])[0] if results.get("distances") else []
    
    # FIXED: Bug IDX-2 — Validate lengths before zip
    if not (len(docs) == len(metas) == len(dists)):
        logger.warning("ChromaDB returned unequal result lengths: docs=%d, metas=%d, dists=%d", 
                       len(docs), len(metas), len(dists))
        # Use shortest length to avoid index errors
        min_len = min(len(docs), len(metas), len(dists))
        docs = docs[:min_len]
        metas = metas[:min_len]
        dists = dists[:min_len]

    for doc, meta, dist in zip(docs, metas, dists):
        formatted.append({
            "text": doc,
            "metadata": meta or {},
            "distance": round(dist, 4) if dist else 0.0,
        })

    logger.info("Query returned %d chunks (query: '%.50s...')", len(formatted), query_text)
    return formatted


def get_collection_stats() -> Dict[str, Any]:
    """Return stats about the current ChromaDB collection."""
    collection = _get_collection()
    return {
        "collection_name": CHROMA_COLLECTION,
        "total_chunks": collection.count(),
        "embedding_model": EMBEDDING_MODEL,
        "persist_dir": str(CHROMA_DIR),
    }


def clear_collection():
    """Delete all chunks from the collection."""
    global _collection
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(CHROMA_COLLECTION)
        _collection = None
        logger.info("Cleared collection '%s'", CHROMA_COLLECTION)
    except Exception as e:
        logger.warning("Could not clear collection: %s", e)
