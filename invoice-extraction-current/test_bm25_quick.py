#!/usr/bin/env python
"""Quick BM25 smoke test to verify basic functionality."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("BM25 Retriever Quick Test")
print("=" * 50)

try:
    from rag.bm25_retriever import BM25Retriever
    from core.config import BM25_INDEX_PATH
    print("[OK] BM25Retriever imported successfully")
    
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
    retriever.load_index()
    print(f"[OK] Index loaded: {retriever.bm25 is not None}")
    print(f"     Documents count: {len(retriever.documents) if retriever.documents else 0}")
    print(f"     Metadata count: {len(retriever.metadata) if retriever.metadata else 0}")
    
    # Test 1: Basic search
    result = retriever.search("GST001", top_k=5)
    print(f"[OK] Search returned {len(result)} results")
    
    # Test 2: Verify result is not None (Bug BM25-1 fix)
    if result is None:
        print("[FAIL] BM25 search returned None - BUG NOT FIXED")
        sys.exit(1)
    print("[OK] Result is not None (Bug BM25-1 fix verified)")
    
    # Test 3: Empty query should not crash
    result2 = retriever.search("nonexistent xyz 12345", top_k=3)
    print(f"[OK] Empty result query returned {len(result2)} results")
    
    print()
    print("=" * 50)
    print("All BM25 tests PASSED!")
    print("=" * 50)
    
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
