# rag package — multi-strategy RAG pipeline for invoice Q&A
#
# Modules:
#   chunker         — invoice JSON → natural-language chunks (5 types)
#   indexer         — ChromaDB vector store (sentence-transformers)
#   bm25_retriever  — BM25Okapi keyword search (with stemming)
#   sql_retriever   — LLM-generated SQL against SQLite
#   router          — query classification (sql/bm25/vector/hybrid)
#   reranker        — cross-encoder re-ranking + RRF fusion
#   query_expander  — HyDE query expansion + query decomposition
#   qa_chain        — unified RAG pipeline with conversation memory
#   evaluator       — evaluation framework with test suite
#   agent           — high-level orchestrator
