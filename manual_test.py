#!/usr/bin/env python3
"""
Manual test to verify router patterns work correctly
Run this from Python REPL or directly
"""
import re

# Test patterns from router.py
_BM25_SEARCH_PATTERNS = [
    r"\bsearch\s+for\b",
    r"\bfind\b\s+(the\s+)?invoice\s+(with\s+)?(GSTIN|number|#)",
    r"\bdo we have\b.*\binvoices?\b.*\bfrom\b",
    r"\bare there any\b.*\bGSTIN\b",
    r"\bis there an?\b.*\binvoice\s+(for|with|#)",
    r"\bshow\b\s+(me\s+)?invoice\s+(#|number)",
    r"\binvoices?\s+from\b\s+[A-Z]",
    r"\bfile\b.*\b\.pdf\b",
    # Line item patterns - THE NEW ONES
    r"\bfind\s+invoices?\s+(containing|with|that\s+have)\b",
    r"\b(which|what)\s+invoices?\s+(have|contain|include|with)\b",
    r"\binvoices?\s+(containing|with|that\s+have|that\s+include)\b",
    r"\bshow.*\b(sticker|print|label|product|service|line\s+item)s?\b",
    r"\bfind.*\b(sticker|print|label|product|service)s?\b",
    r"\b(sticker|print|label)\s+(products?|services?|items?)\b",
]

_BM25_SEARCH_RE = [re.compile(p, re.IGNORECASE) for p in _BM25_SEARCH_PATTERNS]

def check_query(query):
    """Check if query matches BM25 patterns"""
    has_match = any(p.search(query) for p in _BM25_SEARCH_RE)
    return has_match

# Test cases from the test file
test_queries = [
    # Primary failing queries
    ('Search for "Sticker" line items', True),
    ("Find invoices containing label products", True),
    ("Which invoices have printing services?", True),
    
    # Additional line item patterns
    ("Find invoices with sticker products", True),
    ("Show invoices containing print services", True),
    ("Which invoices contain label items", True),
    ("Find invoices that have printing", True),
    ("Show sticker products", True),
    ("Find print services", True),
    ("Invoices containing digital print", True),
    
    # Existing patterns (should also work)
    ("Show me invoice GST001", True),  # Invoice reference
    ("Find invoice with GSTIN 36ARKPC6820F1ZZ", True),  # GSTIN
]

print("=" * 80)
print("TESTING BM25 PATTERN MATCHING")
print("=" * 80)
print(f"{'QUERY':<50} {'MATCHES':<10} {'EXPECTED':<10} {'STATUS'}")
print("-" * 80)

passed = 0
for query, expected in test_queries:
    matches = check_query(query)
    status = "✅" if matches == expected else "❌"
    if matches == expected:
        passed += 1
    
    query_short = query[:47] + "..." if len(query) > 50 else query
    print(f"{query_short:<50} {str(matches):<10} {str(expected):<10} {status}")

print("-" * 80)
print(f"RESULTS: {passed}/{len(test_queries)} patterns matched correctly ({100*passed/len(test_queries):.0f}%)")
print("=" * 80)

if passed == len(test_queries):
    print("✅ All BM25 patterns are working correctly!")
else:
    print(f"⚠️ {len(test_queries)-passed} patterns failed to match")
