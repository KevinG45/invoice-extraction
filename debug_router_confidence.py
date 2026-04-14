#!/usr/bin/env python3
"""
Router Confidence Analysis
==========================
Deep investigation of why strategy accuracy is 73% vs 85% target.

ISSUE: Router choosing wrong strategies, confidence scores miscalibrated
ROOT CAUSE: Need to profile decision-making process and confidence score calibration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'invoice-extraction-current'))

def test_router_confidence_calibration():
    """Analyze router decision-making and confidence scoring."""
    
    print("=" * 60)
    print("ROUTER CONFIDENCE FORENSIC ANALYSIS")
    print("=" * 60)
    
    # Import router and test with actual test cases that failed
    try:
        from rag.router import Router
        router = Router(database_path="invoice-extraction-current/data/invoices.db")
    except Exception as e:
        print(f"✗ Failed to initialize router: {e}")
        return
    
    # Test cases from actual failures - analyze routing decisions
    test_cases = [
        {
            "query": "What are the line items in GST001?",
            "expected_strategy": "bm25",  # Should use BM25 for exact match + line items
            "category": "line_item_search"
        },
        {
            "query": "Find invoices with total amount greater than 50000",
            "expected_strategy": "sql", # Should use SQL for numerical comparison
            "category": "sql_aggregate"  
        },
        {
            "query": "Who is the vendor for invoice GST001?",
            "expected_strategy": "bm25", # Should use BM25 for exact invoice lookup
            "category": "bm25_exact"
        },
        {
            "query": "What companies have issued the most invoices?",
            "expected_strategy": "sql", # Should use SQL for aggregation
            "category": "sql_aggregate"
        },
        {
            "query": "Show me invoices related to technology services",
            "expected_strategy": "vector", # Should use vector for semantic search
            "category": "vector_semantic"
        },
        {
            "query": "What was the GSTIN number again?", 
            "expected_strategy": "memory", # Should use memory for follow-up
            "category": "conversation_memory"
        }
    ]
    
    print("\n1. Testing routing accuracy for known test cases...")
    
    correct_routes = 0
    for i, test_case in enumerate(test_cases, 1):
        query = test_case['query']
        expected = test_case['expected_strategy']
        category = test_case['category']
        
        print(f"\n   Test #{i} ({category}):")
        print(f"      Query: {query}")
        print(f"      Expected: {expected}")
        
        try:
            # Get routing decision
            route_result = router.route_query(query)
            actual = route_result.get('strategy', 'unknown')
            confidence = route_result.get('confidence', 0.0)
            
            print(f"      Actual: {actual}")
            print(f"      Confidence: {confidence:.3f}")
            
            # Check if correct
            is_correct = (actual == expected)
            correct_routes += int(is_correct)
            print(f"      Result: {'✓' if is_correct else '✗'}")
            
            # Analyze confidence appropriateness
            if is_correct and confidence < 0.7:
                print(f"      ⚠️  Correct but low confidence ({confidence:.3f})")
            elif not is_correct and confidence > 0.8:
                print(f"      ⚠️  Wrong but high confidence ({confidence:.3f})")
                
        except Exception as e:
            print(f"      ✗ Routing failed: {e}")
    
    accuracy = (correct_routes / len(test_cases)) * 100
    print(f"\n   Overall Accuracy: {correct_routes}/{len(test_cases)} = {accuracy:.1f}%")
    print(f"   Target: 85%")
    print(f"   Gap: {85 - accuracy:.1f} percentage points")
    
    # Test 2: Confidence score distribution analysis
    print("\n2. Analyzing confidence score distribution...")
    
    confidence_ranges = {
        "very_low": (0.0, 0.3),
        "low": (0.3, 0.5), 
        "medium": (0.5, 0.7),
        "high": (0.7, 0.9),
        "very_high": (0.9, 1.0)
    }
    
    range_counts = {range_name: 0 for range_name in confidence_ranges}
    range_accuracy = {range_name: [] for range_name in confidence_ranges}
    
    # Test with a broader set of queries
    broader_test_queries = [
        "How many invoices total?",
        "What is the vendor GSTIN?", 
        "Show me technology related invoices",
        "Find high value invoices",
        "What are line items?",
        "Who was the previous vendor?",
        "Calculate average invoice amount",
        "Search for Mumbai vendors"
    ]
    
    for query in broader_test_queries:
        try:
            route_result = router.route_query(query)
            confidence = route_result.get('confidence', 0.0)
            
            # Find which range this confidence falls into
            for range_name, (low, high) in confidence_ranges.items():
                if low <= confidence < high:
                    range_counts[range_name] += 1
                    break
                    
        except Exception as e:
            print(f"      Failed for query '{query}': {e}")
    
    print(f"   Confidence distribution:")
    for range_name, count in range_counts.items():
        low, high = confidence_ranges[range_name]
        percentage = (count / len(broader_test_queries)) * 100
        print(f"      {range_name.replace('_', ' ').title()} ({low:.1f}-{high:.1f}): {count} queries ({percentage:.1f}%)")
    
    # Test 3: Pattern matching analysis  
    print("\n3. Analyzing pattern matching effectiveness...")
    
    # Check if patterns are correctly identifying different query types
    pattern_categories = {
        "sql": ["count", "total", "sum", "average", "how many", "greater than"],
        "bm25": ["gstin", "invoice number", "specific invoice", "exact"],
        "vector": ["related to", "similar", "about", "concerning"], 
        "memory": ["again", "previous", "earlier", "what was"]
    }
    
    for category, keywords in pattern_categories.items():
        print(f"\n   Testing {category.upper()} patterns:")
        
        for keyword in keywords[:3]:  # Test first 3 keywords
            test_query = f"Test query with {keyword} keyword"
            try:
                route_result = router.route_query(test_query)
                strategy = route_result.get('strategy', 'unknown')
                confidence = route_result.get('confidence', 0.0)
                
                matches_expected = (strategy == category)
                print(f"      '{keyword}' → {strategy} ({confidence:.2f}) {'✓' if matches_expected else '✗'}")
                
            except Exception as e:
                print(f"      '{keyword}' → Failed: {e}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_router_confidence_calibration()