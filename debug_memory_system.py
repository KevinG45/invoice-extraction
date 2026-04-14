#!/usr/bin/env python3
"""
Memory System Forensic Analysis
================================
Deep investigation of why _resolve_follow_up_query() returns generic responses
instead of accessing ConversationMemory data.

ISSUE: Memory system shows 0% success rate in test results
ROOT CAUSE: Need to trace data flow from storage to retrieval
"""

import sys
import os

# Add the correct path to invoice-extraction-current
current_dir = os.path.dirname(os.path.abspath(__file__))
invoice_current_path = os.path.join(current_dir, 'invoice-extraction-current')
sys.path.insert(0, invoice_current_path)

try:
    from rag.qa_chain import QAChain
    from core.database_config import get_database_connection
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Available modules in rag/:")
    rag_path = os.path.join(invoice_current_path, 'rag')
    if os.path.exists(rag_path):
        print(os.listdir(rag_path))
    sys.exit(1)

def test_memory_storage_and_retrieval():
    """Test if memory system actually stores and retrieves data correctly."""
    
    print("=" * 60)
    print("MEMORY SYSTEM FORENSIC ANALYSIS")
    print("=" * 60)
    
    # Initialize components
    try:
        conn = get_database_connection()
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return
        
    try:
        qa_chain = QAChain(database_path="invoice-extraction-current/data/invoices.db")
        print("✓ QAChain initialized")
    except Exception as e:
        print(f"✗ QAChain initialization failed: {e}")
        return
    
    # Test 1: Direct memory storage/retrieval
    print("\n1. Testing direct memory storage/retrieval...")
    test_query = "What is Reliance's GSTIN number?"
    test_answer = "Reliance's GSTIN number is 36ARKPC6820F1ZZ"
    
    # Store in memory
    memory.store_interaction(test_query, test_answer, metadata={"strategy": "bm25"})
    print(f"✓ Stored: {test_query[:50]}...")
    
    # Retrieve from memory  
    entities = memory.get_conversation_context()
    print(f"✓ Retrieved {len(entities)} entities from memory")
    for entity in entities:
        print(f"   - {entity}")
    
    # Test 2: Follow-up query resolution
    print("\n2. Testing _resolve_follow_up_query() method...")
    follow_up = "What was their GSTIN again?"
    
    # Check if method exists and is callable
    if hasattr(qa_chain, '_resolve_follow_up_query'):
        print("✓ _resolve_follow_up_query method exists")
        try:
            result = qa_chain._resolve_follow_up_query(follow_up)
            print(f"✓ Method executed successfully")
            print(f"   Result: {result[:100]}..." if result else "   Result: EMPTY OR NULL")
        except Exception as e:
            print(f"✗ Method failed with error: {e}")
    else:
        print("✗ _resolve_follow_up_query method NOT FOUND")
    
    # Test 3: ConversationMemory state inspection
    print("\n3. Inspecting ConversationMemory internal state...")
    print(f"   Memory object type: {type(memory)}")
    print(f"   Memory object methods: {[m for m in dir(memory) if not m.startswith('_')]}")
    
    # Check if memory has data
    if hasattr(memory, 'entities'):
        print(f"   Entities count: {len(memory.entities)}")
        for i, entity in enumerate(memory.entities[:3]):  # First 3
            print(f"   Entity {i+1}: {entity}")
    
    # Test 4: Database connection verification
    print("\n4. Testing database connection...")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM invoices")
        count = cursor.fetchone()[0]
        print(f"✓ Database connected, {count} invoices found")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_memory_storage_and_retrieval()