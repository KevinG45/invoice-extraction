#!/usr/bin/env python3
"""
Quick test script to debug memory system issues.
Simulates the failing memory sequence from the test suite.
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from rag.qa_chain import answer_question
import uuid

def test_memory_sequence():
    """Test the exact sequence that's failing in tests 49-50"""
    
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    
    print("=== MEMORY SYSTEM DEBUG TEST ===")
    print(f"Session ID: {session_id}")
    print()
    
    # Step 1: Ask about GST001 (this should work and store entities)
    print("Step 1: Show me invoice GST001")
    print("-" * 40)
    result1 = answer_question("Show me invoice GST001", session_id=session_id, use_memory=True)
    print(f"Strategy: {result1['strategy']}")
    print(f"Answer: {result1['answer'][:100]}...")
    print()
    
    # Step 2: Follow-up question (this should use memory_direct)
    print("Step 2: What is the vendor name?")
    print("-" * 40)
    result2 = answer_question("What is the vendor name?", session_id=session_id, use_memory=True)
    print(f"Strategy: {result2['strategy']}")
    print(f"Answer: {result2['answer']}")
    print()
    
    # Check if memory worked
    if result2['strategy'] == 'memory_direct':
        print("✅ SUCCESS: Memory system worked!")
    else:
        print("❌ FAILURE: Memory system failed - fell back to:", result2['strategy'])
    
    return result1, result2

if __name__ == "__main__":
    test_memory_sequence()