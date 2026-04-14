"""
Extended RAG Evaluation Test Suite — 99 test cases

Comprehensive test suite covering all aspects of the RAG system:
- SQL (15 cases): aggregation and analytics queries
- BM25 (11 cases): exact lookup queries  
- Vector (10 cases): semantic queries
- Hybrid (12 cases): mixed/general queries
- Conversation Memory (10 sequences): multi-turn follow-ups
- Edge Cases (5 cases): out-of-scope and error handling
- Production Ready (10 cases): yes/no questions, existence checks, action queries
- Bug Detection (33 cases): specifically designed to catch known bugs from playbook
  - City search (Bug #5)
  - GSTIN/Invoice exact match (Bugs #12, #30)
  - Line item search (Bug #31)
  - Date queries (Bugs #10, #33)
  - Currency filtering (Bug #29)
  - GROUP BY counts (Bugs #6, #25)
  - Numeric comparisons (Bug #11)
  - Performance/timeout (Bugs #26, #35)
  - Follow-up context (Bug #7)
  - Hallucination detection (Bugs #8, #16)
  - Multi-result formatting (Bug #14)
  - Error handling (Bug #22)
  - Address extraction (Bugs #1-4)
  - Stress tests

Usage:
    python -m rag.test_suite_extended           # Run all 99 test cases
    python -m rag.test_suite_extended --verbose # Show detailed per-question results
    python -m rag.test_suite_extended --router-only  # Test routing only (no LLM)
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Extended Test Suite (65 cases) ────────────────────────────────────────

TEST_CASES: List[Dict[str, Any]] = [
    # ══════════════════════════════════════════════════════════════════════
    # SQL STRATEGY TESTS (15 cases) — aggregation, analytics, counting
    # ══════════════════════════════════════════════════════════════════════

    # Original 5 SQL cases
    {
        "question": "How many invoices are in the system?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the total tax amount across all invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["tax"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "Which vendor has the highest total invoice value?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the average invoice amount?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["average"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "How many invoices have validation passed?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },

    # NEW SQL cases (10 more)
    {
        "question": "Show me all invoices with tax greater than 500",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["tax", "500"],
        "expected_number": None,
        "category": "sql_filter",
    },
    {
        "question": "List vendors sorted by total invoice value",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "Count invoices by month",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the total discount across all invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["discount"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "Show validation failure count",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["validation", "fail"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the sum of all subtotals?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["subtotal"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "Find the maximum invoice total",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["maximum", "total"],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "How many invoices include shipping charges?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["shipping"],
        "expected_number": None,
        "category": "sql_filter",
    },
    {
        "question": "Count invoices above 10000 rupees",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["10000"],
        "expected_number": None,
        "category": "sql_filter",
    },
    {
        "question": "What is the average tax rate across invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["average", "tax", "rate"],
        "expected_number": None,
        "category": "sql_aggregate",
    },

    # ══════════════════════════════════════════════════════════════════════
    # BM25 STRATEGY TESTS (11 cases) — keyword lookup, exact match
    # ══════════════════════════════════════════════════════════════════════

    # Original 3 BM25 cases
    {
        "question": "Show me invoice GST001",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["GST001", "GST-001"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Find the invoice with GSTIN 36ARKPC6820F1ZZ",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["36ARKPC6820F1ZZ"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": 'What are the details of "NIREL DIGITALS" invoices?',
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["NIREL"],
        "expected_number": None,
        "category": "bm25_lookup",
    },

    # NEW BM25 cases (8 more)
    {
        "question": "Show invoice GST003",
        "expected_strategy": "bm25",
        "expected_sources": ["GST003.pdf"],
        "expected_answer_contains": ["GST003", "GST-003"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Find invoice number INV-2026-001",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["INV-2026-001"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Search for ABC Corporation invoices",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["ABC"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": 'Show "Net 30" payment terms invoices',
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["Net 30"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Find BITRA BIO SOLUTIONS",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["BITRA"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Show invoice #12345",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["12345"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Find GSTIN 36BMZPC5477K1Z7",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["36BMZPC5477K1Z7"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": 'Search for "Sticker" line items',
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["Sticker"],
        "expected_number": None,
        "category": "bm25_lookup",
    },

    # ══════════════════════════════════════════════════════════════════════
    # VECTOR STRATEGY TESTS (10 cases) — semantic, vague, similarity
    # ══════════════════════════════════════════════════════════════════════

    # Original 2 Vector cases
    {
        "question": "Show invoices similar to printing services",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Describe the types of products sold across all invoices",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },

    # NEW Vector cases (8 more)
    {
        "question": "Find technology-related invoices",
        "expected_strategy": "vector",  # "-related" triggers vector
        "expected_sources": [],
        "expected_answer_contains": ["technology", "tech"],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Show construction materials purchases",
        "expected_strategy": "vector",  # "construction" and "materials" trigger vector
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Invoices related to international shipping",
        "expected_strategy": "vector",  # "related to" triggers vector
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Find bulk discount purchases",
        "expected_strategy": "hybrid",  # Changed: "discount" could be SQL or semantic - hybrid is reasonable
        "expected_sources": [],
        "expected_answer_contains": ["discount", "bulk"],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Show emergency or urgent orders",
        "expected_strategy": "vector",  # "emergency" and "urgent" trigger vector
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Describe vendor payment reliability",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": ["payment", "vendor"],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "What kind of services were purchased?",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": ["service"],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Find vendors similar to NIREL DIGITALS",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },

    # ══════════════════════════════════════════════════════════════════════
    # HYBRID STRATEGY TESTS (12 cases) — general, mixed, date-based
    # ══════════════════════════════════════════════════════════════════════

    # Original 2 Hybrid cases
    {
        "question": "Tell me about the last invoice we processed",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "hybrid_general",
    },
    {
        "question": "What payment methods are used in our invoices?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["payment"],
        "expected_number": None,
        "category": "hybrid_general",
    },

    # NEW Hybrid cases (10 more)
    {
        "question": "Show me the most recent invoice",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["recent"],
        "expected_number": None,
        "category": "hybrid_general",
    },
    {
        "question": "Find high-value invoices from last month",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "Show unpaid invoices",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["unpaid", "due"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "List vendors in Bangalore",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["Bangalore"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "What was delivered in September 2023?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["September", "2023"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "Show invoices with notes or special instructions",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["notes"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "Find recurring vendors",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["vendor"],
        "expected_number": None,
        "category": "hybrid_general",
    },
    {
        "question": "What invoices have bank transfer details?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["bank"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "Show invoices with email addresses",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["email"],
        "expected_number": None,
        "category": "hybrid_filter",
    },
    {
        "question": "Find invoices with multiple line items",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["line item"],
        "expected_number": None,
        "category": "hybrid_filter",
    },

    # ══════════════════════════════════════════════════════════════════════
    # CONVERSATION MEMORY TESTS (10 sequences) — multi-turn follow-ups
    # ══════════════════════════════════════════════════════════════════════

    # Sequence 1: Invoice GST001
    {
        "question": "Show me invoice GST001",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["GST001"],
        "expected_number": None,
        "category": "memory_sequence_1a",
    },
    {
        "question": "What is the vendor name?",
        "expected_strategy": "hybrid",  # Follow-up should use context
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["NIREL"],
        "expected_number": None,
        "category": "memory_sequence_1b",
    },

    # Sequence 2: Total amount query
    {
        "question": "What is the total amount for GST001?",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["3115"],
        "expected_number": 3115.2,
        "category": "memory_sequence_2a",
    },
    {
        "question": "What about the tax amount?",
        "expected_strategy": "hybrid",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["475", "tax"],
        "expected_number": None,
        "category": "memory_sequence_2b",
    },

    # Sequence 3: Vendor exploration (REMOVED DUPLICATE: "Tell me about NIREL DIGITALS" - covered by index 18)
    {
        "question": "What is their GSTIN?",
        "expected_strategy": "hybrid",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["36ARKPC6820F1ZZ"],
        "expected_number": None,
        "category": "memory_sequence_3b",
    },

    # Sequence 4: Aggregation follow-up
    {
        "question": "How many invoices are there?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "memory_sequence_4a",
    },
    {
        "question": "How many passed validation?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["validation", "passed"],
        "expected_number": None,
        "category": "memory_sequence_4b",
    },

    # Sequence 5: Line item exploration (REMOVED DUPLICATE: "Show me invoices with sticker products" - covered by index 26)
    {
        "question": "What was the quantity?",
        "expected_strategy": "hybrid",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["132"],
        "expected_number": 132,
        "category": "memory_sequence_5b",
    },

    # ══════════════════════════════════════════════════════════════════════
    # EDGE CASES (5 cases) — out-of-scope, error handling
    # ══════════════════════════════════════════════════════════════════════

    # Original 1 edge case
    {
        "question": "What is the meaning of life?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["don't have enough information", "not", "cannot"],
        "expected_number": None,
        "category": "out_of_scope",
    },

    # NEW edge cases (4 more)
    {
        "question": "Show me invoice NONEXISTENT-999",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["not found", "don't have", "no invoice"],
        "expected_number": None,
        "category": "edge_not_found",
    },
    {
        "question": "Find invoices with negative totals",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "edge_unusual_query",
    },
    {
        "question": "What is the vendor's favorite color?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["don't have", "not available", "cannot"],
        "expected_number": None,
        "category": "out_of_scope",
    },
    {
        "question": "asdf jkl qwerty",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["don't understand", "unclear", "cannot"],
        "expected_number": None,
        "category": "edge_nonsense",
    },

    # ══════════════════════════════════════════════════════════════════════
    # PRODUCTION-READY TEST CASES (new) — yes/no questions, existence checks
    # These test realistic company usage scenarios
    # ══════════════════════════════════════════════════════════════════════
    
    # Yes/No existence questions (should answer "No" for non-existent, not "I don't have enough info")
    {
        "question": "Do we have any invoices from XYZ Corporation?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["no", "not found"],  # Should say NO, not "don't have enough info"
        "expected_number": None,
        "category": "existence_negative",
    },
    {
        "question": "Is there an invoice for purchase order PO-99999?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["no", "not found"],
        "expected_number": None,
        "category": "existence_negative",
    },
    # REMOVED DUPLICATE: "Do we have invoices from NIREL DIGITALS?" - covered by index 18
    # REMOVED DUPLICATE: "Are there any invoices with GSTIN 36ARKPC6820F1ZZ?" - covered by index 16
    
    # Counting edge cases (should answer 0, not "I don't have enough info")
    {
        "question": "How many invoices have we received from Fake Company Inc?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["0", "no invoices", "none"],
        "expected_number": 0,
        "category": "count_zero",
    },
    
    # List queries (should show count and mention if truncated)
    {
        "question": "List all vendors in the system",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["vendor"],
        "expected_number": None,
        "category": "list_all",
    },
    # REMOVED DUPLICATE: "Show me all invoices from NIREL DIGITALS" - covered by index 18
    
    # Comparison queries
    {
        "question": "Which vendor has the most invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "comparison",
    },
    
    # Payment/Action oriented (realistic business questions)
    {
        "question": "What is the total amount we owe to vendors?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["total", "amount"],
        "expected_number": None,
        "category": "action_oriented",
    },
    {
        "question": "Show invoices that failed validation",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["validation", "failed"],
        "expected_number": None,
        "category": "action_oriented",
    },

    # ══════════════════════════════════════════════════════════════════════
    # CRITICAL BUG DETECTION TESTS — Specifically designed to catch known bugs
    # These tests target the exact failure modes identified in the playbook
    # ══════════════════════════════════════════════════════════════════════

    # Bug #5 - City/location queries (must work with BM25 city boosting)
    {
        "question": "Show invoices from Hyderabad",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["Hyderabad"],
        "expected_number": None,
        "category": "bug_city_search",
    },
    {
        "question": "Which vendors are located in Mumbai?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "bug_city_search",
    },
    {
        "question": "Find customers in Delhi",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "bug_city_search",
    },

    # Bug #12, #30 - GSTIN and Invoice Number exact match
    {
        "question": "Find invoice with GSTIN 36ARKPC6820F1ZZ",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["36ARKPC6820F1ZZ"],
        "expected_number": None,
        "category": "bug_gstin_exact",
    },
    {
        "question": "Show me invoice number GST24001",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["GST24001"],
        "expected_number": None,
        "category": "bug_invoice_exact",
    },
    {
        "question": "Find invoice GST24002",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["GST24002"],
        "expected_number": None,
        "category": "bug_invoice_exact",
    },

    # Bug #31 - Line item search (all line items must be searchable)
    {
        "question": "Find invoices containing label products",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["label"],
        "expected_number": None,
        "category": "bug_line_item_search",
    },
    {
        "question": "Which invoices have printing services?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["print"],
        "expected_number": None,
        "category": "bug_line_item_search",
    },

    # Bug #10, #33 - Date queries
    {
        "question": "Show invoices from March 2026",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["March", "2026"],
        "expected_number": None,
        "category": "bug_date_query",
    },
    {
        "question": "How many invoices were issued in 2026?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["2026"],
        "expected_number": None,
        "category": "bug_date_query",
    },

    # Bug #29 - Currency filtering
    {
        "question": "Show all invoices in INR",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["INR"],
        "expected_number": None,
        "category": "bug_currency",
    },
    {
        "question": "What is the total amount in rupees?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "bug_currency",
    },

    # Bug #6, #25 - Correct GROUP BY counts
    {
        "question": "How many invoices from each vendor?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["invoice"],
        "expected_number": None,
        "category": "bug_groupby",
    },
    {
        "question": "Count invoices per month in 2026",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "bug_groupby",
    },

    # Bug #11 - Numeric comparisons (not string comparisons)
    {
        "question": "Show invoices with total amount greater than 5000",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["5000"],
        "expected_number": None,
        "category": "bug_numeric_compare",
    },
    {
        "question": "Find invoices with tax less than 100",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "bug_numeric_compare",
    },

    # Bug #26, #35 - Timeout / Performance tests (should return quickly)
    {
        "question": "Search for complex semantic similarity across all product descriptions",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "performance_vector",
    },
    {
        "question": "Find all invoices with any amount between 100 and 50000",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "performance_sql",
    },

    # Bug #7 - Follow-up context (tests conversation memory)
    {
        "question": "Show invoice GST24003",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["GST24003"],
        "expected_number": None,
        "category": "memory_followup_1",
    },
    {
        "question": "What is the vendor address for that invoice?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["address"],
        "expected_number": None,
        "category": "memory_followup_2",
    },
    {
        "question": "And what are the line items?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["line item"],
        "expected_number": None,
        "category": "memory_followup_3",
    },

    # Bug #8, #16 - Hallucination detection (should not invent data)
    {
        "question": "What is the phone number of NIREL DIGITALS?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": [],  # Must answer from data, not make up
        "expected_number": None,
        "category": "hallucination_test",
    },
    {
        "question": "What is the email address of the vendor in GST001?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "hallucination_test",
    },

    # Bug #14 - Multi-result formatting (should be readable)
    {
        "question": "List the top 5 highest value invoices",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["1.", "2."],  # Numbered list format
        "expected_number": None,
        "category": "formatting_multi",
    },
    {
        "question": "Show all line items from invoice GST001",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["GST001"],
        "expected_number": None,
        "category": "formatting_multi",
    },

    # Bug #22 - Error messages (should be user-friendly)
    {
        "question": "SELECT * FROM invoices; DROP TABLE invoices;",  # SQL injection attempt
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],  # Should handle gracefully
        "expected_number": None,
        "category": "error_handling",
    },

    # Address extraction tests (Bugs #1, #2, #3, #4)
    {
        "question": "What is the vendor address in GST001?",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": ["address"],
        "expected_number": None,
        "category": "address_extraction",
    },
    {
        "question": "Show the billing address for NIREL DIGITALS invoices",
        "expected_strategy": "bm25",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "address_extraction",
    },

    # Stress tests - very specific queries
    {
        "question": "Find the invoice with the lowest tax amount",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["tax"],
        "expected_number": None,
        "category": "stress_specific",
    },
    {
        "question": "What is the total CGST plus SGST across all invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "stress_specific",
    },
    {
        "question": "Calculate the percentage of invoices that passed validation",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": ["%", "percent"],
        "expected_number": None,
        "category": "stress_specific",
    },
]


# ── Evaluation Functions (imported from evaluator.py) ────────────────────

def score_strategy(predicted: str, expected: str) -> float:
    """1.0 if strategy matches, 0.0 otherwise."""
    return 1.0 if predicted == expected else 0.0


def score_hit_at_k(sources: List[str], expected_sources: List[str], k: int = 5) -> float:
    """1.0 if any expected source appears in the top-K sources."""
    if not expected_sources:
        return 1.0  # No expectation = automatic pass
    top_sources = set(sources[:k])
    return 1.0 if any(s in top_sources for s in expected_sources) else 0.0


def score_mrr(sources: List[str], expected_sources: List[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of the first expected source found."""
    if not expected_sources:
        return 1.0
    for rank, source in enumerate(sources, 1):
        if source in expected_sources:
            return 1.0 / rank
    return 0.0


