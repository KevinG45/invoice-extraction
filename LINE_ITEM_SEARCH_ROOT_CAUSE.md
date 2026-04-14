# LINE ITEM SEARCH DEBUG - ROOT CAUSE ANALYSIS

## Issue Summary
- **Tests Failing**: "Find invoices containing label products", "Which invoices have printing services?"
- **Success Rate**: 0% (not routing correctly)
- **Root Cause**: Router is not recognizing line item search queries as BM25 queries

## Evidence

### 1. Data Exists ✅
All test invoices have line items with proper descriptions:
- GST001: "Stciker - Size 13x19" (line item search should find this)
- GST24005: "Sticker With Lamination - Bac Gaurd" (with multiple sticker items)
- GST003: "Digital Print Out - Printing on Size..." (print item)
- GST24028: "A4 Printouts - Registration Forms" (printouts)

### 2. BM25 Index Building ✅
The BM25 retriever properly includes line items in document text (line 569-578 of bm25_retriever.py):
```python
for item in data.get("line_items") or []:
    desc = item.get("description")
    if desc is not None:
        if isinstance(desc, list):
            parts.extend(str(d) for d in desc)
        else:
            parts.append(str(desc))
```

Line items are also included in metadata summaries (line 316-318):
```python
"line_items_summary": "; ".join(
    str(item.get("description", ""))[:50] for item in line_items[:5]
),
```

### 3. Router Logic Issue ❌
The failing queries:
- "Find invoices containing label products" → Expected: BM25, Actual: HYBRID (or VECTOR)
- "Which invoices have printing services?" → Expected: BM25, Actual: HYBRID (or VECTOR)

#### Why They're Not Routing to BM25:

Looking at `router.py`:
- Line 234: "find" is NOT in `_SQL_KEYWORDS` ✅
- Line 258: Query doesn't match `_INVOICE_NUM_RE` (no invoice number) ✅
- Line 293: Query doesn't match `_GSTIN_RE` ✅
- Line 316: Query doesn't match `_QUOTED_RE` ✅
- Line 328: Query doesn't match `_COMPANY_NAME_RE` ✅
- Line 362: Checking `_HYBRID_FILTER_KEYWORDS` - "label" and "printing" are NOT in this list ✓
- Line 374-385: Checking `_BM25_SEARCH_RE` patterns...

**THE PROBLEM**: The BM25 search patterns (lines 77-86) are:
```python
_BM25_SEARCH_PATTERNS = [
    r"\bsearch\s+for\b",
    r"\bfind\b\s+(the\s+)?invoice\s+(with\s+)?(GSTIN|number|#)",
    r"\bdo we have\b.*\binvoices?\b.*\bfrom\b",
    r"\bare there any\b.*\bGSTIN\b",
    r"\bis there an?\b.*\binvoice\s+(for|with|#)",
    r"\bshow\b\s+(me\s+)?invoice\s+(#|number)",
    r"\binvoices?\s+from\b\s+[A-Z]",
    r"\bfile\b.*\b\.pdf\b",
]
```

**CRITICAL ISSUE**: 
- Pattern 1 requires "search for" (but queries say "Find invoices containing")
- Pattern 2 requires "find invoice with GSTIN/number/#" (but "Find invoices containing label" doesn't have "with")
- Pattern 3, 4, 5, 6 all require "invoice" to be in a specific context
- Pattern 7 requires "invoices from [CAPITAL]" (but "label" and "printing" are lowercase)

None of these patterns match "Find invoices containing label products" or "Which invoices have printing services?"

#### Fallthrough Behavior:
After failing all BM25 patterns (line 374), the query falls through to:
- Line 388: Checking `_VECTOR_KEYWORDS` - "services" might match "services were" or fail
- Line 400: Falls back to HYBRID with low confidence (0.5)

## Why This Causes 0% Success Rate

Even though:
1. Line items ARE in the data ✅
2. Line items ARE indexed by BM25 ✅
3. BM25 CAN search for keywords like "sticker", "print", "label" ✅

The query gets routed to VECTOR or HYBRID instead of BM25, which:
- VECTOR: Uses semantic embeddings (might not match "label products" well)
- HYBRID: Combines both but may not prioritize exact keyword matches

The real problem is **query routing**, not the search functionality itself.

## Solution Required

Add line item search patterns to `_BM25_SEARCH_PATTERNS` in `router.py`:

```python
_BM25_SEARCH_PATTERNS = [
    # Existing patterns...
    r"\bfind.*\b(invoices?|documents?)\b.*\b(contain|with|have)\b",  # "Find invoices containing X"
    r"\b(which|what)\b.*\binvoices?\b.*\b(have|contain|with|include)\b",  # "Which invoices have X"
    r"\bshow.*\b(invoices?)\b.*\b(with|contain|include)\b.*\b(sticker|print|label|product)",  # Specific items
]
```

Then test with:
```python
route_query("Find invoices containing label products")  # Should return: strategy=bm25
route_query("Which invoices have printing services?")  # Should return: strategy=bm25
```

## Next Steps

1. Update `router.py` with line item search patterns
2. Re-test the router to ensure BM25 routing for these queries
3. Run test_suite_extended.py to verify line item search passes
4. Verify BM25 actually returns relevant results with proper scores
