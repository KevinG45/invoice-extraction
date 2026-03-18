"""
Query router for the invoice RAG system.

Classifies a user question into one of four retrieval strategies
using pure Python string matching and regex — no LLM calls.
"""

import re


# ── Keyword / pattern sets ──────────────────────────────────────────────────

_SQL_KEYWORDS = [
    "total", "sum", "count", "average", "avg",
    "how many", "highest", "lowest", "maximum", "minimum",
    "past due", "overdue", "greater than", "less than",
    "more than", "fewer than", "between",
    "most expensive", "cheapest",
    "group by", "per month", "per vendor", "per year",
]

# "top N" is SQL-style but plain "top vendor" is not
_TOP_N_RE = re.compile(r"\btop\s+\d+\b", re.IGNORECASE)

_VECTOR_KEYWORDS = [
    "similar to", "like", "unusual", "type of",
    "describe", "explain", "what kind", "related to",
    "category", "nature of",
]

# Invoice-number patterns: e.g. GST-001, INV-2024-001, INV/2024/001, #12345
_INVOICE_NUM_RE = re.compile(
    r"\b(?:GST|INV|BILL|PO|REC|QUOT|SO)[/-]?\d[\w/-]*\b",
    re.IGNORECASE,
)

# GSTIN pattern: 15-char alphanumeric Indian tax ID
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b")

# Quoted exact terms: "NIREL DIGITALS" or 'NIREL DIGITALS'
_QUOTED_RE = re.compile(r"""(['"])(.+?)\1""")

# All-caps vendor-style name: 2+ consecutive uppercase words (3+ chars each)
_ALLCAPS_NAME_RE = re.compile(r"\b(?:[A-Z]{3,}\s+){1,}[A-Z]{3,}\b")

# Date-range pattern: between <date> and <date>
_DATE_RANGE_RE = re.compile(
    r"between\s+(.+?)\s+and\s+(.+?)(?:\s|$|\?)", re.IGNORECASE
)

# Amount threshold: above/below/over/under ₹/$/Rs 1234
_AMOUNT_RE = re.compile(
    r"(?:above|below|over|under|exceeding|more than|less than|greater than)"
    r"\s*[₹$]?\s*[\d,]+(?:\.\d+)?",
    re.IGNORECASE,
)

# Vendor name in quotes or all-caps for filter extraction
_VENDOR_FILTER_RE = re.compile(
    r"(?:vendor|supplier|from|by)\s+[\"']?([A-Z][\w\s]+)[\"']?",
    re.IGNORECASE,
)


# ── Filter extraction helpers ───────────────────────────────────────────────

def _extract_filters(query: str) -> dict:
    """Pull structured filters out of the query string."""
    filters = {}

    # Date range
    m = _DATE_RANGE_RE.search(query)
    if m:
        filters["date_from"] = m.group(1).strip()
        filters["date_to"] = m.group(2).strip()

    # Amount threshold
    m = _AMOUNT_RE.search(query)
    if m:
        filters["amount_condition"] = m.group(0).strip()

    # Quoted vendor name
    m = _QUOTED_RE.search(query)
    if m:
        filters["vendor_name"] = m.group(2).strip()

    return filters


# ── Main router ─────────────────────────────────────────────────────────────

def route_query(query: str) -> dict:
    """Classify *query* into a retrieval strategy.

    Returns
    -------
    dict with keys: strategy, reasoning, sql_intent, filters
    """
    q_lower = query.lower()
    filters = _extract_filters(query)

    # ── Rule 1: SQL aggregation / analytics ──────────────────────────────
    for kw in _SQL_KEYWORDS:
        if kw in q_lower:
            return {
                "strategy": "sql",
                "reasoning": f"Query contains aggregation keyword '{kw}'.",
                "sql_intent": True,
                "filters": filters,
            }

    if _TOP_N_RE.search(query):
        return {
            "strategy": "sql",
            "reasoning": "Query asks for a top-N ranking.",
            "sql_intent": True,
            "filters": filters,
        }

    # ── Rule 2: Exact lookup (invoice number, GSTIN, exact name) ─────────
    if _INVOICE_NUM_RE.search(query):
        match = _INVOICE_NUM_RE.search(query).group(0)
        return {
            "strategy": "bm25",
            "reasoning": f"Query references a specific invoice number '{match}'.",
            "sql_intent": False,
            "filters": {**filters, "invoice_number": match},
        }

    if _GSTIN_RE.search(query):
        match = _GSTIN_RE.search(query).group(0)
        return {
            "strategy": "bm25",
            "reasoning": f"Query references a GSTIN '{match}'.",
            "sql_intent": False,
            "filters": {**filters, "gstin": match},
        }

    if _QUOTED_RE.search(query):
        match = _QUOTED_RE.search(query).group(2)
        return {
            "strategy": "bm25",
            "reasoning": f"Query contains a quoted exact term '{match}'.",
            "sql_intent": False,
            "filters": {**filters, "exact_term": match},
        }

    if _ALLCAPS_NAME_RE.search(query):
        match = _ALLCAPS_NAME_RE.search(query).group(0)
        return {
            "strategy": "bm25",
            "reasoning": f"Query references an all-caps name '{match}'.",
            "sql_intent": False,
            "filters": {**filters, "vendor_name": match},
        }

    # ── Rule 3: Fuzzy / semantic question ────────────────────────────────
    for kw in _VECTOR_KEYWORDS:
        if kw in q_lower:
            return {
                "strategy": "vector",
                "reasoning": f"Query uses semantic keyword '{kw}'.",
                "sql_intent": False,
                "filters": filters,
            }

    # ── Rule 4: Fall-through → hybrid ────────────────────────────────────
    return {
        "strategy": "hybrid",
        "reasoning": "No clear signal; using hybrid retrieval for best coverage.",
        "sql_intent": False,
        "filters": filters,
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # SQL (2 cases)
        ("What is the total amount for all invoices in March?",           "sql"),
        ("How many invoices did NIREL DIGITALS send?",                    "sql"),
        # BM25 (3 cases — invoice number, GSTIN, exact vendor name)
        ("Show me invoice GST-001",                                       "bm25"),
        ("Find the invoice with GSTIN 29AABCU9603R1ZM",                  "bm25"),
        ('What are the details of "CANAA CREATECH" invoices?',           "bm25"),
        # Vector (2 cases)
        ("Show invoices similar to printing services",                    "vector"),
        ("What type of products does the top vendor sell?",              "vector"),
        # Hybrid (1 case)
        ("Tell me about the last invoice we received",                   "hybrid"),
    ]

    print("=" * 68)
    print(f"{'#':<3} {'EXPECT':<8} {'GOT':<8} {'PASS':<5}  QUERY")
    print("=" * 68)

    all_passed = True
    for i, (query, expected) in enumerate(tests, 1):
        result = route_query(query)
        got = result["strategy"]
        ok = got == expected
        if not ok:
            all_passed = False
        tag = "OK" if ok else "FAIL"
        print(f"{i:<3} {expected:<8} {got:<8} {tag:<5}  {query}")
        print(f"    reason: {result['reasoning']}")
        if result["filters"]:
            print(f"    filters: {result['filters']}")

    print("=" * 68)
    print(f"Result: {'ALL 8 PASSED' if all_passed else 'SOME FAILED'}")