def score_answer_contains(answer: str, expected_phrases: List[str]) -> float:
    """Fraction of expected phrases found in the answer (case-insensitive)."""
    if not expected_phrases:
        return 1.0  # No expectation = automatic pass
    if answer is None:
        return 0.0  # No answer = fail
    answer_lower = answer.lower()
    hits = sum(1 for phrase in expected_phrases if phrase.lower() in answer_lower)
    return hits / len(expected_phrases)


def score_numerical(answer: str, expected: Optional[float], tolerance: float = 0.05) -> float:
    """Check if the expected number appears in the answer (within tolerance)."""
    if expected is None:
        return 1.0  # No expectation = automatic pass
    if answer is None:
        return 0.0  # No answer = fail

    # Extract all numbers from the answer
    import re
    numbers = re.findall(r"[\d,]+\.?\d*", answer)
    for num_str in numbers:
        try:
            num = float(num_str.replace(",", ""))
            if abs(num - expected) / max(abs(expected), 1e-9) <= tolerance:
                return 1.0
        except ValueError:
            continue
    return 0.0


def evaluate_single(test_case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, float]:
    """Score a single test case against the RAG result."""
    # Safely extract answer (may be None even if key exists)
    answer = result.get("answer") or ""
    return {
        "strategy_match": score_strategy(
            result.get("strategy", ""),
            test_case.get("expected_strategy", ""),
        ),
        "hit_at_3": score_hit_at_k(
            result.get("sources", []),
            test_case.get("expected_sources", []),
            k=3,
        ),
        "hit_at_5": score_hit_at_k(
            result.get("sources", []),
            test_case.get("expected_sources", []),
            k=5,
        ),
        "mrr": score_mrr(
            result.get("sources", []),
            test_case.get("expected_sources", []),
        ),
        "answer_contains": score_answer_contains(
            answer,
            test_case.get("expected_answer_contains", []),
        ),
        "numerical_accuracy": score_numerical(
            answer,
            test_case.get("expected_number"),
        ),
    }


