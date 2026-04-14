#!/usr/bin/env python3
"""
Targeted test of 5 critical failing cases to validate fixes.
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from rag.qa_chain import answer_question
from rag.router import is_follow_up
import uuid

def run_quick_validation():
    """Test 5 critical cases that were previously failing"""
    
    session_id = str(uuid.uuid4())
    
    print("=== QUICK VALIDATION TEST ===")
    print(f"Session ID: {session_id}")
    print()
    
    # Test 1: Follow-up detection fix
    print("1. Follow-up Detection Test")
    print("-" * 30)
    
    test_queries = [
        ("Show 'Net 30' payment terms invoices", "Should be FALSE"),
        ("What is the vendor name?", "Should be TRUE"),
    ]
    
    for query, desc in test_queries:
        result = is_follow_up(query)
        print(f"   '{query}' -> {result} ({desc})")
    print()
    
    # Test 2: BM25 line item query (previously failed)
    print("2. BM25 Line Item Query")
    print("-" * 30)
    result = answer_question("Show line items for invoice GST001", session_id=session_id)
    print(f"   Strategy: {result['strategy']} (expected: bm25)")
    print(f"   Answer: {result['answer'][:100]}...")
    print()
    
    # Test 3: Memory sequence (store then follow-up)
    print("3. Memory System Test")
    print("-" * 30)
    
    # Store entities first
    result1 = answer_question("Show me invoice GST001", session_id=session_id)
    print(f"   Step 1 - Strategy: {result1['strategy']}")
    
    # Try follow-up
    result2 = answer_question("What is the vendor name?", session_id=session_id)
    print(f"   Step 2 - Strategy: {result2['strategy']} (expected: memory_direct or bm25)")
    print(f"   Answer: {result2['answer'][:80]}...")
    
    if "NIREL" in result2['answer'].upper():
        print("   ✅ Memory or fallback worked - found vendor!")
    else:
        print("   ❌ Still failing to get vendor info")
    
    print()
    
    # Test 4: SQL aggregate (should work)
    print("4. SQL Aggregate Query")
    print("-" * 30)
    result = answer_question("How many invoices are in the system?", session_id=session_id)
    print(f"   Strategy: {result['strategy']} (expected: sql)")
    print(f"   Answer: {result['answer'][:50]}...")
    print()
    
    print("=== END VALIDATION ===")

if __name__ == "__main__":
    run_quick_validation()