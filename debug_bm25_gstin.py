#!/usr/bin/env python3
"""
Debug script: Check BM25 metadata for GSTIN 36ARKPC6820F1ZZ

This script investigates why test cases #17, #67, #77 fail to find GSTIN 36ARKPC6820F1ZZ
which should be in GST001.pdf invoice data.
"""

import sys
import json
import pickle
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent / "invoice-extraction-current"
sys.path.insert(0, str(project_root))

from rag.bm25_retriever import BM25Retriever

def main():
    print("🔍 DEBUGGING BM25 GSTIN LOOKUP")
    print("="*50)
    
    # Initialize BM25 retriever
    bm25_retriever = BM25Retriever(index_path="invoice-extraction-current/rag/bm25_index.pkl")
    
    # Try to load existing index
    try:
        bm25_retriever.load_index()
        print(f"✅ Loaded BM25 index with {len(bm25_retriever.metadata)} documents")
    except FileNotFoundError:
        print("❌ BM25 index not found. Building new index...")
        # Build index from JSON extractions
        num_docs = bm25_retriever.build_index("invoice-extraction-current/data/extractions")
        print(f"✅ Built BM25 index with {num_docs} documents")
        
        # Save the index
        bm25_retriever.save_index()
        print("✅ Saved BM25 index")
    
    # Search for the problematic GSTIN
    target_gstin = "36ARKPC6820F1ZZ"
    print(f"\n🔎 Searching for GSTIN: {target_gstin}")
    
    # Check metadata for any GSTIN matches
    gstin_matches = []
    for i, meta in enumerate(bm25_retriever.metadata):
        vendor_gstin = meta.get("vendor_gstin")
        bill_to_gstin = meta.get("bill_to_gstin") 
        
        if vendor_gstin == target_gstin or bill_to_gstin == target_gstin:
            gstin_matches.append((i, meta))
            print(f"📄 Doc {i}: {meta.get('source_file')}")
            print(f"   vendor_gstin: {vendor_gstin}")
            print(f"   bill_to_gstin: {bill_to_gstin}")
            print(f"   invoice_id: {meta.get('invoice_id')}")
    
    if not gstin_matches:
        print(f"❌ No exact matches for GSTIN {target_gstin} in metadata")
        
        # Show all GSTINs to see what we have
        print(f"\n📋 All GSTINs in database:")
        unique_gstins = set()
        for meta in bm25_retriever.metadata:
            if meta.get("vendor_gstin"):
                unique_gstins.add(meta.get("vendor_gstin"))
            if meta.get("bill_to_gstin"):
                unique_gstins.add(meta.get("bill_to_gstin"))
        
        for gstin in sorted(unique_gstins):
            if gstin:  # Skip None values
                print(f"  - {gstin}")
    
    # Test BM25 search for the GSTIN
    print(f"\n🔍 Testing BM25 search for '{target_gstin}'")
    results = bm25_retriever.search(target_gstin, top_k=5)
    
    if results:
        print(f"✅ BM25 search returned {len(results)} results:")
        for i, (score, doc_id, meta, text) in enumerate(results):
            print(f"  {i+1}. Score: {score:.3f}, Doc: {meta.get('source_file')}")
            print(f"      Invoice: {meta.get('invoice_id')}")
            print(f"      Vendor GSTIN: {meta.get('vendor_gstin')}")
            print(f"      Bill-To GSTIN: {meta.get('bill_to_gstin')}")
    else:
        print(f"❌ BM25 search returned no results")
    
    # Check the raw JSON file for GST001
    print(f"\n📄 Checking GST001.json extraction directly...")
    gst001_path = Path("invoice-extraction-current/data/extractions/GST001.json")
    if gst001_path.exists():
        with open(gst001_path, 'r', encoding='utf-8') as f:
            gst001_data = json.load(f)
        
        vendor = gst001_data.get("vendor", {})
        bill_to = gst001_data.get("bill_to", {})
        
        print(f"  vendor.tax_id: {vendor.get('tax_id')}")
        print(f"  bill_to.tax_id: {bill_to.get('tax_id')}")
        print(f"  invoice_number: {gst001_data.get('invoice_number')}")
        
        # Check if either matches our target
        if vendor.get('tax_id') == target_gstin or bill_to.get('tax_id') == target_gstin:
            print(f"✅ Found {target_gstin} in GST001.json!")
        else:
            print(f"❌ {target_gstin} not found in GST001.json")
    else:
        print("❌ GST001.json not found")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main()