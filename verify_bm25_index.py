#!/usr/bin/env python3
"""
Verify BM25 index status and GSTIN lookup capability.

This script:
1. Checks if index file exists and its age
2. Loads the index and checks metadata
3. Tests GSTIN search functionality
4. Recommends actions if needed
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pickle

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/invoice-extraction-current")

from core.config import BM25_INDEX_PATH, OUTPUTS_DIR
from rag.bm25_retriever import BM25Retriever

def check_index_file():
    """Check if index file exists and its age."""
    index_path = Path(BM25_INDEX_PATH)
    if not index_path.exists():
        return None, "MISSING"
    
    stat = index_path.stat()
    size = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime)
    age = datetime.now() - mtime
    return (size, mtime), age

def check_extractions_count():
    """Count JSON extraction files."""
    extractions_dir = Path(OUTPUTS_DIR)
    if not extractions_dir.exists():
        return 0
    json_files = list(extractions_dir.glob("*.json"))
    return len(json_files)

def load_index_metadata():
    """Load index metadata directly from pickle file."""
    try:
        with open(BM25_INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        return data.get("metadata", [])
    except Exception as e:
        return None

def main():
    print("=" * 70)
    print("BM25 INDEX DIAGNOSTIC REPORT")
    print("=" * 70)
    
    # Check 1: Index file status
    print("\n📁 INDEX FILE STATUS")
    print("-" * 70)
    index_info, age = check_index_file()
    if index_info is None:
        print(f"❌ Index file NOT FOUND: {BM25_INDEX_PATH}")
        print("   → Need to rebuild index with: python run_bm25_index.py")
    else:
        size_mb = index_info[0] / (1024 * 1024)
        print(f"✓ Index file exists: {BM25_INDEX_PATH}")
        print(f"  Size: {size_mb:.2f} MB")
        print(f"  Modified: {index_info[1]}")
        print(f"  Age: {age.days}d {age.seconds//3600}h")
    
    # Check 2: Extraction files
    print("\n📊 EXTRACTION FILES")
    print("-" * 70)
    extraction_count = check_extractions_count()
    print(f"✓ Total extraction files: {extraction_count}")
    print(f"  Location: {OUTPUTS_DIR}")
    
    # Check 3: Index metadata
    print("\n🔍 INDEX METADATA")
    print("-" * 70)
    metadata = load_index_metadata()
    if metadata is None:
        print("❌ Could not load index metadata")
    else:
        print(f"✓ Metadata records: {len(metadata)}")
        if len(metadata) < extraction_count:
            print(f"⚠ WARNING: Index has {len(metadata)} records but {extraction_count} extraction files exist")
            print("   → Index may be STALE. Need to rebuild.")
        
        # Check for GST001
        gst001_count = sum(1 for m in metadata if "GST001" in str(m.get("source_file", "")))
        print(f"  GST001 documents in index: {gst001_count}")
        
        # Check for target GSTIN
        target_gstin = "36ARKPC6820F1ZZ"
        gstin_count = sum(1 for m in metadata 
                          if (m.get("vendor_gstin") or "").upper() == target_gstin 
                          or (m.get("bill_to_gstin") or "").upper() == target_gstin)
        print(f"  Documents with GSTIN {target_gstin}: {gstin_count}")
    
    # Check 4: GSTIN search functionality
    print("\n🔎 GSTIN SEARCH TEST")
    print("-" * 70)
    try:
        retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
        retriever.load_index()
        
        if retriever.bm25 is None:
            print("❌ BM25 index is not loaded (bm25 object is None)")
        else:
            print(f"✓ BM25 index loaded successfully")
            print(f"  Corpus size: {len(retriever.corpus)} documents")
            
            # Test GSTIN search
            target_gstin = "36ARKPC6820F1ZZ"
            print(f"\n  Testing search for GSTIN: {target_gstin}")
            results = retriever.search(target_gstin, top_k=10)
            
            if not results:
                print(f"  ❌ NO RESULTS FOUND for {target_gstin}")
            else:
                print(f"  ✓ Found {len(results)} results:")
                for i, r in enumerate(results[:3]):
                    score = r.get('score', 0)
                    source = r.get('source_file', 'Unknown')
                    vendor_gstin = r.get('vendor_gstin', '')
                    bill_to_gstin = r.get('bill_to_gstin', '')
                    vendor_name = r.get('vendor_name', '')
                    
                    # Check if this is an exact match
                    is_exact = (vendor_gstin.upper() == target_gstin or 
                                bill_to_gstin.upper() == target_gstin)
                    exact_marker = "✓ EXACT MATCH" if is_exact else ""
                    
                    print(f"\n    [{i+1}] Score: {score} {exact_marker}")
                    print(f"        File: {source}")
                    print(f"        Vendor: {vendor_name}")
                    print(f"        Vendor GSTIN: {vendor_gstin}")
                    print(f"        Bill-To GSTIN: {bill_to_gstin}")
    
    except Exception as e:
        print(f"❌ Error during search test: {e}")
        import traceback
        traceback.print_exc()
    
    # Recommendations
    print("\n" + "=" * 70)
    print("📋 RECOMMENDATIONS")
    print("=" * 70)
    
    if index_info is None or (metadata and len(metadata) < extraction_count):
        print("\n1. REBUILD INDEX:")
        print("   Run: python invoice-extraction-current/run_bm25_index.py")
        print("   This will rebuild the index from all extraction files.")
    
    if metadata and gstin_count == 0:
        print("\n2. VERIFY EXTRACTION DATA:")
        print(f"   The GSTIN {target_gstin} is not in the index.")
        print("   Check if:")
        print("   a) The extraction contains this GSTIN")
        print("   b) The index was rebuilt after extractions")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
