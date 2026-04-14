#!/usr/bin/env python3
"""
Simple System State Analysis
============================
Basic investigation of the current RAG system state and imports.
"""

import sys
import os

def analyze_system_state():
    """Check what's available in the current system."""
    
    print("=" * 60)
    print("RAG SYSTEM STATE ANALYSIS")
    print("=" * 60)
    
    # Check directory structure
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    invoice_current = os.path.join(current_dir, 'invoice-extraction-current')
    print(f"invoice-extraction-current exists: {os.path.exists(invoice_current)}")
    
    if os.path.exists(invoice_current):
        print(f"Contents of invoice-extraction-current:")
        for item in os.listdir(invoice_current):
            print(f"  - {item}")
            
        # Check RAG directory
        rag_dir = os.path.join(invoice_current, 'rag')
        if os.path.exists(rag_dir):
            print(f"\nContents of rag/:")
            for item in os.listdir(rag_dir):
                print(f"  - {item}")
                
            # Check specific files
            files_to_check = ['qa_chain.py', 'router.py', 'bm25_retriever.py']
            for filename in files_to_check:
                filepath = os.path.join(rag_dir, filename)
                if os.path.exists(filepath):
                    size = os.path.getsize(filepath)
                    print(f"  ✓ {filename}: {size:,} bytes")
                else:
                    print(f"  ✗ {filename}: NOT FOUND")
        
        # Check data directory
        data_dir = os.path.join(invoice_current, 'data')
        if os.path.exists(data_dir):
            print(f"\nContents of data/:")
            for item in os.listdir(data_dir):
                print(f"  - {item}")
                
            # Check database
            db_path = os.path.join(data_dir, 'invoices.db')
            if os.path.exists(db_path):
                size = os.path.getsize(db_path)
                print(f"  ✓ invoices.db: {size:,} bytes")
            else:
                print(f"  ✗ invoices.db: NOT FOUND")
    
    # Try basic imports
    print(f"\n" + "=" * 30)
    print("IMPORT TESTING")
    print("=" * 30)
    
    # Add correct path
    sys.path.insert(0, invoice_current)
    
    modules_to_test = [
        ('rag.qa_chain', 'QAChain'),
        ('rag.router', 'Router'), 
        ('rag.bm25_retriever', 'BM25Retriever'),
        ('core.database_config', 'get_database_connection')
    ]
    
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}: Available")
        except ImportError as e:
            print(f"✗ {module_name}.{class_name}: Import failed - {e}")
        except AttributeError as e:
            print(f"✗ {module_name}.{class_name}: Class not found - {e}")
        except Exception as e:
            print(f"✗ {module_name}.{class_name}: Other error - {e}")
    
    # Try to connect to database
    print(f"\n" + "=" * 30)  
    print("DATABASE TESTING")
    print("=" * 30)
    
    try:
        import sqlite3
        db_path = os.path.join(invoice_current, 'data', 'invoices.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✓ Database connected")
        print(f"  Tables: {[t[0] for t in tables]}")
        
        # Check invoice count
        cursor.execute("SELECT COUNT(*) FROM invoices")
        invoice_count = cursor.fetchone()[0]
        print(f"  Invoice count: {invoice_count}")
        
        # Check line items
        cursor.execute("SELECT COUNT(*) FROM line_items")
        line_item_count = cursor.fetchone()[0] 
        print(f"  Line item count: {line_item_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
    
    print(f"\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    analyze_system_state()