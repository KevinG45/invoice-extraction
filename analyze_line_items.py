#!/usr/bin/env python3
"""
Direct Line Item Search Analysis - No imports, pure analysis
"""

import json
from pathlib import Path

# Direct path analysis
base_path = Path('C:/Users/kmgs4/Documents/Christ Uni/invoice-extraction/invoice-extraction-current')
outputs_path = base_path / 'outputs' / 'extractions'

print("🔍 LINE ITEM SEARCH ISSUE DIAGNOSIS")
print("=" * 70)

# Step 1: Verify files exist
print(f"\n1. Checking outputs directory: {outputs_path}")
print(f"   Directory exists: {outputs_path.exists()}")

json_files = list(outputs_path.glob("*.json"))
print(f"   JSON files found: {len(json_files)}")

# Step 2: Check known test invoices
print(f"\n2. Checking known test invoices:")
print("-" * 70)

known_invoices = {
    "GST001_20260319_085735.json": ["Stciker"],
    "GST24005_20260319_090439.json": ["Sticker", "Lamination"],
    "GST003_20260319_085809.json": ["Digital Print"],
    "GST24028_20260319_091143.json": ["A4 Printouts"],
}

for filename, keywords in known_invoices.items():
    filepath = outputs_path / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        line_items = data.get("line_items", [])
        invoice_id = data.get("invoice_number")
        
        print(f"\n✅ {invoice_id} ({filename})")
        print(f"   Line items: {len(line_items)}")
        
        found_keywords = set()
        for item in line_items:
            desc = item.get("description", "").lower()
            for kw in keywords:
                if kw.lower() in desc:
                    found_keywords.add(kw)
            print(f"     - {item.get('description', 'N/A')[:70]}")
        
        for kw in keywords:
            if kw in found_keywords:
                print(f"   ✅ Contains '{kw}'")
            else:
                print(f"   ❌ MISSING '{kw}'")
    else:
        print(f"\n❌ NOT FOUND: {filename}")

# Step 3: Search for all invoices with print/sticker/label keywords
print(f"\n\n3. Finding ALL invoices with print/sticker/label keywords:")
print("-" * 70)

keywords = ["sticker", "print", "label", "flex", "banner"]
matching_invoices = {}

for json_file in json_files:
    with open(json_file, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            continue
    
    invoice_id = data.get("invoice_number", "UNKNOWN")
    line_items = data.get("line_items", [])
    
    for item in line_items:
        desc = (item.get("description") or "").lower()
        for kw in keywords:
            if kw in desc:
                if invoice_id not in matching_invoices:
                    matching_invoices[invoice_id] = []
                matching_invoices[invoice_id].append((kw, item.get("description")))
                break

print(f"Found {len(matching_invoices)} invoices with target keywords:")
for invoice_id, items in sorted(matching_invoices.items()):
    print(f"\n  {invoice_id}:")
    for kw, desc in items[:2]:
        print(f"    [{kw}] {desc[:65]}")

# Step 4: Check BM25 document building
print(f"\n\n4. Testing BM25 document string building:")
print("-" * 70)

# Simulate what BM25 does
sample_file = outputs_path / "GST001_20260319_085735.json"
if sample_file.exists():
    with open(sample_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Build document string like BM25 does
    parts = []
    
    # Line items
    for item in data.get("line_items", []):
        desc = item.get("description")
        if desc:
            parts.append(str(desc))
    
    doc_text = " ".join(parts)
    print(f"\nGST001 document text from line items:")
    print(f"  '{doc_text}'")
    print(f"  Length: {len(doc_text)} chars")
    
    # Tokenize like BM25
    tokens = [t for t in doc_text.lower().replace("-", " ").split() if len(t) >= 2]
    print(f"  Tokens: {tokens}")
    print(f"  Contains 'sticker': {'sticker' in tokens}")
    print(f"  Contains 'stciker': {'stciker' in tokens}")  # Misspelling
    print(f"  Contains 'size': {'size' in tokens}")

print("\n" + "=" * 70)
print("✅ Analysis complete!")