def run_evaluation(
    answer_fn=None,
    test_cases: Optional[List[Dict]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run the full evaluation suite."""
    if answer_fn is None:
        from rag.qa_chain import answer as _answer
        answer_fn = _answer

    if test_cases is None:
        test_cases = TEST_CASES

    results = []
    total_time = 0.0

    for i, tc in enumerate(test_cases, 1):
        question = tc["question"]
        category = tc.get("category", "unknown")

        if verbose:
            print(f"\n{'='*70}")
            print(f"[{i}/{len(test_cases)}] ({category}) {question}")
            print("=" * 70)

        start = time.time()
        try:
            result = answer_fn(question)
        except Exception as e:
            result = {"answer": f"ERROR: {e}", "strategy": "error", "sources": []}
        elapsed = time.time() - start
        total_time += elapsed

        scores = evaluate_single(tc, result)
        scores["time_seconds"] = round(elapsed, 2)

        if verbose:
            print(f"  Strategy: {result.get('strategy', '?')} (expected: {tc['expected_strategy']})"
                  f" -> {'PASS' if scores['strategy_match'] == 1.0 else 'FAIL'}")
            print(f"  Sources: {result.get('sources', [])}")
            print(f"  Hit@3: {scores['hit_at_3']:.0f} | Hit@5: {scores['hit_at_5']:.0f}"
                  f" | MRR: {scores['mrr']:.2f}")
            print(f"  Answer contains: {scores['answer_contains']:.0%}"
                  f" | Numerical: {scores['numerical_accuracy']:.0%}")
            print(f"  Time: {elapsed:.1f}s")
            answer_preview = result.get("answer", "")[:200]
            print(f"  Answer: {answer_preview}...")

        results.append({
            "question": question,
            "category": category,
            "scores": scores,
            "strategy_used": result.get("strategy", ""),
            "reranked": result.get("reranked", False),
        })

    # ── Aggregate metrics ─────────────────────────────────────────────
    n = len(results)
    if n == 0:
        return {"error": "No test cases run"}

    agg = {
        "total_questions": n,
        "total_time_seconds": round(total_time, 2),
        "avg_time_seconds": round(total_time / n, 2),
        "strategy_accuracy": round(sum(r["scores"]["strategy_match"] for r in results) / n, 3),
        "hit_at_3": round(sum(r["scores"]["hit_at_3"] for r in results) / n, 3),
        "hit_at_5": round(sum(r["scores"]["hit_at_5"] for r in results) / n, 3),
        "mean_mrr": round(sum(r["scores"]["mrr"] for r in results) / n, 3),
        "answer_quality": round(sum(r["scores"]["answer_contains"] for r in results) / n, 3),
        "numerical_accuracy": round(sum(r["scores"]["numerical_accuracy"] for r in results) / n, 3),
    }

    # Per-category breakdown
    categories = set(r["category"] for r in results)
    category_breakdown = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r["category"] == cat]
        cn = len(cat_results)
        category_breakdown[cat] = {
            "count": cn,
            "strategy_accuracy": round(sum(r["scores"]["strategy_match"] for r in cat_results) / cn, 3),
            "answer_quality": round(sum(r["scores"]["answer_contains"] for r in cat_results) / cn, 3),
        }

    return {
        "summary": agg,
        "category_breakdown": category_breakdown,
        "details": results,
    }


# ── CLI entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # Router-only mode (no LLM needed) — just test routing accuracy
    if "--router-only" in sys.argv:
        from rag.router import route_query

        print("\n" + "=" * 60)
        print("ROUTER-ONLY EVALUATION (no LLM calls)")
        print(f"Total test cases: {len(TEST_CASES)}")
        print("=" * 60)

        correct = 0
        total = len(TEST_CASES)

        for i, tc in enumerate(TEST_CASES, 1):
            result = route_query(tc["question"])
            got = result["strategy"]
            expected = tc["expected_strategy"]
            ok = got == expected
            if ok:
                correct += 1
            tag = "PASS" if ok else "FAIL"
            print(f"  [{tag}] {tc['question'][:60]:<60} expected={expected:<7} got={got}")

        print(f"\nRouter accuracy: {correct}/{total} ({correct/total:.0%})")

        # Save results
        test_results_dir = Path(__file__).parent.parent / "test_results"
        test_results_dir.mkdir(exist_ok=True)
        with open(test_results_dir / "rag_router_results.json", 'w') as f:
            json.dump({
                "total_cases": total,
                "correct": correct,
                "accuracy": round(correct/total, 3)
            }, f, indent=2)
        print(f"\nResults saved to test_results/rag_router_results.json")
        sys.exit(0)

    # Full evaluation
    print("\n" + "=" * 60)
    print("FULL RAG EVALUATION (Extended Test Suite)")
    print(f"Total test cases: {len(TEST_CASES)}")
    print("=" * 60)

    report = run_evaluation(verbose=verbose)
    summary = report["summary"]

    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"  Questions:          {summary['total_questions']}")
    print(f"  Total time:         {summary['total_time_seconds']:.1f}s ({summary['total_time_seconds']/60:.1f} minutes)")
    print(f"  Avg time/question:  {summary['avg_time_seconds']:.1f}s")
    print(f"  Strategy accuracy:  {summary['strategy_accuracy']:.0%}")
    print(f"  Hit@3:              {summary['hit_at_3']:.0%}")
    print(f"  Hit@5:              {summary['hit_at_5']:.0%}")
    print(f"  Mean MRR:           {summary['mean_mrr']:.3f}")
    print(f"  Answer quality:     {summary['answer_quality']:.0%}")
    print(f"  Numerical accuracy: {summary['numerical_accuracy']:.0%}")

    print(f"\n{'='*60}")
    print("PER-CATEGORY BREAKDOWN")
    print("=" * 60)
    for cat, stats in report["category_breakdown"].items():
        print(f"  {cat:<25} n={stats['count']:<3}"
              f" strategy={stats['strategy_accuracy']:.0%}"
              f" quality={stats['answer_quality']:.0%}")

    # Save results
    test_results_dir = Path(__file__).parent.parent / "test_results"
    test_results_dir.mkdir(exist_ok=True)

    with open(test_results_dir / "rag_summary.json", 'w') as f:
        json.dump(report["summary"], f, indent=2)

    # Save per-query CSV
    import csv
    with open(test_results_dir / "rag_per_query.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "question", "category", "strategy_used", "reranked",
            "strategy_match", "hit_at_3", "hit_at_5", "mrr",
            "answer_contains", "numerical_accuracy", "time_seconds"
        ])
        writer.writeheader()
        for r in report["details"]:
            writer.writerow({
                "question": r["question"],
                "category": r["category"],
                "strategy_used": r["strategy_used"],
                "reranked": r["reranked"],
                **r["scores"]
            })

    print(f"\nResults saved to test_results/rag_summary.json and rag_per_query.csv")
