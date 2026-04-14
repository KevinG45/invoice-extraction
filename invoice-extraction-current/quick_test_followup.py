#!/usr/bin/env python3
"""
Quick test to verify follow-up detection logic.
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from rag.router import is_follow_up

def test_followup_detection():
    """Test the improved follow-up detection"""
    
    test_cases = [
        # Should be FALSE (not follow-ups)
        ("Show 'Net 30' payment terms invoices", False),
        ("Show me invoice GST001", False),
        ("What is the total tax amount across all invoices?", False),
        ("List all invoices from NIREL DIGITALS", False),
        ("Find invoices with payment terms 'Net 30'", False),
        
        # Should be TRUE (real follow-ups)
        ("What is the vendor name?", True),
        ("What is their GSTIN?", True), 
        ("What is the total?", True),
        ("What about the tax?", True),
        ("And the date?", True),
        ("Their address?", True),
    ]
    
    print("=== FOLLOW-UP DETECTION TEST ===")
    print()
    
    for query, expected in test_cases:
        result = is_follow_up(query)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status} | '{query}' -> {result} (expected {expected})")
    
    print()

if __name__ == "__main__":
    test_followup_detection()