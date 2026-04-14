#!/usr/bin/env python3
"""
Test the updated router patterns for line item search
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent / "invoice-extraction-current"
sys.path.insert(0, str(project_root))

from rag.router import route_query

def test_line_item_routing():
    print("🧭 TESTING UPDATED ROUTER FOR LINE ITEM QUERIES")
    print("="*60)
    
    # Test the failing line item queries
    test_cases = [
        # The original failing queries
        ('Search for "Sticker" line items', "bm25"),
        ("Find invoices containing label products", "bm25"),
        ("Which invoices have printing services?", "bm25"),
        
        # Additional line item patterns
        ("Find invoices with sticker products", "bm25"),
        ("Show invoices containing print services", "bm25"),
        ("Which invoices contain label items", "bm25"),
        ("Find invoices that have printing", "bm25"),
        ("Show sticker products", "bm25"),
        ("Find print services", "bm25"),
        ("Invoices containing digital print", "bm25"),
        
        # Should still work - existing patterns
        ("Show me invoice GST001", "bm25"),
        ("Find invoice with GSTIN 36ARKPC6820F1ZZ", "bm25"),
        
        # Should NOT be BM25 - general/analytical queries
        ("What is the total amount of all invoices?", "sql"),
        ("Describe the types of products sold", "vector"),
        ("Show me the most recent invoice", "hybrid"),
    ]
    
    print(f"{'QUERY':<45} {'EXPECTED':<8} {'GOT':<8} {'PASS'}")
    print("-" * 70)
    
    passed = 0
    total = len(test_cases)
    
    for query, expected in test_cases:
        route = route_query(query)
        got = route["strategy"]
        confidence = route.get("confidence", 0.0)
        reasoning = route["reasoning"]
        
        is_pass = got == expected
        if is_pass:
            passed += 1
        
        status = "✅ PASS" if is_pass else "❌ FAIL"
        
        # Truncate query for table format
        query_short = query[:42] + "..." if len(query) > 45 else query
        
        print(f"{query_short:<45} {expected:<8} {got:<8} {status}")
        
        if not is_pass:
            print(f"  → Reason: {reasoning}")
            print(f"  → Confidence: {confidence:.2f}")
    
    print("-" * 70)
    print(f"Result: {passed}/{total} PASSED ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("✅ All line item queries now route to BM25!")
    else:
        print(f"⚠️ {total-passed} routing failures remain")
    
    return passed == total

if __name__ == "__main__":
    success = test_line_item_routing()
    exit(0 if success else 1)