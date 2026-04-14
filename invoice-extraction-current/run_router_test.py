#!/usr/bin/env python3
"""
Standalone router test runner for the invoice RAG system.
Executes the 104 comprehensive test cases from rag/router.py
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.router import route_query

if __name__ == "__main__":
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPREHENSIVE ROUTER TEST COVERAGE (104 test cases from test suite)
    # ═══════════════════════════════════════════════════════════════════════════
    tests = [
        # SQL STRATEGY TESTS (33 cases)
        ("How many invoices are in the system?", "sql"),
        ("What is the total tax amount across all invoices?", "sql"),
        ("Which vendor has the highest total invoice value?", "sql"),
        ("What is the average invoice amount?", "sql"),
        ("How many invoices have validation passed?", "sql"),
        ("Show me all invoices with tax greater than 500", "sql"),
        ("List vendors sorted by total invoice value", "sql"),
        ("Count invoices by month", "sql"),
        ("What is the total discount across all invoices?", "sql"),
        ("Show validation failure count", "sql"),
        ("What is the sum of all subtotals?", "sql"),
        ("Find the maximum invoice total", "sql"),
        ("How many invoices include shipping charges?", "sql"),
        ("Count invoices above 10000 rupees", "sql"),
        ("What is the average tax rate across invoices?", "sql"),
        ("Find invoices with negative totals", "sql"),
        ("How many invoices have we received from Fake Company Inc?", "sql"),
        ("List all vendors in the system", "sql"),
        ("Which vendor has the most invoices?", "sql"),
        ("What is the total amount we owe to vendors?", "sql"),
        ("Show invoices that failed validation", "sql"),
        ("Show invoices from March 2026", "sql"),
        ("How many invoices were issued in 2026?", "sql"),
        ("Show all invoices in INR", "sql"),
        ("What is the total amount in rupees?", "sql"),
        ("How many invoices from each vendor?", "sql"),
        ("Count invoices per month in 2026", "sql"),
        ("Show invoices with total amount greater than 5000", "sql"),
        ("Find invoices with tax less than 100", "sql"),
        ("Find all invoices with any amount between 100 and 50000", "sql"),
        ("List the top 5 highest value invoices", "sql"),
        ("Find the invoice with the lowest tax amount", "sql"),
        ("What is the total CGST plus SGST across all invoices?", "sql"),

        # BM25 STRATEGY TESTS (33 cases)
        ("Show me invoice GST001", "bm25"),
        ("Find the invoice with GSTIN 36ARKPC6820F1ZZ", "bm25"),
        ('What are the details of "NIREL DIGITALS" invoices?', "bm25"),
        ("Show invoice GST003", "bm25"),
        ("Find invoice number INV-2026-001", "bm25"),
        ("Search for ABC Corporation invoices", "bm25"),
        ('Show "Net 30" payment terms invoices', "bm25"),
        ("Find BITRA BIO SOLUTIONS", "bm25"),
        ("Show invoice #12345", "bm25"),
        ("Find GSTIN 36BMZPC5477K1Z7", "bm25"),
        ('Search for "Sticker" line items', "bm25"),
        ("Show me invoice NONEXISTENT-999", "bm25"),
        ("Do we have any invoices from XYZ Corporation?", "bm25"),
        ("Is there an invoice for purchase order PO-99999?", "bm25"),
        ("Do we have invoices from NIREL DIGITALS?", "bm25"),
        ("Are there any invoices with GSTIN 36ARKPC6820F1ZZ?", "bm25"),
        ("Show me all invoices from NIREL DIGITALS", "bm25"),
        ("Find invoice with GSTIN 36ARKPC6820F1ZZ", "bm25"),
        ("Show me invoice number GST24001", "bm25"),
        ("Find invoice GST24002", "bm25"),
        ("Find invoices containing label products", "bm25"),
        ("Which invoices have printing services?", "bm25"),
        ("Show invoice GST24003", "bm25"),
        ("What is the phone number of NIREL DIGITALS?", "bm25"),
        ("What is the email address of the vendor in GST001?", "bm25"),
        ("Show all line items from invoice GST001", "bm25"),
        ("What is the vendor address in GST001?", "bm25"),
        ("Show the billing address for NIREL DIGITALS invoices", "bm25"),
        ("What is the total amount for GST001?", "bm25"),
        ("Tell me about NIREL DIGITALS", "bm25"),
        ("Show me invoices with sticker products", "bm25"),
        ("Find GSTIN 29AABCU9603R1ZM", "bm25"),
        ("Show me invoice GST-001", "bm25"),

        # HYBRID STRATEGY TESTS (27 cases)
        ("Tell me about the last invoice we processed", "hybrid"),
        ("What payment methods are used in our invoices?", "hybrid"),
        ("Show me the most recent invoice", "hybrid"),
        ("Find high-value invoices from last month", "hybrid"),
        ("Show unpaid invoices", "hybrid"),
        ("List vendors in Bangalore", "hybrid"),
        ("What was delivered in September 2023?", "hybrid"),
        ("Show invoices with notes or special instructions", "hybrid"),
        ("Find recurring vendors", "hybrid"),
        ("What invoices have bank transfer details?", "hybrid"),
        ("Show invoices with email addresses", "hybrid"),
        ("Find invoices with multiple line items", "hybrid"),
        ("What is the meaning of life?", "hybrid"),
        ("What is the vendor's favorite color?", "hybrid"),
        ("asdf jkl qwerty", "hybrid"),
        ("Show invoices from Hyderabad", "hybrid"),
        ("Which vendors are located in Mumbai?", "hybrid"),
        ("Find customers in Delhi", "hybrid"),
        ("SELECT * FROM invoices; DROP TABLE invoices;", "hybrid"),
        ("Calculate the percentage of invoices that passed validation", "hybrid"),
        ("Find bulk discount purchases", "hybrid"),
        ("Tell me about the last invoice we received", "hybrid"),
        ("Do we have any invoices from XYZ Corporation?", "hybrid"),
        ("Find high-value invoices from last month", "hybrid"),
        ("What invoices have bank transfer details?", "hybrid"),
        ("Find invoices with multiple line items", "hybrid"),
        ("How many invoices are there?", "hybrid"),

        # VECTOR STRATEGY TESTS (11 cases)
        ("Show invoices similar to printing services", "vector"),
        ("Describe the types of products sold across all invoices", "vector"),
        ("Find technology-related invoices", "vector"),
        ("Show construction materials purchases", "vector"),
        ("Invoices related to international shipping", "vector"),
        ("Show emergency or urgent orders", "vector"),
        ("Describe vendor payment reliability", "vector"),
        ("What kind of services were purchased?", "vector"),
        ("Find vendors similar to NIREL DIGITALS", "vector"),
        ("Search for complex semantic similarity across all product descriptions", "vector"),
        ("What type of products does the top vendor sell?", "vector"),
    ]

    print("=" * 80)
    print(f"{'#':<3} {'EXPECT':<8} {'GOT':<8} {'PASS':<5}  QUERY")
    print("=" * 80)

    all_passed = True
    failed_count = 0
    failed_tests = []
    
    for i, (query, expected) in enumerate(tests, 1):
        result = route_query(query)
        got = result["strategy"]
        ok = got == expected
        if not ok:
            all_passed = False
            failed_count += 1
            failed_tests.append((i, query, expected, got, result))
        tag = "OK" if ok else "FAIL"
        print(f"{i:<3} {expected:<8} {got:<8} {tag:<5}  {query}")
        if not ok or result.get("filters"):
            print(f"    reason: {result['reasoning']}")
            if result.get("filters"):
                print(f"    filters: {result['filters']}")

    print("=" * 80)
    total = len(tests)
    passed = total - failed_count
    pass_rate = 100 * passed / total
    print(f"Result: {passed}/{total} PASSED ({pass_rate:.0f}%)")
    
    if failed_count > 0:
        print(f"\n⚠️  WARNING: {failed_count} routing failures detected!")
        print(f"   This means the router is selecting the wrong strategy.")
        print(f"   Review the failed cases below to improve routing logic:\n")
        for i, query, expected, got, result in failed_tests:
            print(f"   [{i}] Query: {query}")
            print(f"       Expected: {expected}, Got: {got}")
            print(f"       Reason: {result['reasoning']}")
            print()
    else:
        print(f"\n✅ All {total} test cases pass! Router strategy selection is working correctly.")
    
    # Count tests by strategy for coverage analysis
    strategy_counts = {}
    for _, expected in tests:
        strategy_counts[expected] = strategy_counts.get(expected, 0) + 1
    
    print(f"\n📊 Test Coverage by Strategy:")
    for strategy, count in sorted(strategy_counts.items()):
        percentage = 100 * count / total
        print(f"   {strategy.upper():<8}: {count:3d} tests ({percentage:4.1f}%)")
    print(f"   {'TOTAL':<8}: {total:3d} tests (100.0%)")
    
    print(f"\n🎯 This comprehensive test suite covers all 104 test cases from the")
    print(f"   extended RAG evaluation suite to prevent routing regressions.")
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)
