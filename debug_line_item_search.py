#!/usr/bin/env python3
"""
Line Item Search Forensic Analysis
==================================
Deep investigation of why line item searches fail despite correct BM25 indexing logic.

ISSUE: Line item search shows 0% success rate
ROOT CAUSE: Need to verify actual BM25 index contents vs expectations
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'invoice-extraction-current'))

from rag.bm25_retriever import BM25Retriever
from rag.database_config import get_database_connection

def test_line_item_indexing_and_search():
    """Verify if BM25 index actually contains line item descriptions."""
    
    print("=" * 60)
    print("LINE ITEM SEARCH FORENSIC ANALYSIS") 
    print("=" * 60)
    
    # Initialize BM25 retriever
    conn = get_database_connection()
    retriever = BM25Retriever(database_path="invoice-extraction-current/data/invoices.db")
    
    # Test 1: Check if _build_document_string includes line items
    print("\n1. Testing document string building...")
    
    # Get a sample invoice with line items
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_id, invoice_number FROM invoices LIMIT 3")
    sample_invoices = cursor.fetchall()
    
    for invoice_id, invoice_number in sample_invoices:
        print(f"\nInvoice {invoice_number} (ID: {invoice_id}):")
        
        # Check line items in database
        cursor.execute("SELECT description, quantity, unit_price FROM line_items WHERE invoice_id = ?", (invoice_id,))
        line_items = cursor.fetchall()
        print(f"   Database line items: {len(line_items)}")
        
        if line_items:
            for i, (desc, qty, price) in enumerate(line_items[:2]):  # First 2
                print(f"   #{i+1}: {desc} (qty: {qty}, price: {price})")
        
        # Check what _build_document_string produces
        if hasattr(retriever, '_build_document_string'):
            try:
                doc_string = retriever._build_document_string(invoice_id)
                print(f"   Document string length: {len(doc_string)}")
                print(f"   Contains 'item' or 'description': {'item' in doc_string.lower() or 'description' in doc_string.lower()}")
                
                # Show snippet containing line items
                lines = doc_string.split('\n')
                line_item_lines = [line for line in lines if 'item' in line.lower() or 'description' in line.lower()]
                if line_item_lines:
                    print(f"   Line item content sample: {line_item_lines[0][:80]}...")
                else:
                    print("   ⚠️  NO line item content found in document string")
                    
            except Exception as e:
                print(f"   ✗ _build_document_string failed: {e}")
        else:
            print("   ✗ _build_document_string method not found")
    
    # Test 2: Search for actual line item content
    print("\n2. Testing line item search...")
    
    test_queries = [
        "LCD Display Screen",
        "item description", 
        "product details",
        "service charges",
        "materials"
    ]
    
    for query in test_queries:
        print(f"\nSearching for: '{query}'")
        try:
            results = retriever.retrieve(query, k=3)
            print(f"   Results found: {len(results)}")
            
            for i, result in enumerate(results[:2]):  # First 2
                print(f"   #{i+1}: {result.get('invoice_number', 'N/A')} (score: {result.get('score', 'N/A')})")
                content = result.get('content', '')
                if 'item' in content.lower() or query.lower() in content.lower():
                    print(f"        ✓ Contains relevant content")
                else:
                    print(f"        ⚠️  No relevant content found")
                    
        except Exception as e:
            print(f"   ✗ Search failed: {e}")
    
    # Test 3: BM25 index inspection
    print("\n3. Inspecting BM25 index structure...")
    
    if hasattr(retriever, 'bm25') and retriever.bm25:
        print(f"   BM25 object exists: {type(retriever.bm25)}")
        print(f"   Document count: {len(retriever.bm25.corpus) if hasattr(retriever.bm25, 'corpus') else 'Unknown'}")
        
        # Check vocabulary for line item terms
        line_item_terms = ['item', 'description', 'product', 'service', 'material', 'lcd', 'display']
        if hasattr(retriever.bm25, 'doc_freqs'):
            found_terms = [term for term in line_item_terms if term in retriever.bm25.doc_freqs]
            print(f"   Line item terms in vocabulary: {found_terms}")
        else:
            print("   Cannot inspect vocabulary (doc_freqs not available)")
    else:
        print("   ✗ BM25 object not initialized")
    
    # Test 4: Router patterns verification
    print("\n4. Checking router patterns for line items...")
    try:
        from rag.router import Router
        router = Router(database_path="invoice-extraction-current/data/invoices.db")
        
        if hasattr(router, 'bm25_patterns'):
            line_item_patterns = [p for p in router.bm25_patterns if 'item' in p.lower() or 'product' in p.lower()]
            print(f"   Line item patterns in router: {len(line_item_patterns)}")
            for pattern in line_item_patterns:
                print(f"   - {pattern}")
        
        # Test routing for line item queries
        for query in ["what are the line items", "show me the products"]:
            route_result = router.route_query(query)
            print(f"   Query: '{query}' → Strategy: {route_result.get('strategy', 'Unknown')}")
            
    except Exception as e:
        print(f"   ✗ Router inspection failed: {e}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_line_item_indexing_and_search()