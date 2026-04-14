#!/usr/bin/env python3
"""
False Negative Override System Forensic Analysis
===============================================
Deep investigation of why the detection system doesn't trigger for obvious cases.

ISSUE: False negative override not triggering when it should
ROOT CAUSE: Need to test detection logic with actual failing test cases
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'invoice-extraction-current'))

def test_false_negative_detection():
    """Test false negative detection logic with real failing test cases."""
    
    print("=" * 60)
    print("FALSE NEGATIVE OVERRIDE FORENSIC ANALYSIS")
    print("=" * 60)
    
    # Test cases from the actual test output showing failures
    test_cases = [
        {
            "query": "What are the line items in GST001?",
            "strategy": "bm25", 
            "sources": [{"content": "Line items: LCD Display Screen, Keyboard"}],
            "llm_answer": "I cannot find the line items for invoice GST001.",
            "should_override": True
        },
        {
            "query": "Show me invoice details for GST002", 
            "strategy": "vector",
            "sources": [{"content": "Invoice GST002: Total ₹15,000"}],
            "llm_answer": "No invoice details found for GST002.",
            "should_override": True
        },
        {
            "query": "What is the weather today?",
            "strategy": "bm25",
            "sources": [],
            "llm_answer": "I cannot find weather information.",
            "should_override": False
        }
    ]
    
    print("\n1. Testing NOT_FOUND_PHRASES detection...")
    
    # Extract the actual phrases from qa_chain.py
    not_found_phrases = [
        "not found", "no invoice", "no invoices", "not available",
        "cannot find", "unable to find", "i don't have",
        "not in the invoice", "not present", "no data",
        "cannot determine", "insufficient information"
    ]
    
    print(f"   Configured phrases: {not_found_phrases}")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test Case #{i}: {test_case['query'][:40]}...")
        answer = test_case['llm_answer'].lower()
        
        # Check phrase matching
        matched_phrases = [phrase for phrase in not_found_phrases if phrase in answer]
        print(f"      Answer: {test_case['llm_answer']}")
        print(f"      Matched phrases: {matched_phrases}")
        print(f"      Has sources: {len(test_case['sources']) > 0}")
        print(f"      Should override: {test_case['should_override']}")
        
        # Simulate detection logic
        would_trigger = (len(matched_phrases) > 0 and 
                        test_case['strategy'] in ("bm25", "vector", "hybrid") and
                        len(test_case['sources']) > 0)
        print(f"      Would trigger: {would_trigger}")
        print(f"      Expected: {test_case['should_override']}")
        
        if would_trigger == test_case['should_override']:
            print(f"      ✓ Detection working correctly")
        else:
            print(f"      ✗ Detection FAILED")
    
    # Test 2: _results_match_query logic
    print("\n2. Testing _results_match_query() logic...")
    
    def simulate_results_match_query(query, sources):
        """Simulate the logic that checks if sources are relevant to query."""
        if not sources:
            return False
            
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for source in sources:
            content = source.get('content', '').lower()
            content_words = set(content.split())
            
            # Check for common words (excluding stop words)
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
            significant_query_words = query_words - stop_words
            overlap = significant_query_words.intersection(content_words)
            
            if len(overlap) >= 2:  # At least 2 significant words match
                return True
                
        return False
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n   Test Case #{i}:")
        query = test_case['query']
        sources = test_case['sources']
        
        match_result = simulate_results_match_query(query, sources)
        print(f"      Query: {query}")
        print(f"      Sources: {len(sources)} found")
        print(f"      Results match query: {match_result}")
        
        if sources:
            print(f"      Source content: {sources[0]['content']}")
    
    # Test 3: _build_factual_answer_from_sources logic
    print("\n3. Testing factual answer building...")
    
    def simulate_build_factual_answer(query, sources):
        """Simulate building a factual answer from sources."""
        if not sources:
            return "No information available."
            
        # Extract key information from first source
        content = sources[0].get('content', '')
        
        if 'line items' in query.lower():
            if 'LCD' in content or 'Keyboard' in content:
                return f"Based on the invoice data, the line items include: {content}."
        elif 'invoice details' in query.lower():
            if '₹' in content or 'Total' in content:
                return f"The invoice details are: {content}."
        
        return f"Based on the available information: {content}."
    
    for test_case in test_cases[:2]:  # Skip weather query
        query = test_case['query']
        sources = test_case['sources']
        
        factual_answer = simulate_build_factual_answer(query, sources)
        print(f"\n   Query: {query}")
        print(f"   Generated answer: {factual_answer}")
        print(f"   Original LLM answer: {test_case['llm_answer']}")
        print(f"   Improvement: {'✓' if len(factual_answer) > len(test_case['llm_answer']) else '?'}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_false_negative_detection()