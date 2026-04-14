import sys
sys.path.insert(0, '.')

# Test BM25 first
print("Testing BM25 Retriever...")
try:
    from rag.bm25_retriever import BM25Retriever
    retriever = BM25Retriever()
    print(f"  Index loaded: {retriever.index is not None}")
    print(f"  Documents: {len(retriever.documents) if retriever.documents else 0}")
    result = retriever.search("GST001", top_k=3)
    print(f"  Search result count: {len(result)}")
    print(f"  BM25 TEST PASSED")
except Exception as e:
    print(f"  BM25 FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test qa_chain answer function
print("\nTesting QA Chain...")
try:
    from rag.qa_chain import answer
    result = answer("How many invoices are in the system?")
    print(f"  Strategy: {result.get('strategy')}")
    print(f"  Answer preview: {str(result.get('answer', ''))[:200]}")
    if result.get('strategy') != 'error':
        print("  QA Chain TEST PASSED")
    else:
        print(f"  QA Chain FAILED - returned error: {result.get('answer')}")
except Exception as e:
    print(f"  QA Chain FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test BM25 lookup
print("\nTesting BM25 Lookup Query...")
try:
    result = answer("Show me invoice GST001")
    print(f"  Strategy: {result.get('strategy')}")
    print(f"  Answer preview: {str(result.get('answer', ''))[:200]}")
    if result.get('strategy') != 'error':
        print("  BM25 Query TEST PASSED")
    else:
        print(f"  BM25 Query FAILED - returned error: {result.get('answer')}")
except Exception as e:
    print(f"  BM25 Query FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
