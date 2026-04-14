#!/usr/bin/env python
"""Quick test to identify the NoneType.lower() bug."""
import traceback

def test_failing_queries():
    """Test the specific queries that failed with NoneType error."""
    from rag.qa_chain import answer
    
    failing_queries = [
        "Find invoice number INV-2026-001",
        "Show me invoice NONEXISTENT-999",
    ]
    
    for query in failing_queries:
        print(f"\n{'='*60}")
        print(f"Testing: {query}")
        print("="*60)
        try:
            result = answer(query)
            print(f"Strategy: {result.get('strategy')}")
            print(f"Answer type: {type(result.get('answer'))}")
            print(f"Answer: {result.get('answer', '')[:200] if result.get('answer') else 'None'}")
            print(f"Sources: {result.get('sources', [])}")
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    test_failing_queries()
