#!/usr/bin/env python3
"""
Minimal Line Item Search Test - Direct file analysis
"""

import sys
import os
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent / "invoice-extraction-current"
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from core.config import BM25_INDEX_PATH, OUTPUTS_DIR
from rag.bm25_retriever import BM25Retriever

def main():
    print("🔧 MINIMAL LINE ITEM SEARCH DEBUG")
    print("="*60)
    
    # Step 1: List extraction files
    extractions_dir = Path(OUTPUTS_DIR) / "extractions"
    json_files = sorted(extractions_dir.glob("*.json"))
    print(f"\n✅ Found {len(json_files)} extraction files")
    
    # Step 2: Check line item content
    print("\n📋 CHECKING LINE ITEM CONTENT:")
    print("-"*60)
    
    known_invoices = {
        "GST001_20260319_085735.json": "Stciker",
        "GST24005_20260319_090439.json": "Sticker",
        "GST003_20260319_085809.json": "Digital Print",
        "GST24028_20260319_091143.json": "A4 Printouts"
    }
    
    for filename, expected_keyword in known_invoices.items():
        filepath = extractions_dir / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            line_items = data.get("line_items", [])
            print(f"\n{filename}:")
            print(f"  Line items count: {len(line_items)}")
            
            for i, item in enumerate(line_items[:3]):
                desc = item.get("description", "")
                print(f"    Item {i+1}: {desc[:60]}")
                if expected_keyword.lower() in desc.lower():
                    print(f"      ✅ Contains '{expected_keyword}'")
        else:
            print(f"\n❌ Not found: {filename}")
    
    # Step 3: Build and test BM25 index
    print("\n\n🏗️  BUILDING BM25 INDEX:")
    print("-"*60)
    
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
    count = retriever.build_index(extractions_dir=str(OUTPUTS_DIR))
    print(f"✅ Indexed {count} documents")
    
    # Step 4: Test searches
    print("\n\n🔍 TESTING SEARCHES:")
    print("-"*60)
    
    test_queries = [
        'sticker',
        'print',
        'label',
        'Sticker With Lamination',
        'Digital Print Out',
        'A4 Printouts',
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = retriever.search(query, top_k=3)
        
        if results:
            for i, result in enumerate(results):
                source = result.get('source_file', 'Unknown')
                score = result.get('score', 0)
                line_items_summary = result.get('line_items_summary', '')[:80]
                print(f"  {i+1}. {source} (score: {score})")
                print(f"     Items: {line_items_summary}")
        else:
            print(f"  ❌ No results")
    
    # Step 5: Check if metadata has line items
    print("\n\n📊 METADATA ANALYSIS:")
    print("-"*60)
    print(f"Total documents in index: {len(retriever.metadata)}")
    
    items_with_summaries = sum(1 for m in retriever.metadata if m.get('line_items_summary'))
    print(f"Documents with line item summaries: {items_with_summaries}")
    
    # Sample some metadata
    print("\nSample metadata entries:")
    for i in range(min(3, len(retriever.metadata))):
        m = retriever.metadata[i]
        print(f"  {m.get('source_file')}: {m.get('line_items_summary')[:60]}")
    
    print("\n🏁 DEBUG COMPLETE")

if __name__ == "__main__":
    main()
