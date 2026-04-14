#!/usr/bin/env python3

# Quick test to check BM25 metadata for GSTIN

from rag.bm25_retriever import BM25Retriever
from core.config import BM25_INDEX_PATH

print("Loading BM25 retriever...")
retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))
retriever.load_index()

print(f"Total documents: {len(retriever.metadata) if retriever.metadata else 0}")

# Look for GST001 specifically
gst001_docs = []
for i, meta in enumerate(retriever.metadata or []):
    if "GST001" in str(meta.get("source_file", "")):
        gst001_docs.append((i, meta))

print(f"\nFound {len(gst001_docs)} GST001 documents:")
for i, (idx, meta) in enumerate(gst001_docs):
    print(f"  [{idx}] {meta.get('source_file')}")
    print(f"      vendor_gstin: {meta.get('vendor_gstin')}")
    print(f"      bill_to_gstin: {meta.get('bill_to_gstin')}")
    print(f"      vendor_name: {meta.get('vendor_name')}")

# Test the GSTIN search
print(f"\nTesting GSTIN search for '36ARKPC6820F1ZZ':")
results = retriever.search("Find GSTIN 36ARKPC6820F1ZZ", top_k=5)
print(f"Results: {len(results)}")
for i, result in enumerate(results):
    print(f"  [{i}] Score: {result.get('score', 'N/A'):.3f}")
    print(f"      Source: {result.get('source_file')}")
    print(f"      Vendor: {result.get('vendor_name')}")

# Test just the GSTIN without context
print(f"\nTesting direct GSTIN '36ARKPC6820F1ZZ':")
results = retriever.search("36ARKPC6820F1ZZ", top_k=5)
print(f"Results: {len(results)}")
for i, result in enumerate(results):
    print(f"  [{i}] Score: {result.get('score', 'N/A'):.3f}")
    print(f"      Source: {result.get('source_file')}")