"""Build the BM25 keyword search index over extracted invoices."""

from core.config import BM25_INDEX_PATH, OUTPUTS_DIR
from rag.bm25_retriever import BM25Retriever


def main():
    retriever = BM25Retriever(index_path=str(BM25_INDEX_PATH))

    print(f"Building BM25 index from: {OUTPUTS_DIR}")
    count = retriever.build_index(extractions_dir=str(OUTPUTS_DIR))
    print(f"Indexed {count} documents  ->  {BM25_INDEX_PATH}")

    # ── Quick sanity test ─────────────────────────────────────────────
    print("\n--- Test 1: exact vendor name 'NIREL DIGITALS' ---")
    for r in retriever.search("NIREL DIGITALS", top_k=3):
        print(f"  score={r['score']:.4f}  file={r['source_file']}  "
              f"vendor={r['vendor_name']}  total={r['total_amount']}")

    print("\n--- Test 2: partial description 'lamination' ---")
    for r in retriever.search("lamination", top_k=3):
        print(f"  score={r['score']:.4f}  file={r['source_file']}  "
              f"vendor={r['vendor_name']}  total={r['total_amount']}")


if __name__ == "__main__":
    main()
