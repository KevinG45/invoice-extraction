#!/usr/bin/env python3
"""
BM25 Line Item Index Verification
=================================
Comprehensive investigation to verify BM25 index actually contains line item data.

ISSUE: Line item search shows 0% success despite correct indexing logic
GOAL: Identify if issue is in indexing, searching, or routing
"""

import os
import sys
import sqlite3

def verify_bm25_line_item_indexing():
    """Verify BM25 index contains line item descriptions and test search functionality."""
    
    print("=" * 70)
    print("BM25 LINE ITEM INDEX VERIFICATION")
    print("=" * 70)
    
    # Set up paths
    current_dir = os.getcwd()
    invoice_current = os.path.join(current_dir, 'invoice-extraction-current')
    
    if not os.path.exists(invoice_current):
        print(f"✗ invoice-extraction-current directory not found at: {invoice_current}")
        return
        
    # Add to Python path
    sys.path.insert(0, invoice_current)
    
    try:
        # Import required modules
        from rag.bm25_retriever import BM25Retriever
        print("✓ Successfully imported BM25Retriever")
        
        # Check database first
        db_path = os.path.join(invoice_current, 'data', 'invoices.db')
        if not os.path.exists(db_path):
            print(f"✗ Database not found at: {db_path}")
            return
            
        print(f"✓ Database found: {db_path}")
        
        # Check line items in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get line item counts
        cursor.execute("SELECT COUNT(*) FROM line_items")
        line_item_count = cursor.fetchone()[0]
        print(f"✓ Database contains {line_item_count:,} line items")
        
        # Sample line items
        cursor.execute("SELECT invoice_id, description, quantity, unit_price FROM line_items LIMIT 5")
        sample_items = cursor.fetchall()
        
        print(f"\nSample line items:")
        for i, (inv_id, desc, qty, price) in enumerate(sample_items, 1):
            print(f"  {i}. Invoice {inv_id}: {desc} (qty: {qty}, price: ₹{price})")
            
        # Initialize BM25 retriever
        try:
            retriever = BM25Retriever(database_path=db_path)
            print(f"✓ BM25Retriever initialized")
        except Exception as e:
            print(f"✗ Failed to initialize BM25Retriever: {e}")
            return
            
        # Check BM25 index file
        bm25_index_path = os.path.join(invoice_current, 'rag', 'bm25_index.pkl')
        if os.path.exists(bm25_index_path):
            size = os.path.getsize(bm25_index_path)
            print(f"✓ BM25 index file exists: {size:,} bytes")
        else:
            print(f"⚠️  BM25 index file not found: {bm25_index_path}")
            
        # Test document string building for sample invoices
        print(f"\n" + "=" * 40)
        print("DOCUMENT STRING VERIFICATION")
        print("=" * 40)
        
        # Get invoices that have line items
        cursor.execute("""
            SELECT DISTINCT i.id, i.invoice_number, COUNT(li.id) as item_count
            FROM invoices i 
            JOIN line_items li ON li.invoice_id = i.id 
            GROUP BY i.id 
            LIMIT 3
        """)
        invoice_samples = cursor.fetchall()
        
        for invoice_id, invoice_num, item_count in invoice_samples:
            print(f"\nTesting Invoice {invoice_num} (ID: {invoice_id}, {item_count} line items):")
            
            # Test _build_document_string method
            if hasattr(retriever, '_build_document_string'):
                try:
                    doc_string = retriever._build_document_string(invoice_id)
                    print(f"  Document string length: {len(doc_string):,} chars")
                    
                    # Check for line item content
                    lines = doc_string.split('\n')
                    line_item_lines = []
                    
                    for line in lines:
                        line_lower = line.lower()
                        if any(keyword in line_lower for keyword in ['description:', 'item:', 'product:', 'service:']):
                            line_item_lines.append(line.strip())
                    
                    print(f"  Line item lines found: {len(line_item_lines)}")
                    
                    # Show first few line item entries
                    for i, line in enumerate(line_item_lines[:3]):
                        print(f"    {i+1}: {line[:80]}...")
                        
                    # Check for specific line item descriptions from database
                    cursor.execute("SELECT description FROM line_items WHERE invoice_id = ? LIMIT 3", (invoice_id,))
                    db_descriptions = [row[0] for row in cursor.fetchall()]
                    
                    print(f"  Database descriptions: {db_descriptions}")
                    
                    # Verify descriptions are in document string
                    found_in_doc = []
                    for desc in db_descriptions:
                        if desc and desc.lower() in doc_string.lower():
                            found_in_doc.append(desc)
                    
                    print(f"  Descriptions found in document: {len(found_in_doc)}/{len(db_descriptions)}")
                    if len(found_in_doc) < len(db_descriptions):
                        print(f"  ⚠️  Some descriptions missing from document string!")
                        for desc in db_descriptions:
                            if desc and desc.lower() not in doc_string.lower():
                                print(f"    Missing: {desc}")
                    else:
                        print(f"  ✓ All descriptions found in document")
                        
                except Exception as e:
                    print(f"  ✗ _build_document_string failed: {e}")
            else:
                print(f"  ✗ _build_document_string method not found")
                
        # Test actual BM25 search functionality
        print(f"\n" + "=" * 40)
        print("BM25 SEARCH TESTING")
        print("=" * 40)
        
        # Test queries that should find line items
        test_queries = [
            "LCD Display Screen",  # Specific product from sample data
            "Keyboard",            # Another specific product
            "line items",          # Generic line item query
            "product description", # Generic product query
            "services",            # Service-related query
        ]
        
        for query in test_queries:
            print(f"\nTesting query: '{query}'")
            try:
                # Test with retrieve method
                results = retriever.retrieve(query, k=5)
                print(f"  Results found: {len(results)}")
                
                if results:
                    for i, result in enumerate(results[:2], 1):
                        inv_num = result.get('invoice_number', 'N/A')
                        score = result.get('score', 0)
                        content_snippet = result.get('content', '')[:100]
                        print(f"    {i}. {inv_num} (score: {score:.3f}) - {content_snippet}...")
                        
                        # Check if result actually contains the query term
                        if query.lower() in content_snippet.lower():
                            print(f"       ✓ Query term found in content")
                        else:
                            print(f"       ⚠️  Query term NOT found in content")
                else:
                    print(f"  ⚠️  No results returned for '{query}'")
                    
            except Exception as e:
                print(f"  ✗ Search failed: {e}")
                
        # Test BM25 index structure if accessible
        print(f"\n" + "=" * 40)
        print("BM25 INDEX STRUCTURE")
        print("=" * 40)
        
        if hasattr(retriever, 'bm25') and retriever.bm25:
            try:
                # Check document count
                if hasattr(retriever.bm25, 'corpus'):
                    doc_count = len(retriever.bm25.corpus)
                    print(f"  Documents in index: {doc_count:,}")
                    
                # Check vocabulary for line item terms
                line_item_terms = ['lcd', 'display', 'screen', 'keyboard', 'item', 'product', 'service', 'description']
                
                if hasattr(retriever.bm25, 'doc_freqs'):
                    vocab_size = len(retriever.bm25.doc_freqs)
                    print(f"  Vocabulary size: {vocab_size:,} terms")
                    
                    found_terms = []
                    for term in line_item_terms:
                        if term in retriever.bm25.doc_freqs:
                            freq = retriever.bm25.doc_freqs[term]
                            found_terms.append(f"{term}({freq})")
                            
                    print(f"  Line item terms in vocabulary: {found_terms}")
                    
                    if not found_terms:
                        print(f"  ✗ NO line item terms found in BM25 vocabulary!")
                    else:
                        print(f"  ✓ Found {len(found_terms)} line item terms")
                        
            except Exception as e:
                print(f"  ✗ Failed to inspect BM25 index: {e}")
        else:
            print(f"  ✗ BM25 index not accessible or not initialized")
            
        conn.close()
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print(f"Make sure you're in the correct directory and dependencies are installed")
        return
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return
        
    print(f"\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    verify_bm25_line_item_indexing()