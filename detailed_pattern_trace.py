#!/usr/bin/env python3
"""
MANUAL PATTERN VERIFICATION - All Line Item Queries
Trace through each query with the actual regex patterns from router.py
"""

import re

# Exact patterns from router.py (Lines 76-94)
patterns = {
    "Pattern 1: search for": r"\bsearch\s+for\b",
    "Pattern 2: find invoice with #/GSTIN": r"\bfind\b\s+(the\s+)?invoice\s+(with\s+)?(GSTIN|number|#)",
    "Pattern 3: do we have invoices from": r"\bdo we have\b.*\binvoices?\b.*\bfrom\b",
    "Pattern 4: are there any GSTIN": r"\bare there any\b.*\bGSTIN\b",
    "Pattern 5: is there an invoice": r"\bis there an?\b.*\binvoice\s+(for|with|#)",
    "Pattern 6: show invoice #": r"\bshow\b\s+(me\s+)?invoice\s+(#|number)",
    "Pattern 7: invoices from [VENDOR]": r"\binvoices?\s+from\b\s+[A-Z]",
    "Pattern 8: file .pdf": r"\bfile\b.*\b\.pdf\b",
    "Pattern 9: find invoices containing/with/that have": r"\bfind\s+invoices?\s+(containing|with|that\s+have)\b",
    "Pattern 10: which/what invoices have/contain/include/with": r"\b(which|what)\s+invoices?\s+(have|contain|include|with)\b",
    "Pattern 11: invoices containing/with/that have/that include": r"\binvoices?\s+(containing|with|that\s+have|that\s+include)\b",
    "Pattern 12: show ... sticker/print/label/product/service": r"\bshow.*\b(sticker|print|label|product|service|line\s+item)s?\b",
    "Pattern 13: find ... sticker/print/label/product/service": r"\bfind.*\b(sticker|print|label|product|service)s?\b",
    "Pattern 14: sticker/print/label products/services/items": r"\b(sticker|print|label)\s+(products?|services?|items?)\b",
}

# Test queries
test_queries = [
    'Search for "Sticker" line items',
    "Find invoices containing label products",
    "Which invoices have printing services?",
    "Find invoices with sticker products",
    "Show invoices containing print services",
    "Which invoices contain label items",
    "Find invoices that have printing",
    "Show sticker products",
    "Find print services",
    "Invoices containing digital print",
]

print("=" * 100)
print("DETAILED PATTERN MATCHING TRACE FOR LINE ITEM QUERIES")
print("=" * 100)

for query in test_queries:
    print(f"\n📍 Query: \"{query}\"")
    print("-" * 100)
    
    matches = []
    for pattern_name, pattern_str in patterns.items():
        regex = re.compile(pattern_str, re.IGNORECASE)
        match = regex.search(query)
        if match:
            matches.append((pattern_name, match.group(0)))
    
    if matches:
        print(f"✅ MATCHES ({len(matches)} pattern{'s' if len(matches) > 1 else ''}):")
        for pattern_name, matched_text in matches:
            print(f"   • {pattern_name}")
            print(f"     → Matched text: \"{matched_text}\"")
    else:
        print("❌ NO PATTERNS MATCHED")
    
    print()

print("=" * 100)
print("SUMMARY")
print("=" * 100)

total_queries = len(test_queries)
passing_queries = 0

for query in test_queries:
    matches_found = False
    for pattern_name, pattern_str in patterns.items():
        regex = re.compile(pattern_str, re.IGNORECASE)
        if regex.search(query):
            matches_found = True
            break
    
    status = "✅ PASS" if matches_found else "❌ FAIL"
    print(f"{status}: \"{query}\"")
    if matches_found:
        passing_queries += 1

print("-" * 100)
print(f"\nRESULT: {passing_queries}/{total_queries} queries match BM25 patterns ({100*passing_queries/total_queries:.0f}%)")
print("=" * 100)

if passing_queries == total_queries:
    print("\n✅ SUCCESS: All line item queries will route to BM25!")
    print("\nExpected routing for these queries:")
    print("  • Strategy: BM25")
    print("  • Confidence: 0.75")
    print("  • Fallback: HYBRID")
    print("  • Reasoning: Query uses a keyword search pattern")
else:
    print(f"\n❌ FAILURE: {total_queries - passing_queries} queries did not match")
