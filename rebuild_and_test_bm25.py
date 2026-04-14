#!/usr/bin/env python3
"""
Rebuild BM25 index and test GSTIN lookup
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path  
project_root = Path(__file__).parent / "invoice-extraction-current"
sys.path.insert(0, str(project_root))

# Set working directory to project root
os.chdir(project_root)

from core.config import BM25_INDEX_PATH, OUTPUTS_DIR
from rag.bm25_retriever import BM25Retriever

def main():
    print(f"🔧 REBUILDING BM25 INDEX")
    print(f"From: {OUTPUTS_DIR}")
    print(f"To: {BM25_INDEX_PATH}")
    print("="*50)
    
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
    
    # Build fresh index (automatically saves to disk)
    count = retriever.build_index(extractions_dir=str(OUTPUTS_DIR))
    print(f"✅ Indexed {count} documents")
    print(f"✅ Saved to {BM25_INDEX_PATH}")
    
    print(f"\n🔍 TESTING GSTIN LOOKUP")
    print("="*50)
    
    # Test the problematic GSTIN
    gstin_query = "36ARKPC6820F1ZZ"
    print(f"Searching for: {gstin_query}")
    
    results = retriever.search(gstin_query, top_k=10)
    
    if results:
        print(f"✅ Found {len(results)} results:")
        for i, r in enumerate(results):
            score = r.get('score', 0)
            source_file = r.get('source_file', 'Unknown')
            vendor_gstin = r.get('vendor_gstin')
            bill_to_gstin = r.get('bill_to_gstin')
            vendor_name = r.get('vendor_name', 'Unknown')
            
            print(f"  {i+1}. Score: {score:.4f}")
            print(f"      File: {source_file}")
            print(f"      Vendor: {vendor_name}")
            print(f"      Vendor GSTIN: {vendor_gstin}")
            print(f"      Bill-To GSTIN: {bill_to_gstin}")
            
            # Check if this matches our target
            if vendor_gstin == gstin_query or bill_to_gstin == gstin_query:
                print(f"      ✅ EXACT MATCH FOUND!")
            print()
    else:
        print(f"❌ No results found for {gstin_query}")
    
    print(f"🔍 TESTING OTHER QUERIES")
    print("="*50)
    
    # Test a known working query
    print(f"Testing 'NIREL DIGITALS'...")
    nirel_results = retriever.search("NIREL DIGITALS", top_k=3)
    if nirel_results:
        print(f"✅ Found {len(nirel_results)} results for NIREL DIGITALS")
        for r in nirel_results[:2]:  # Show first 2
            print(f"  - {r.get('source_file')} (score: {r.get('score', 0):.4f})")
    else:
        print("❌ No results for NIREL DIGITALS")
    
    # Test BM25 exact match logic
    print(f"\n🔧 CHECKING METADATA FOR GST001")
    print("="*50)
    
    # Look for GST001 in metadata
    for i, meta in enumerate(retriever.metadata):
        source_file = meta.get('source_file', '')
        if 'GST001' in source_file:
            print(f"Found GST001 metadata at index {i}:")
            print(f"  source_file: {meta.get('source_file')}")
            print(f"  invoice_id: {meta.get('invoice_id')}")
            print(f"  vendor_gstin: {meta.get('vendor_gstin')}")
            print(f"  bill_to_gstin: {meta.get('bill_to_gstin')}")
            print(f"  vendor_name: {meta.get('vendor_name')}")
            break
    else:
        print("❌ No GST001 found in metadata")

if __name__ == "__main__":
    main()