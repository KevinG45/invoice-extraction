# QUICK FIX CHECKLIST

## Summary
Tests #17, #67, #77 fail because GSTIN "36ARKPC6820F1ZZ" is not found. Root cause: **Stale BM25 Index**

## What Was Fixed ✅

### 1. rebuild_and_test_bm25.py
- ❌ Removed call to non-existent `save_index()` method
- ✅ Fixed: `build_index()` automatically saves to disk

### 2. debug_gstin.py  
- ❌ Was: `BM25Retriever()` (missing parameter)
- ✅ Now: `BM25Retriever(index_path=str(BM25_INDEX_PATH))`
- ✅ Added: `retriever.load_index()`

### 3. test_bm25_quick.py
- ❌ Was: `BM25Retriever()` (missing parameter and load call)
- ✅ Now: Correct initialization with load_index()

## How to Verify the Fix

### Quick Test (2 minutes)
```bash
cd "C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"
python rebuild_and_test_bm25.py
```

**Look for these in output:**
- ✅ `Indexed X documents` (should be ~96)
- ✅ `EXACT MATCH FOUND!` for GSTIN 36ARKPC6820F1ZZ
- ✅ `Score: 999.0000` (indicates exact match)

### Detailed Diagnosis (1 minute)
```bash
python verify_bm25_index.py
```

**Expected output:**
- Index file status
- Extraction file count
- Metadata record count
- GSTIN search results

### Run the Actual Tests (5 minutes)
```bash
cd invoice-extraction-current
python -m pytest ../tests/ -v -k "test_17 or test_67 or test_77"
```

**Should see:** All 3 tests PASS ✅

---

## Key Information

### GSTIN Details
- **GSTIN**: 36ARKPC6820F1ZZ
- **Vendor**: NIREL DIGITALS
- **Location**: GST001 invoices (multiple versions)
- **Files**: 75+ extraction files contain this GSTIN

### Index Information
- **Location**: `invoice-extraction-current/rag/bm25_index.pkl`
- **Extraction dir**: `invoice-extraction-current/outputs/extractions/`
- **File count**: 96 JSON files
- **Index records**: Should match file count after rebuild

### Regex Pattern (CORRECT)
```
\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b
```
Matches: `36ARKPC6820F1ZZ` ✓

### Exact Match Logic (WORKING)
- When GSTIN found in query → Score forced to 999
- Guaranteed top result
- Works for both vendor_gstin and bill_to_gstin

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "No results found" | Stale index | Run `python run_bm25_index.py` |
| AttributeError: save_index | Old script version | Use latest rebuild_and_test_bm25.py |
| TypeError: missing index_path | Old initialization | Use updated debug_gstin.py |
| Index has 0 records | Not loaded | Call `retriever.load_index()` |

---

## Files Changed
- ✅ rebuild_and_test_bm25.py (1 fix)
- ✅ invoice-extraction-current/debug_gstin.py (1 fix)
- ✅ invoice-extraction-current/test_bm25_quick.py (1 fix)
- ✓ verify_bm25_index.py (new diagnostic tool)
- ✓ BM25_FIX_REPORT.md (this documentation)

---

**Status**: Ready for testing ✅
**Est. Time to Fix**: Run `python run_bm25_index.py` (~30 seconds)
**Est. Time to Verify**: Run test suite (~2 minutes)
