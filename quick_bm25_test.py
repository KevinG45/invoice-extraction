#!/usr/bin/env python3
"""
Quick BM25 Line Item Test
=========================
Simple test to verify if BM25 index contains line item data and if search works.
"""

import os
import sys
import sqlite3

def quick_bm25_test():
    """Quick test of BM25 line item functionality."""
    
    print("QUICK BM25 LINE ITEM TEST")
    print("=" * 40)
    
    # Setup
    current_dir = os.getcwd()
    invoice_current = os.path.join(current_dir, 'invoice-extraction-current')
    
    if not os.path.exists(invoice_current):
        print(f"✗ invoice-extraction-current not found")
        return False
    
    sys.path.insert(0, invoice_current)
    
    try:
        # Test 1: Check database has line items
        db_path = os.path.join(invoice_current, 'data', 'invoices.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM line_items")
        count = cursor.fetchone()[0]
        print(f"✓ Database has {count:,} line items")
        
        # Test 2: Get sample line item descriptions
        cursor.execute("SELECT description FROM line_items WHERE description IS NOT NULL LIMIT 5")
        descriptions = [row[0] for row in cursor.fetchall()]
        print(f"✓ Sample descriptions: {descriptions[:2]}")
        conn.close()
        
        # Test 3: Import and test BM25Retriever
        from rag.bm25_retriever import BM25Retriever
        retriever = BM25Retriever(database_path=db_path)
        print(f"✓ BM25Retriever initialized")
        
        # Test 4: Search for actual line item content
        test_queries = ["LCD Display", "Keyboard", "line items"]
        
        for query in test_queries:
            results = retriever.retrieve(query, k=3)
            print(f"Query '{query}': {len(results)} results")
            
            if results:
                # Check if any result contains the query term
                found_match = False
                for result in results:
                    content = result.get('content', '')
                    if query.lower() in content.lower():
                        found_match = True
                        break
                        
                if found_match:
                    print(f"  ✓ Found matching content")
                else:
                    print(f"  ⚠️  No matching content (possible index issue)")
            else:
                print(f"  ✗ No results found")
                
        print("\n" + "=" * 40)
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = quick_bm25_test()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")