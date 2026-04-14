#!/usr/bin/env python3
"""
Line Item Search Test - Debug why line item search has 0% success rate

This script tests line item search functionality by:
1. Rebuilding BM25 index to ensure it's current
2. Testing exact queries from failing test cases
3. Checking both BM25 and vector search results
4. Verifying line item content is properly indexed
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent / "invoice-extraction-current"
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from core.config import BM25_INDEX_PATH, OUTPUTS_DIR
from rag.bm25_retriever import BM25Retriever
from rag.indexer import query_chunks

def test_line_item_searches():
    print("🔧 LINE ITEM SEARCH DEBUG")
    print("="*50)
    
    # Step 1: Rebuild BM25 index to ensure it's current
    print("1. Rebuilding BM25 index...")
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
    count = retriever.build_index(extractions_dir=str(OUTPUTS_DIR))
    print(f"✅ Indexed {count} documents")
    
    # Step 2: Test the failing line item queries
    test_queries = [
        'Search for "Sticker" line items',
        "Find invoices containing label products", 
        "Which invoices have printing services?",
        # Also test the misspelled version we found
        "Find Stciker products",
        "Digital print services"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing: '{query}'")
        print("-" * 60)
        
        # Test BM25 search
        print("BM25 Results:")
        try:
            bm25_results = retriever.search(query, top_k=10)
            if bm25_results:
                for i, result in enumerate(bm25_results[:5]):  # Show top 5
                    score = result.get('score', 0)
                    source = result.get('source_file', 'Unknown')
                    vendor = result.get('vendor_name', 'Unknown')
                    line_items = result.get('line_items_summary', 'No summary')
                    
                    print(f"  {i+1}. Score: {score:.3f}")
                    print(f"     File: {source}")
                    print(f"     Vendor: {vendor}")
                    print(f"     Line Items: {line_items[:100]}...")
                    
                    # Check if it contains what we're looking for
                    if any(word in line_items.lower() for word in ['sticker', 'stciker', 'print', 'label']):
                        print(f"     ✅ CONTAINS TARGET KEYWORDS!")
                    print()
            else:
                print("  ❌ No BM25 results found")
        except Exception as e:
            print(f"  ❌ BM25 Error: {e}")
        
        # Test Vector search
        print("Vector Search Results:")
        try:
            vector_results = query_chunks(query, n_results=5)
            if vector_results:
                for i, chunk in enumerate(vector_results):
                    metadata = chunk.get('metadata', {})
                    chunk_text = chunk.get('text', '')[:150]
                    chunk_type = metadata.get('chunk_type', 'unknown')
                    source_file = metadata.get('source_file', 'unknown')
                    
                    print(f"  {i+1}. Type: {chunk_type}, File: {source_file}")
                    print(f"     Text: {chunk_text}...")
                    
                    if chunk_type == 'line_item':
                        print(f"     ✅ FOUND LINE ITEM CHUNK!")
                    print()
            else:
                print("  ❌ No vector results found")
        except Exception as e:
            print(f"  ❌ Vector Error: {e}")
    
    # Step 3: Check specific invoices we know have line items
    print(f"\n📄 VERIFYING KNOWN INVOICES WITH LINE ITEMS")
    print("="*50)
    
    known_invoices = {
        "GST001": "Stciker - Size 13x19",
        "GST24005": "Sticker With Lamination", 
        "GST003": "Digital Print Out",
        "GST024028": "A4 Printouts"
    }
    
    for invoice_id, expected_item in known_invoices.items():
        print(f"Checking {invoice_id} for '{expected_item}':")
        
        # Search for the specific invoice
        results = retriever.search(invoice_id, top_k=3)
        found_invoice = False
        
        for result in results:
            if invoice_id in result.get('source_file', ''):
                found_invoice = True
                line_items = result.get('line_items_summary', '')
                print(f"  ✅ Found {invoice_id}")
                print(f"  Line items: {line_items}")
                
                if expected_item.lower() in line_items.lower():
                    print(f"  ✅ Contains expected item: '{expected_item}'")
                else:
                    print(f"  ⚠️  Does NOT contain '{expected_item}' in summary")
                break
        
        if not found_invoice:
            print(f"  ❌ Could not find {invoice_id} in BM25 results")
        print()
    
    print("🏁 LINE ITEM SEARCH DEBUG COMPLETE")
    print("="*50)

if __name__ == "__main__":
    test_line_item_searches()