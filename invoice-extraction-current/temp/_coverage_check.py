import json, glob, os, sys
sys.path.insert(0, r'invoice-extraction-current')
from rag.chunker import chunk_invoice
from rag.indexer import get_collection_stats, _indexed_source_files

files = sorted(glob.glob(r'invoice-extraction-current/outputs/extractions/*.json'))
out = len(files)
sources = []
chunks_total = 0
vendor_missing = 0
billto_missing = 0
invnum_missing = 0

for p in files:
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    src = ((d.get('metadata') or {}).get('source_file') or os.path.basename(p))
    sources.append(src)
    chunks_total += len(chunk_invoice(d, filename=os.path.basename(p)))
    if not ((d.get('vendor') or {}).get('name')):
        vendor_missing += 1
    if not ((d.get('bill_to') or {}).get('name')):
        billto_missing += 1
    if not d.get('invoice_number'):
        invnum_missing += 1

indexed = _indexed_source_files()
missing = [s for s in set(sources) if s not in indexed]
stats = get_collection_stats()

print(f'outputs_json={out}')
print(f'expected_chunks_from_outputs={chunks_total}')
print(f'chroma_total_chunks={stats.get("total_chunks")}')
print(f'indexed_source_files={len(indexed)}')
print(f'missing_indexed_source_files={len(missing)}')
print(f'vendor_name_missing={vendor_missing}')
print(f'bill_to_name_missing={billto_missing}')
print(f'invoice_number_missing={invnum_missing}')
